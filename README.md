# trading

Finanz-Rechercheagent: durchsucht das Internet nach Anlagekandidaten (Aktien,
ETFs, Krypto) und bewertet sie nach vier Kriterien - Fundamentaldaten,
technische Indikatoren, News & Sentiment und qualitative Faktoren
(Geschaeftsmodell/Risiko) - zu einem gewichteten Gesamtscore.

Der Agent nutzt die Claude API mit dem serverseitigen `web_search`-Tool fuer
die Recherche und erzeugt einen Markdown-Report mit Ranking-Tabelle,
Einzelbewertungen und Quellenangaben.

## Setup

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...   # oder: ant auth login
```

## Nutzung

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
