"""Core backtest engine — pure Python, no external framework."""
import math
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.backtest import BacktestRun, BacktestSnapshot, BacktestPosition, BacktestMetrics
from app.models.signal import WeeklySelection, SelectionPick
from app.models.ticker import Ticker, TickerPrice, FxDaily


@dataclass
class Position:
    ticker_id: str
    shares: float
    entry_price: float


@dataclass
class Order:
    ticker_id: str
    shares: float  # positive = buy, negative = sell
    price: float
    notional: float = 0.0


@dataclass
class Portfolio:
    cash: float
    positions: dict = field(default_factory=dict)  # ticker_id -> Position

    def total_value(self, prices: dict, fx_rates: dict) -> float:
        val = self.cash
        for tid, pos in self.positions.items():
            if tid in prices and prices[tid]:
                fx = fx_rates.get(tid, 1.0)
                val += pos.shares * prices[tid] * fx
        return val

    def rebalance(self, targets: dict, prices: dict, fx_rates: dict, min_trade: float = 50) -> list[Order]:
        total = self.total_value(prices, fx_rates)
        orders = []

        # Sell positions not in targets
        for tid in list(self.positions.keys()):
            if tid not in targets and tid in prices and prices[tid]:
                pos = self.positions[tid]
                fx = fx_rates.get(tid, 1.0)
                orders.append(Order(
                    ticker_id=tid, shares=-pos.shares, price=prices[tid],
                    notional=pos.shares * prices[tid] * fx,
                ))

        # Resize/buy
        for tid, weight in targets.items():
            if tid not in prices or not prices[tid]:
                continue
            fx = fx_rates.get(tid, 1.0)
            target_value = total * weight
            current_value = 0
            if tid in self.positions:
                current_value = self.positions[tid].shares * prices[tid] * fx
            delta_value = target_value - current_value
            if abs(delta_value) < min_trade:
                continue
            delta_shares = delta_value / (prices[tid] * fx)
            orders.append(Order(
                ticker_id=tid, shares=delta_shares, price=prices[tid],
                notional=abs(delta_value),
            ))

        return orders

    def execute(self, orders: list[Order], fx_rates: dict):
        for order in orders:
            fx = fx_rates.get(order.ticker_id, 1.0)
            cost = order.shares * order.price * fx
            self.cash -= cost

            if order.ticker_id in self.positions:
                pos = self.positions[order.ticker_id]
                new_shares = pos.shares + order.shares
                if abs(new_shares) < 0.0001:
                    del self.positions[order.ticker_id]
                else:
                    pos.shares = new_shares
            elif order.shares > 0:
                self.positions[order.ticker_id] = Position(
                    ticker_id=order.ticker_id,
                    shares=order.shares,
                    entry_price=order.price,
                )


