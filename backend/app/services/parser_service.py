import io
import json
import re
from datetime import date

import openpyxl
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.signal import WeeklySignal, WeeklySelection, SelectionPick, CompanyDossier
from app.models.ticker import Ticker

# Column index -> (field_name, type)
# Based on xlsx analysis: 38 columns (A-AL)
XLSX_NUMERIC_COLS = {
    4: "cagr_pot",
    5: "mediana_retorno_l5y",
    6: "pct_3m_alcista_5y",
    7: "mod1y_ev_ebit",
    8: "mod1y_ev_ebitda",
    9: "mod1y_p_fcf",
    10: "mod1y_per",
    # 11: growth_rev_est_pend (string)
    12: "anal_rev_growth",
    # 13: gross_margin_pend (string)
    # 14: net_income_pend (string)
    15: "annual_pct_buyback_3y",
    16: "dividend_yield_3y",
    17: "net_debt_ebitda_1y",
}

XLSX_STRING_COLS = {
    11: "growth_rev_est_pend",
    13: "gross_margin_pend",
    14: "net_income_pend",
    18: "pq_barata",
    19: "orden",
    20: "estado_perf_vs_ev",
    21: "perfil_compounder",
}

# JSON/text analysis columns (22-36)
XLSX_JSON_COLS = {
    22: "ai_directiva",
    23: "valores_crecimiento",
    24: "antiguedad_directiva",
    25: "caida_acciones",
    26: "calidad_directiva",
    27: "cortos_motivo",
    28: "evo_market_share",
    29: "fijacion_precios",
    30: "guidance_search",
    31: "potencial_fraude",
    32: "risk_news_list",
    33: "risk_transcript_list",
    34: "sensibilidad_macro",
    35: "subida_acciones",
    36: "customer_concentration_risk",
}

# Columns that should be stored as JSONB (attempt json.loads)
JSONB_FIELDS = {
    "ai_directiva", "valores_crecimiento", "calidad_directiva",
    "fijacion_precios", "guidance_search", "potencial_fraude", "sensibilidad_macro",
}


def _safe_float(val) -> float | None:
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _safe_json(val, field_name: str):
    """Try to parse as JSON. Returns dict if JSONB field, string otherwise."""
    if val is None:
        return None
    s = str(val).strip()
    if not s:
        return None
    if field_name in JSONB_FIELDS:
        try:
            return json.loads(s)
        except (json.JSONDecodeError, ValueError):
            return None  # Store None if invalid JSON for JSONB columns
    return s


def get_or_create_ticker(db: Session, symbol: str, name: str | None = None) -> Ticker:
    result = db.execute(select(Ticker).where(Ticker.symbol == symbol.upper()))
    ticker = result.scalar_one_or_none()
    if not ticker:
        try:
            ticker = Ticker(symbol=symbol.upper(), name=name)
            db.add(ticker)
            db.flush()
        except Exception:
            db.rollback()
            result = db.execute(select(Ticker).where(Ticker.symbol == symbol.upper()))
            ticker = result.scalar_one_or_none()
    elif name and not ticker.name:
        ticker.name = name
    return ticker


def parse_xlsx(db: Session, xlsx_data: bytes, workspace_id, batch_id, week_date: date) -> tuple[int, list[str]]:
    """Parse xlsx file and create WeeklySignal records. Returns (row_count, warnings)."""
    wb = openpyxl.load_workbook(io.BytesIO(xlsx_data), read_only=True, data_only=True)
    ws = wb.active
    warnings = []
    rows_created = 0

    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return 0, ["Empty spreadsheet"]

    header = rows[0]
    data_rows = rows[1:]

    for i, row in enumerate(data_rows):
        if not row or not row[0]:
            continue

        symbol = str(row[0]).strip().upper()
        name = str(row[2]).strip() if row[2] else None

        ticker = get_or_create_ticker(db, symbol, name)

        # Check for duplicate
        existing = db.execute(
            select(WeeklySignal).where(
                WeeklySignal.workspace_id == workspace_id,
                WeeklySignal.ticker_id == ticker.id,
                WeeklySignal.week_date == week_date,
            )
        ).scalar_one_or_none()

        if existing:
            warnings.append(f"Duplicate: {symbol} for week {week_date}, skipping")
            continue

        # Build signal kwargs
        kwargs = {
            "batch_id": batch_id,
            "workspace_id": workspace_id,
            "ticker_id": ticker.id,
            "week_date": week_date,
        }

        # Numeric columns
        for col_idx, field in XLSX_NUMERIC_COLS.items():
            kwargs[field] = _safe_float(row[col_idx]) if col_idx < len(row) else None

        # String columns
        for col_idx, field in XLSX_STRING_COLS.items():
            kwargs[field] = str(row[col_idx]).strip() if col_idx < len(row) and row[col_idx] else None

        # JSON/text columns
        for col_idx, field in XLSX_JSON_COLS.items():
            kwargs[field] = _safe_json(row[col_idx] if col_idx < len(row) else None, field)

        # Status column (37)
        kwargs["status"] = str(row[37]).strip() if len(row) > 37 and row[37] else None

        signal = WeeklySignal(**kwargs)
        db.add(signal)
        rows_created += 1

    wb.close()
    return rows_created, warnings


