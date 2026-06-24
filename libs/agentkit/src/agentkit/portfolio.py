"""
Canonical synthetic portfolio — the single source of truth for every surface
(financial agent, orchestrator REST API, web + mobile dashboards).

Headline figures are authored once; the pure metrics functions in
agentkit.finance recompute AUM / TWR / volatility / Sharpe / IRR from these
inputs so the numbers are genuinely *computed* and unit-testable.
"""

from __future__ import annotations

import math
from datetime import date
from decimal import Decimal
from typing import Any

from agentkit.finance.metrics import (
    CashflowRow,
    DealSnapshot,
    compute_portfolio_metrics,
)

# ── Canonical inputs ────────────────────────────────────────────────────────

_TARGET_AUM = Decimal("20400000")  # $20.4M assets under management
_TARGET_COST_BASIS = Decimal("12550000")  # AUM − cost = $7.85M total profit
NUM_DEALS = 48
INCEPTION = date(2011, 8, 1)  # ≈14.9y holding period → 7.14% annualized at 178.65% TWR
_RISK_FREE = 0.0  # demo measures excess return over a ~0% cash rate

# One aggregate snapshot drives AUM + profit exactly (active book = whole book).
_SEED_DEALS: list[DealSnapshot] = [
    DealSnapshot(_TARGET_AUM, _TARGET_COST_BASIS, _TARGET_AUM, "active"),
]


def _build_monthly_returns() -> list[float]:
    """
    Deterministic monthly HPR series calibrated so the metrics library yields:
      • ITD TWR            ≈ 178.65%   (cumulative product of (1+r) ≈ 2.7865)
      • annual volatility  ≈ 12.27%    (monthly std-dev ≈ 3.53%)
    """
    n = 178  # ~14.8 years of monthly observations
    amp = 0.03532  # ±3.532% monthly swing → ≈12.27% annualized volatility
    target = 2.7865  # 1 + 1.7865 (ITD TWR)
    per_pair = target ** (1.0 / (n / 2))
    drift = math.sqrt(per_pair + amp * amp) - 1.0
    series = [drift + amp if i % 2 == 0 else drift - amp for i in range(n)]
    prod = 1.0
    for r in series:
        prod *= 1.0 + r
    series[0] = (1.0 + series[0]) * (target / prod) - 1.0
    return series


_SEED_MONTHLY_RETURNS: list[float] = _build_monthly_returns()

# Capital calls + a closing NAV distribution, calibrated to IRR ≈ 8%.
_SEED_CASHFLOWS: list[CashflowRow] = [
    CashflowRow(date(2011, 8, 1), 3_300_000.0),
    CashflowRow(date(2014, 1, 1), 2_100_000.0),
    CashflowRow(date(2017, 6, 1), 1_300_000.0),
    CashflowRow(date(2020, 3, 1), 800_000.0),
    CashflowRow(date(2026, 6, 1), -20_400_000.0),
]

# Geography allocation (by NAV %) — sums to 100.
GEO: dict[str, float] = {
    "Asia": 37.0,
    "North America": 35.0,
    "Global": 16.0,
    "Europe": 8.0,
    "Middle East": 4.0,
}

# Sector allocation (by NAV %) — sums to 100.
SECTOR: dict[str, float] = {
    "Real Estate": 45.0,
    "Private Equity": 35.0,
    "Equities": 15.0,
    "Credit": 5.0,
}

# Top deals by MOIC (fictional holdings).
TOP_DEALS: list[dict[str, Any]] = [
    {"name": "Aurora Brands", "moic": 1.55, "asset_class": "PE", "status": "exited"},
    {"name": "Project Summit", "moic": 1.52, "asset_class": "PE", "status": "exited"},
    {"name": "Project Delta", "moic": 1.47, "asset_class": "PE", "status": "active"},
    {"name": "Singapore Grade-A Office", "moic": 1.42, "asset_class": "RE", "status": "active"},
    {"name": "Metro Class-A Office Tower", "moic": 1.29, "asset_class": "RE", "status": "active"},
    {"name": "Zenith Capital", "moic": 1.21, "asset_class": "PE", "status": "active"},
]

# Representative holdings for the portfolio table (name, sector, geo, $M AUM, TWR%).
DEALS: list[dict[str, Any]] = [
    {
        "name": "Aurora Brands",
        "sector": "Private Equity",
        "geo": "North America",
        "status": "Exited",
        "aum": 0.78,
        "twr": 55.0,
    },
    {
        "name": "Project Summit",
        "sector": "Private Equity",
        "geo": "North America",
        "status": "Exited",
        "aum": 0.61,
        "twr": 52.0,
    },
    {
        "name": "Project Delta",
        "sector": "Private Equity",
        "geo": "Asia",
        "status": "Active",
        "aum": 0.59,
        "twr": 47.0,
    },
    {
        "name": "Singapore Grade-A Office",
        "sector": "Real Estate",
        "geo": "Asia",
        "status": "Active",
        "aum": 1.08,
        "twr": 42.0,
    },
    {
        "name": "Metro Class-A Office Tower",
        "sector": "Real Estate",
        "geo": "North America",
        "status": "Active",
        "aum": 1.10,
        "twr": 29.0,
    },
    {
        "name": "Helios Media",
        "sector": "Private Equity",
        "geo": "Asia",
        "status": "Active",
        "aum": 0.69,
        "twr": 44.0,
    },
    {
        "name": "Global Infrastructure Fund",
        "sector": "Real Estate",
        "geo": "Global",
        "status": "Active",
        "aum": 0.62,
        "twr": 31.0,
    },
    {
        "name": "Nordic Clean Tech",
        "sector": "Private Equity",
        "geo": "Europe",
        "status": "Active",
        "aum": 0.24,
        "twr": 24.0,
    },
    {
        "name": "Zenith Capital",
        "sector": "Private Equity",
        "geo": "North America",
        "status": "Active",
        "aum": 0.45,
        "twr": 21.0,
        "vintage": 2019,
        "moic": 1.21,
    },
]


def get_metrics() -> dict[str, Any]:
    """Compute the canonical portfolio metrics."""
    m = compute_portfolio_metrics(
        _SEED_DEALS,
        _SEED_MONTHLY_RETURNS,
        _SEED_CASHFLOWS,
        INCEPTION,
        risk_free=_RISK_FREE,
    )
    return {
        "aum": float(m.aum),
        "aum_fmt": f"${m.aum / 1_000_000:.1f}M",
        "twr_pct": m.twr_pct,
        "annualized_pct": m.annualized_pct,
        "irr_pct": m.irr_pct,
        "sharpe": m.sharpe,
        "volatility_pct": m.volatility,
        "total_profit": float(m.total_profit),
        "profit_fmt": f"${m.total_profit / 1_000_000:.2f}M",
        "years": m.years,
        "num_deals": NUM_DEALS,
        "num_active": NUM_DEALS - 6,
    }
