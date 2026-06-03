import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_workspace_with_role
from app.models.signal import WeeklySignal, WeeklySelection, SelectionPick, CompanyDossier
from app.models.ticker import Ticker
from app.models.workspace import Workspace
from app.schemas.signal import HeatmapResponse, HeatmapCell, TickerInfo, SignalSummary, SignalDetail, DossierResponse

router = APIRouter()


@router.get("", response_model=list[SignalSummary])
async def list_signal_weeks(
    workspace_id: uuid.UUID,
    ws_role: tuple[Workspace, str] = Depends(get_workspace_with_role),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(
            WeeklySignal.week_date,
            func.count(WeeklySignal.id).label("total_candidates"),
        )
        .where(WeeklySignal.workspace_id == workspace_id)
        .group_by(WeeklySignal.week_date)
        .order_by(WeeklySignal.week_date.desc())
    )
    rows = result.all()

    summaries = []
    for row in rows:
        # Count selected for this week
        sel_result = await db.execute(
            select(func.count(SelectionPick.id))
            .join(WeeklySelection, SelectionPick.selection_id == WeeklySelection.id)
            .where(
                WeeklySelection.workspace_id == workspace_id,
                WeeklySelection.week_date == row.week_date,
            )
        )
        total_selected = sel_result.scalar() or 0

        summaries.append(SignalSummary(
            week_date=row.week_date,
            total_candidates=row.total_candidates,
            total_selected=total_selected,
        ))
    return summaries


@router.get("/heatmap", response_model=HeatmapResponse)
async def get_heatmap(
    workspace_id: uuid.UUID,
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    ws_role: tuple[Workspace, str] = Depends(get_workspace_with_role),
    db: AsyncSession = Depends(get_db),
):
    # Get all signals with ticker info
    query = (
        select(WeeklySignal, Ticker.symbol, Ticker.name)
        .join(Ticker, WeeklySignal.ticker_id == Ticker.id)
        .where(WeeklySignal.workspace_id == workspace_id)
    )
    if start_date:
        query = query.where(WeeklySignal.week_date >= start_date)
    if end_date:
        query = query.where(WeeklySignal.week_date <= end_date)

    result = await db.execute(query)
    signals = result.all()

    # Get all selection picks
    sel_query = (
        select(SelectionPick.ticker_id, WeeklySelection.week_date)
        .join(WeeklySelection, SelectionPick.selection_id == WeeklySelection.id)
        .where(WeeklySelection.workspace_id == workspace_id)
    )
    if start_date:
        sel_query = sel_query.where(WeeklySelection.week_date >= start_date)
    if end_date:
        sel_query = sel_query.where(WeeklySelection.week_date <= end_date)

    sel_result = await db.execute(sel_query)
    selected_set = {(row.ticker_id, row.week_date) for row in sel_result.all()}

    # Build heatmap
    ticker_map: dict[str, dict] = {}  # symbol -> {name, selection_count}
    weeks_set = set()
    cells = []

    for signal, symbol, name in signals:
        if symbol not in ticker_map:
            ticker_map[symbol] = {"name": name, "selection_count": 0}
        weeks_set.add(signal.week_date)
        is_selected = (signal.ticker_id, signal.week_date) in selected_set
        if is_selected:
            ticker_map[symbol]["selection_count"] += 1
        cells.append(HeatmapCell(
            ticker=symbol,
            week_date=signal.week_date,
            in_universe=True,
            is_selected=is_selected,
        ))

    # Sort tickers: most selected first, then alphabetically
    sorted_tickers = sorted(
        ticker_map.keys(),
        key=lambda s: (-ticker_map[s]["selection_count"], s),
    )

    ticker_infos = [
        TickerInfo(symbol=s, name=ticker_map[s]["name"], selection_count=ticker_map[s]["selection_count"])
        for s in sorted_tickers
    ]

    return HeatmapResponse(
        tickers=ticker_infos,
        weeks=sorted(weeks_set),
        cells=cells,
    )


