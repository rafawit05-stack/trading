# trading

Zwei Tools in diesem Repo:

1. **`finance_agent`** - LLM-Rechercheagent, der das Internet nach Anlagekandidaten
   durchsucht (Aktien, ETFs, Krypto) und sie frei nach vier Kriterien bewertet.
2. **`swing_trade`** - regelbasiertes Evaluation-Framework fuer eine vom Nutzer
   gelieferte Watchlist aus US-/DE-/EU-Aktien: harte Gates, Scoring pro Konzept
   und ein fertiger Risk-Plan (Entry/Stop/Targets/Positionsgroesse).

## finance_agent

Durchsucht das Internet nach Anlagekandidaten (Aktien, ETFs, Krypto) und
bewertet sie nach vier Kriterien - Fundamentaldaten, technische Indikatoren,
News & Sentiment und qualitative Faktoren (Geschaeftsmodell/Risiko) - zu
einem gewichteten Gesamtscore.

Der Agent nutzt die Claude API mit dem serverseitigen `web_search`-Tool fuer
die Recherche und erzeugt einen Markdown-Report mit Ranking-Tabelle,
Einzelbewertungen und Quellenangaben.

### Setup

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...   # oder: ant auth login
```

### Nutzung

```bash
python -m finance_agent "unterbewertete deutsche Tech-Aktien mit stabilem Cashflow"
```

Optionen:

- `--asset-class {stocks,etfs,crypto,mixed}` - Asset-Klasse einschraenken (Standard: `mixed`)
- `--count N` - Anzahl der zu bewertenden Kandidaten (Standard: 5)
- `--weight-fundamentals`, `--weight-technical`, `--weight-news`, `--weight-qualitative` - Gewichtung der vier Kriterien in Prozent (werden automatisch normalisiert)
- `--max-searches N` - maximale Anzahl an Websuchen
- `--output PFAD` - Zielpfad fuer den Markdown-Report (Standard: `reports/finanzreport_<timestamp>.md`)

Beispiel mit angepasster Gewichtung und Fokus auf ETFs:

```bash
python -m finance_agent "nachhaltige Schwellenlaender-ETFs" \
  --asset-class etfs --count 3 \
  --weight-fundamentals 40 --weight-technical 10 --weight-news 20 --weight-qualitative 30
```

Der Report wird als Markdown-Datei gespeichert und zusaetzlich auf stdout
ausgegeben. Alle Bewertungen basieren auf recherchierten, aber nicht
garantiert vollstaendigen oder fehlerfreien Informationen - kein Ersatz fuer
eine eigene Pruefung oder Anlageberatung.

## swing_trade

Implementiert das Swing-Trade Evaluation Framework (siehe
`.claude/skills/swing-trade-evaluation/SKILL.md` fuer die vollstaendige
Regelbeschreibung inkl. der dort dokumentierten Luecken/Korrekturen) als
auditierbaren, getesteten Code statt als freies LLM-Urteil:

- Harte Gates G1-G6 (Regime, Trend, relative Staerke, Liquiditaet,
  Ausschlusskriterien, R:R nach Kosten) - ein Kandidat, bei dem ein Gate nicht
  verifizierbar ist (UNKNOWN), landet nie in der bestaetigten Shortlist.
- Scoring pro Konzept (Trend, Momentum, Volumen, Volatilitaet, Pattern,
  Location, Fundamentaldaten, optional News/Sentiment) mit playbook-abhaengiger
  Logik fuer Breakout (A) und Pullback (B).
- Automatisch generierter Trade-Plan (Entry, Stop, Targets, Positionsgroesse,
  R:R nach Kommission/Slippage, Time-Stop, Invalidation).
- Portfolio-Hinweis bei Sektor-Klumpenrisiko.

**Analyse, keine Anlageberatung.** Die Gewichtung der Scoring-Faktoren ist
standardmaessig gleichgewichtet und explizit als Platzhalter markiert - das
Framework selbst verlangt, dass echte Gewichte aus einem Walk-Forward-Backtest
stammen, nicht aus Annahmen.

### Setup

```bash
pip install -r requirements.txt   # enthaelt bereits yfinance/pandas/numpy
```

### Nutzung

```bash
python -m swing_trade watchlist.example.csv
```

Die Watchlist ist eine CSV mit den Spalten `ticker,market,playbook,sector,
red_flag,earnings_is_thesis,sentiment_score,notes` (siehe
`watchlist.example.csv`). `market` ist `US` oder `EU`, `playbook` ist `A`
(Breakout) oder `B` (Pullback).

Wichtige Optionen:

- `--capital`, `--risk-pct`, `--risk-pct-a-plus` - Kapitalbasis und Risiko pro
  Trade (Standard 1%, 2% nur fuer automatisch erkannte A+-Setups)
- `--commission-bps`, `--slippage-bps` - Kosten fuer die R:R-Berechnung nach Kosten
- `--hold-sessions-max` - Time-Stop in Handelstagen
- `--weights "Trend qual.=2,Momentum=1,..."` - eigene (z.B. backgetestete)
  Gewichtung statt Gleichgewichtung
- `--data-source {yfinance,csv}` - Standardmaessig laedt das Tool Kursdaten live
  via `yfinance`; mit `--data-source csv --price-dir DIR` werden stattdessen
  eigene `<TICKER>.csv`- und `BENCHMARK_US.csv`/`BENCHMARK_EU.csv`-Dateien
  (Spalten `Date,Open,High,Low,Close,Volume`) genutzt - z.B. wenn Yahoo Finance
  in der eigenen Netzwerkumgebung nicht erreichbar ist.

### Tests

```bash
pip install -r requirements-dev.txt
pytest
```

Die Tests laufen komplett gegen synthetische Kursdaten (kein Netzwerkzugriff
noetig) und decken Indikatoren, Gates, Scoring und den Trade-Plan ab.
