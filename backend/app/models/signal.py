import uuid
from datetime import date

from sqlalchemy import String, Integer, Date, Text, Numeric, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class WeeklySignal(Base):
    __tablename__ = "weekly_signals"
    __table_args__ = (UniqueConstraint("workspace_id", "ticker_id", "week_date"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    batch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("upload_batches.id", ondelete="CASCADE")
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    ticker_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tickers.id"), index=True)
    week_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    # Numeric metrics (xlsx cols 4-17)
    cagr_pot: Mapped[float | None] = mapped_column(Numeric(10, 4))
    mediana_retorno_l5y: Mapped[float | None] = mapped_column(Numeric(10, 4))
    pct_3m_alcista_5y: Mapped[float | None] = mapped_column(Numeric(10, 4))
    mod1y_ev_ebit: Mapped[float | None] = mapped_column(Numeric(10, 4))
    mod1y_ev_ebitda: Mapped[float | None] = mapped_column(Numeric(10, 4))
    mod1y_p_fcf: Mapped[float | None] = mapped_column(Numeric(10, 4))
    mod1y_per: Mapped[float | None] = mapped_column(Numeric(10, 4))
    growth_rev_est_pend: Mapped[str | None] = mapped_column(String(50))
    anal_rev_growth: Mapped[float | None] = mapped_column(Numeric(10, 4))
    gross_margin_pend: Mapped[str | None] = mapped_column(String(50))
    net_income_pend: Mapped[str | None] = mapped_column(String(50))
    annual_pct_buyback_3y: Mapped[float | None] = mapped_column(Numeric(10, 4))
    dividend_yield_3y: Mapped[float | None] = mapped_column(Numeric(10, 4))
    net_debt_ebitda_1y: Mapped[float | None] = mapped_column(Numeric(10, 4))

    # Text classifications (xlsx cols 18-21)
    pq_barata: Mapped[str | None] = mapped_column(Text)
    orden: Mapped[str | None] = mapped_column(Text)
    estado_perf_vs_ev: Mapped[str | None] = mapped_column(String(200))
    perfil_compounder: Mapped[str | None] = mapped_column(String(50))

    # JSON analysis columns (xlsx cols 22-36)
    ai_directiva: Mapped[dict | None] = mapped_column(JSONB)
    valores_crecimiento: Mapped[dict | None] = mapped_column(JSONB)
    antiguedad_directiva: Mapped[str | None] = mapped_column(Text)
    caida_acciones: Mapped[str | None] = mapped_column(Text)
    calidad_directiva: Mapped[dict | None] = mapped_column(JSONB)
    cortos_motivo: Mapped[str | None] = mapped_column(Text)
    evo_market_share: Mapped[str | None] = mapped_column(Text)
    fijacion_precios: Mapped[dict | None] = mapped_column(JSONB)
    guidance_search: Mapped[dict | None] = mapped_column(JSONB)
    potencial_fraude: Mapped[dict | None] = mapped_column(JSONB)
    risk_news_list: Mapped[str | None] = mapped_column(Text)
    risk_transcript_list: Mapped[str | None] = mapped_column(Text)
    sensibilidad_macro: Mapped[dict | None] = mapped_column(JSONB)
    subida_acciones: Mapped[str | None] = mapped_column(Text)
    customer_concentration_risk: Mapped[str | None] = mapped_column(Text)

    # Status
    status: Mapped[str | None] = mapped_column(String(20))


class WeeklySelection(Base):
    __tablename__ = "weekly_selections"
    __table_args__ = (UniqueConstraint("workspace_id", "week_date"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    batch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("upload_batches.id", ondelete="CASCADE")
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    week_date: Mapped[date] = mapped_column(Date, nullable=False)
    model_phase1: Mapped[str | None] = mapped_column(String(50))
    model_phases234: Mapped[str | None] = mapped_column(String(50))
    total_analyzed: Mapped[int | None] = mapped_column(Integer)
    executive_summary: Mapped[str | None] = mapped_column(Text)
    alerts: Mapped[str | None] = mapped_column(Text)
    diversification: Mapped[str | None] = mapped_column(Text)
    final_considerations: Mapped[str | None] = mapped_column(Text)

    picks = relationship("SelectionPick", back_populates="selection", cascade="all, delete-orphan")
    dossiers = relationship("CompanyDossier", back_populates="selection", cascade="all, delete-orphan")


class SelectionPick(Base):
    __tablename__ = "selection_picks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    selection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("weekly_selections.id", ondelete="CASCADE")
    )
    ticker_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tickers.id"))
    rank: Mapped[int] = mapped_column(Integer)
    role_activity: Mapped[str | None] = mapped_column(String(255))
    justification: Mapped[str | None] = mapped_column(Text)

    selection = relationship("WeeklySelection", back_populates="picks")


class CompanyDossier(Base):
    __tablename__ = "company_dossiers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    selection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("weekly_selections.id", ondelete="CASCADE")
    )
    ticker_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tickers.id"))
    dossier_order: Mapped[int] = mapped_column(Integer)
    growth_profile: Mapped[str | None] = mapped_column(Text)
    margins_efficiency: Mapped[str | None] = mapped_column(Text)
    financial_health: Mapped[str | None] = mapped_column(Text)
    relative_valuation: Mapped[str | None] = mapped_column(Text)
    management_quality: Mapped[str | None] = mapped_column(Text)
    main_risks: Mapped[str | None] = mapped_column(Text)
    key_opportunities: Mapped[str | None] = mapped_column(Text)
    general_conclusion: Mapped[str | None] = mapped_column(Text)

    selection = relationship("WeeklySelection", back_populates="dossiers")
