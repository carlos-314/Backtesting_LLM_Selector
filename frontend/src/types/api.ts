export interface Workspace {
  id: string;
  name: string;
  slug: string;
  owner_id: string;
  created_at: string;
}

export interface UploadBatch {
  id: string;
  workspace_id: string;
  week_date: string;
  status: string;
  error_detail?: string;
  row_count?: number;
  warning_count: number;
  duplicate_count: number;
  created_at: string;
}

export interface HeatmapCell {
  ticker: string;
  week_date: string;
  in_universe: boolean;
  is_selected: boolean;
}

export interface TickerInfo {
  symbol: string;
  name?: string;
  selection_count: number;
}

export interface HeatmapData {
  tickers: TickerInfo[];
  weeks: string[];
  cells: HeatmapCell[];
}

export interface SignalSummary {
  week_date: string;
  total_candidates: number;
  total_selected: number;
}

export interface SignalDetail {
  id: string;
  ticker: string;
  ticker_name?: string;
  week_date: string;
  cagr_pot?: number;
  mediana_retorno_l5y?: number;
  pct_3m_alcista_5y?: number;
  mod1y_ev_ebit?: number;
  mod1y_ev_ebitda?: number;
  mod1y_p_fcf?: number;
  mod1y_per?: number;
  perfil_compounder?: string;
  estado_perf_vs_ev?: string;
  pq_barata?: string;
  orden?: string;
  status?: string;
  is_selected: boolean;
}

export interface DossierData {
  ticker: string;
  week_date: string;
  growth_profile?: string;
  margins_efficiency?: string;
  financial_health?: string;
  relative_valuation?: string;
  management_quality?: string;
  main_risks?: string;
  key_opportunities?: string;
  general_conclusion?: string;
  justification?: string;
  role_activity?: string;
  signal?: SignalDetail;
}

export interface BacktestRun {
  id: string;
  name?: string;
  status: string;
  start_date: string;
  end_date: string;
  initial_capital: number;
  commission_pct: number;
  slippage_bps: number;
  rebalance_mode: string;
  use_equal_weight_bench: boolean;
  use_random_bench: boolean;
  random_simulations: number;
  external_index_symbol?: string;
  created_at: string;
  completed_at?: string;
}

export interface BacktestMetrics {
  source: string;
  total_return?: number;
  cagr?: number;
  volatility?: number;
  sharpe_ratio?: number;
  max_drawdown?: number;
  sortino_ratio?: number;
  calmar_ratio?: number;
  win_rate?: number;
  turnover?: number;
  pct_random_beaten?: number;
  equity_curve?: Array<{ date: string; value: number }>;
}

export interface BacktestDetail {
  run: BacktestRun;
  metrics: BacktestMetrics[];
}

export interface Member {
  id: string;
  user_id: string;
  email: string;
  full_name: string;
  role: string;
}