class BacktestEngine:
    def __init__(self, run: BacktestRun, db: Session):
        self.run = run
        self.db = db

    def execute(self):
        """Run the full backtest."""
        weeks = self._get_signal_weeks()
        if not weeks:
            return

        portfolio = Portfolio(cash=float(self.run.initial_capital))
        equity_curve = []
        trade_log = []

        for week_date in weeks:
            picks = self._get_week_picks(week_date)
            if not picks:
                # No signal — mark-to-market with latest prices
                monday = self._next_monday(week_date)
                prices = self._get_prices(list(portfolio.positions.keys()), monday)
                fx_rates = self._get_fx_rates(monday)
                val = portfolio.total_value(prices, fx_rates)
                equity_curve.append({"date": str(monday), "value": round(val, 2)})
                continue

            ticker_ids = [p.ticker_id for p in picks]
            target_weights = {tid: 1.0 / len(ticker_ids) for tid in ticker_ids}

            monday = self._next_monday(week_date)
            all_tids = list(set(list(portfolio.positions.keys()) + ticker_ids))
            prices = self._get_prices(all_tids, monday)
            fx_rates = self._get_fx_rates(monday)

            orders = portfolio.rebalance(target_weights, prices, fx_rates)

            # Apply costs
            commission_pct = float(self.run.commission_pct)
            slippage_bps = float(self.run.slippage_bps) / 10000
            for order in orders:
                cost = order.notional * (commission_pct + slippage_bps)
                portfolio.cash -= cost
                trade_log.append({
                    "date": str(monday),
                    "ticker_id": str(order.ticker_id),
                    "shares": round(order.shares, 4),
                    "price": round(order.price, 4),
                    "cost": round(cost, 4),
                    "notional": round(order.notional, 2),
                })

            portfolio.execute(orders, fx_rates)

            # Snapshot
            val = portfolio.total_value(prices, fx_rates)
            equity_curve.append({"date": str(monday), "value": round(val, 2)})

            snapshot = BacktestSnapshot(
                run_id=self.run.id, snapshot_date=monday,
                total_value=round(val, 2), cash=round(portfolio.cash, 2),
            )
            self.db.add(snapshot)
            self.db.flush()

            for tid, pos in portfolio.positions.items():
                bp = BacktestPosition(
                    snapshot_id=snapshot.id, ticker_id=tid,
                    shares=round(pos.shares, 4), entry_price=round(pos.entry_price, 4),
                    current_price=round(prices.get(tid, 0), 4),
                    weight=round((pos.shares * prices.get(tid, 0) * fx_rates.get(tid, 1)) / val, 4) if val else 0,
                )
                self.db.add(bp)

        # Compute metrics
        self._compute_metrics(equity_curve, "portfolio")
        self.db.commit()

    def _get_signal_weeks(self) -> list[date]:
        result = self.db.execute(
            select(WeeklySelection.week_date)
            .where(
                WeeklySelection.workspace_id == self.run.workspace_id,
                WeeklySelection.week_date >= self.run.start_date,
                WeeklySelection.week_date <= self.run.end_date,
            )
            .order_by(WeeklySelection.week_date)
        )
        return [row[0] for row in result.all()]

    def _get_week_picks(self, week_date: date) -> list[SelectionPick]:
        result = self.db.execute(
            select(SelectionPick)
            .join(WeeklySelection, SelectionPick.selection_id == WeeklySelection.id)
            .where(
                WeeklySelection.workspace_id == self.run.workspace_id,
                WeeklySelection.week_date == week_date,
            )
        )
        picks = result.scalars().all()

        if self.run.deduplicate:
            seen = set()
            unique = []
            for p in picks:
                if p.ticker_id not in seen:
                    seen.add(p.ticker_id)
                    unique.append(p)
            picks = unique

        return picks

    def _next_monday(self, d: date) -> date:
        """Get the next Monday on or after date d."""
        days_ahead = (7 - d.weekday()) % 7
        if days_ahead == 0 and d.weekday() != 0:
            days_ahead = 7 - d.weekday()
        if d.weekday() == 0:
            return d
        return d + timedelta(days=days_ahead)

    def _get_prices(self, ticker_ids: list, target_date: date) -> dict:
        """Get open prices for tickers on target_date (or closest prior trading day)."""
        prices = {}
        for tid in ticker_ids:
            result = self.db.execute(
                select(TickerPrice)
                .where(
                    TickerPrice.ticker_id == tid,
                    TickerPrice.date <= target_date,
                )
                .order_by(TickerPrice.date.desc())
                .limit(1)
            )
            price = result.scalar_one_or_none()
            if price and price.open:
                prices[tid] = float(price.open)
            elif price and price.close:
                prices[tid] = float(price.close)
        return prices

    def _get_fx_rates(self, target_date: date) -> dict:
        """Get EUR/USD and EUR/CAD rates for currency conversion."""
        # For now, return 1.0 (EUR base, prices in local currency)
        # TODO: implement proper FX conversion
        return {}

    def _compute_metrics(self, equity_curve: list[dict], source: str):
        if len(equity_curve) < 2:
            return

        values = [e["value"] for e in equity_curve]
        initial = values[0]
        final = values[-1]

        # Weekly returns
        returns = []
        for i in range(1, len(values)):
            if values[i - 1] > 0:
                returns.append(values[i] / values[i - 1] - 1)

        if not returns:
            return

        returns_arr = np.array(returns)
        total_return = final / initial - 1

        # Annualization (weekly data)
        n_weeks = len(returns)
        n_years = n_weeks / 52
        cagr = (final / initial) ** (1 / n_years) - 1 if n_years > 0 else 0

        vol = float(returns_arr.std() * math.sqrt(52))
        rf_weekly = 0.04 / 52  # ~4% risk-free
        sharpe = float((returns_arr.mean() - rf_weekly) / returns_arr.std() * math.sqrt(52)) if returns_arr.std() > 0 else 0

        # Max drawdown
        peak = values[0]
        max_dd = 0
        for v in values:
            if v > peak:
                peak = v
            dd = (peak - v) / peak
            if dd > max_dd:
                max_dd = dd

        # Sortino
        downside = returns_arr[returns_arr < 0]
        downside_std = float(downside.std()) if len(downside) > 0 else 0
        sortino = float((returns_arr.mean() - rf_weekly) / downside_std * math.sqrt(52)) if downside_std > 0 else 0

        calmar = cagr / max_dd if max_dd > 0 else 0
        win_rate = float(np.sum(returns_arr > 0) / len(returns_arr))

        metrics = BacktestMetrics(
            run_id=self.run.id,
            source=source,
            total_return=round(total_return, 4),
            cagr=round(cagr, 4),
            volatility=round(vol, 4),
            sharpe_ratio=round(sharpe, 4),
            max_drawdown=round(max_dd, 4),
            sortino_ratio=round(sortino, 4),
            calmar_ratio=round(calmar, 4),
            win_rate=round(win_rate, 4),
            equity_curve=equity_curve,
        )
        self.db.add(metrics)
