"""Marktabhaengige Schwellenwerte aus dem Swing-Trade Evaluation Framework.

Waehrung: US-Werte in USD, EU-Werte in EUR - es findet keine Waehrungsumrechnung
statt; Kursdaten werden in der jeweiligen Heimatwaehrung des Tickers erwartet.
"""

from __future__ import annotations

LIQUIDITY = {
    "US": {
        "min_avg_volume": 750_000,
        "min_avg_turnover": 10_000_000,
        "max_spread_pct": 0.15,
        "min_market_cap_screen": 1_000_000_000,
        "min_market_cap_floor": 300_000_000,
    },
    "EU": {
        "min_avg_volume": 100_000,
        "min_avg_turnover": 5_000_000,
        "max_spread_pct": 0.30,
        "min_market_cap_screen": 500_000_000,
        "min_market_cap_floor": 200_000_000,
    },
}

# ATR%-Band: Standardband je Markt, EU zusaetzlich verengt fuer "large caps".
# Der Quelltext nennt keinen exakten Large-Cap-Schwellenwert fuer diese Verengung -
# hier wird eine gaengige Konvention (>= 5 Mrd. EUR Marktkapitalisierung) angenommen.
ATR_BAND_DEFAULT = {"US": (2.0, 6.0), "EU": (2.0, 6.0)}
ATR_BAND_LARGE_EU = (1.5, 5.0)
LARGE_EU_MARKET_CAP = 5_000_000_000

RISK_PER_TRADE_DEFAULT_PCT = 1.0
RISK_PER_TRADE_A_PLUS_PCT = 2.0
MIN_RR_AFTER_COSTS = 2.0
STOP_ATR_MULTIPLE = 1.5
NOISE_FLOOR_ATR_MULTIPLE = 0.5  # Mindestabstand Entry->Stop, um Rauschen zu ueberstehen
A_PLUS_MIN_WEIGHTED_SCORE = 8.5

# T1 als rohes 2R-Ziel macht G6 (R:R >= 2.0 NACH Kosten) mathematisch unerreichbar:
# Kosten werden vom Gewinn abgezogen UND zum Risiko addiert, daher liegt ein exakt
# auf 2.0 kalibriertes rohes Ziel nach Kosten immer strikt unter 2.0, unabhaengig vom
# Kandidaten. Siehe SKILL.md "Gaps found" fuer die Herleitung. Fix: T1/T2 bekommen
# einen Kostenpuffer oberhalb der reinen 2R/3R-Vorgabe aus dem Framework-Text.
TARGET_R_MULTIPLE_T1 = 2.3
TARGET_R_MULTIPLE_T2 = 3.3