def parse_txt(db: Session, txt_data: bytes, workspace_id, batch_id, week_date: date) -> list[str]:
    """Parse txt file and create WeeklySelection, SelectionPick, CompanyDossier records. Returns warnings."""
    text = txt_data.decode("utf-8", errors="replace")
    warnings = []

    # Parse header
    model_phase1 = None
    model_phases234 = None
    total_analyzed = None

    m = re.search(r"Modelo Fase 1:\s*(.+)", text)
    if m:
        model_phase1 = m.group(1).strip()
    m = re.search(r"Modelo Fases 2-3-4:\s*(.+)", text)
    if m:
        model_phases234 = m.group(1).strip()
    m = re.search(r"Total de empresas analizadas:\s*(\d+)", text)
    if m:
        total_analyzed = int(m.group(1))

    # Split into main sections
    # Section 1: SELECCION FINAL DE CARTERA
    # Section 2: DOSSIERS INDIVIDUALES - FASE 1
    dossier_split = re.split(r"={10,}\s*\nDOSSIERS INDIVIDUALES", text, maxsplit=1)
    selection_section = dossier_split[0] if dossier_split else text
    dossier_section = dossier_split[1] if len(dossier_split) > 1 else ""

    # Parse selection sections
    executive_summary = _extract_section(selection_section, "1. Resumen Ejecutivo", "2.")
    alerts = _extract_section(selection_section, "2. Alertas", "3.")
    diversification = _extract_section(selection_section, "6. An.lisis de Diversificaci.n", "7.")
    final_considerations = _extract_section(selection_section, "7. Consideraciones Finales", None)

    selection = WeeklySelection(
        batch_id=batch_id,
        workspace_id=workspace_id,
        week_date=week_date,
        model_phase1=model_phase1,
        model_phases234=model_phases234,
        total_analyzed=total_analyzed,
        executive_summary=executive_summary,
        alerts=alerts,
        diversification=diversification,
        final_considerations=final_considerations,
    )
    db.add(selection)
    db.flush()

    # Parse selection picks (section 3)
    picks_text = _extract_section(selection_section, "3. Selecci.n Final", "4.")
    if picks_text:
        # Match both formats:
        #   • CSU – Constellation Software Inc | Rol/Activity: M&A Roll-up / Software
        #   • CSU – Constellation Software Inc | M&A Roll-up / Software
        pick_pattern = re.compile(
            r"[•\-]\s*(\w+)\s*[\u2013\u2014\-]+\s*(.+?)\s*\|\s*(?:Rol/Activity:\s*)?(.+)",
        )
        seen_tickers = set()
        rank = 0
        for m in pick_pattern.finditer(picks_text):
            symbol = m.group(1).strip().upper()
            role_activity = m.group(3).strip()

            if symbol in seen_tickers:
                warnings.append(f"Duplicate pick: {symbol}")
                continue
            seen_tickers.add(symbol)

            ticker = get_or_create_ticker(db, symbol)
            rank += 1

            # Try to find justification in section 4
            justification = _extract_justification(selection_section, symbol)

            pick = SelectionPick(
                selection_id=selection.id,
                ticker_id=ticker.id,
                rank=rank,
                role_activity=role_activity,
                justification=justification,
            )
            db.add(pick)

    # Parse dossiers
    if dossier_section:
        _parse_dossiers(db, dossier_section, selection.id, warnings)

    return warnings


def _extract_section(text: str, start_marker: str, end_marker: str | None) -> str | None:
    pattern = re.compile(re.escape(start_marker).replace(r"\.", "."), re.IGNORECASE)
    m = pattern.search(text)
    if not m:
        return None
    start = m.end()
    if end_marker:
        end_pattern = re.compile(re.escape(end_marker).replace(r"\.", "."), re.IGNORECASE)
        m2 = end_pattern.search(text, start)
        end = m2.start() if m2 else len(text)
    else:
        end = len(text)
    return text[start:end].strip()


def _extract_justification(text: str, symbol: str) -> str | None:
    # Look for pattern like "• Company Name (SYMBOL): justification text"
    pattern = re.compile(
        rf"[•\-]\s*.+?\({symbol}\):\s*(.+?)(?=\n[•\-]|\n\n\d+\.|\Z)",
        re.DOTALL | re.IGNORECASE,
    )
    m = pattern.search(text)
    return m.group(1).strip() if m else None


def _parse_dossiers(db: Session, dossier_text: str, selection_id, warnings: list[str]):
    # Split by dossier separator
    dossier_blocks = re.split(r"\u2500{10,}", dossier_text)

    order = 0
    for block in dossier_blocks:
        # Find ticker header: #N SYMBOL — Company Name
        header_match = re.match(
            r"\s*#(\d+)\s+(\w+)\s*[\u2014\u2013\-]+\s*(.+)",
            block.strip(),
        )
        if not header_match:
            continue

        order += 1
        symbol = header_match.group(2).strip().upper()
        ticker = get_or_create_ticker(db, symbol)

        # Extract 8 dimensions
        dimensions = {
            "growth_profile": _extract_dimension(block, "Perfil de Crecimiento"),
            "margins_efficiency": _extract_dimension(block, "M.rgenes y Eficiencia"),
            "financial_health": _extract_dimension(block, "Salud Financiera"),
            "relative_valuation": _extract_dimension(block, "Valoraci.n Relativa"),
            "management_quality": _extract_dimension(block, "Calidad de Gesti.n"),
            "main_risks": _extract_dimension(block, "Riesgos Principales"),
            "key_opportunities": _extract_dimension(block, "Oportunidades Clave"),
            "general_conclusion": _extract_dimension(block, "Conclusi.n General"),
        }

        dossier = CompanyDossier(
            selection_id=selection_id,
            ticker_id=ticker.id,
            dossier_order=order,
            **dimensions,
        )
        db.add(dossier)


def _extract_dimension(text: str, dimension_name: str) -> str | None:
    # Match **Dimension Name**: content or - **Dimension Name**: content
    pattern = re.compile(
        rf"\*\*{dimension_name}\*\*[:\s]*(.+?)(?=\n\s*[-•]?\s*\*\*|\Z)",
        re.DOTALL | re.IGNORECASE,
    )
    m = pattern.search(text)
    if m:
        return m.group(1).strip()
    return None