@router.get("/{week_date}", response_model=list[SignalDetail])
async def get_week_signals(
    workspace_id: uuid.UUID,
    week_date: date,
    ws_role: tuple[Workspace, str] = Depends(get_workspace_with_role),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(WeeklySignal, Ticker)
        .join(Ticker, WeeklySignal.ticker_id == Ticker.id)
        .where(
            WeeklySignal.workspace_id == workspace_id,
            WeeklySignal.week_date == week_date,
        )
        .order_by(Ticker.symbol)
    )

    # Get selected tickers for this week
    sel_result = await db.execute(
        select(SelectionPick.ticker_id)
        .join(WeeklySelection, SelectionPick.selection_id == WeeklySelection.id)
        .where(
            WeeklySelection.workspace_id == workspace_id,
            WeeklySelection.week_date == week_date,
        )
    )
    selected_ids = {row[0] for row in sel_result.all()}

    details = []
    for signal, ticker in result.all():
        details.append(SignalDetail(
            id=signal.id,
            ticker=ticker.symbol,
            ticker_name=ticker.name,
            week_date=signal.week_date,
            cagr_pot=signal.cagr_pot,
            mediana_retorno_l5y=signal.mediana_retorno_l5y,
            pct_3m_alcista_5y=signal.pct_3m_alcista_5y,
            mod1y_ev_ebit=signal.mod1y_ev_ebit,
            mod1y_ev_ebitda=signal.mod1y_ev_ebitda,
            mod1y_p_fcf=signal.mod1y_p_fcf,
            mod1y_per=signal.mod1y_per,
            growth_rev_est_pend=signal.growth_rev_est_pend,
            anal_rev_growth=signal.anal_rev_growth,
            perfil_compounder=signal.perfil_compounder,
            estado_perf_vs_ev=signal.estado_perf_vs_ev,
            pq_barata=signal.pq_barata,
            orden=signal.orden,
            status=signal.status,
            is_selected=signal.ticker_id in selected_ids,
        ))
    return details


@router.get("/{week_date}/{ticker_symbol}", response_model=DossierResponse)
async def get_signal_dossier(
    workspace_id: uuid.UUID,
    week_date: date,
    ticker_symbol: str,
    ws_role: tuple[Workspace, str] = Depends(get_workspace_with_role),
    db: AsyncSession = Depends(get_db),
):
    # Get ticker
    result = await db.execute(select(Ticker).where(Ticker.symbol == ticker_symbol.upper()))
    ticker = result.scalar_one_or_none()
    if not ticker:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticker not found")

    # Get signal
    result = await db.execute(
        select(WeeklySignal).where(
            WeeklySignal.workspace_id == workspace_id,
            WeeklySignal.ticker_id == ticker.id,
            WeeklySignal.week_date == week_date,
        )
    )
    signal = result.scalar_one_or_none()

    # Get dossier
    result = await db.execute(
        select(CompanyDossier)
        .join(WeeklySelection, CompanyDossier.selection_id == WeeklySelection.id)
        .where(
            WeeklySelection.workspace_id == workspace_id,
            WeeklySelection.week_date == week_date,
            CompanyDossier.ticker_id == ticker.id,
        )
    )
    dossier = result.scalar_one_or_none()

    # Get pick info
    result = await db.execute(
        select(SelectionPick)
        .join(WeeklySelection, SelectionPick.selection_id == WeeklySelection.id)
        .where(
            WeeklySelection.workspace_id == workspace_id,
            WeeklySelection.week_date == week_date,
            SelectionPick.ticker_id == ticker.id,
        )
    )
    pick = result.scalar_one_or_none()

    if not signal and not dossier:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No data for this ticker/week")

    signal_detail = None
    if signal:
        signal_detail = SignalDetail(
            id=signal.id,
            ticker=ticker.symbol,
            ticker_name=ticker.name,
            week_date=signal.week_date,
            cagr_pot=signal.cagr_pot,
            mediana_retorno_l5y=signal.mediana_retorno_l5y,
            pct_3m_alcista_5y=signal.pct_3m_alcista_5y,
            mod1y_ev_ebit=signal.mod1y_ev_ebit,
            mod1y_ev_ebitda=signal.mod1y_ev_ebitda,
            mod1y_p_fcf=signal.mod1y_p_fcf,
            mod1y_per=signal.mod1y_per,
            growth_rev_est_pend=signal.growth_rev_est_pend,
            anal_rev_growth=signal.anal_rev_growth,
            perfil_compounder=signal.perfil_compounder,
            estado_perf_vs_ev=signal.estado_perf_vs_ev,
            pq_barata=signal.pq_barata,
            orden=signal.orden,
            status=signal.status,
            is_selected=pick is not None,
        )

    return DossierResponse(
        ticker=ticker.symbol,
        week_date=week_date,
        growth_profile=dossier.growth_profile if dossier else None,
        margins_efficiency=dossier.margins_efficiency if dossier else None,
        financial_health=dossier.financial_health if dossier else None,
        relative_valuation=dossier.relative_valuation if dossier else None,
        management_quality=dossier.management_quality if dossier else None,
        main_risks=dossier.main_risks if dossier else None,
        key_opportunities=dossier.key_opportunities if dossier else None,
        general_conclusion=dossier.general_conclusion if dossier else None,
        justification=pick.justification if pick else None,
        role_activity=pick.role_activity if pick else None,
        signal=signal_detail,
    )
