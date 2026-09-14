"""Kernlogik des Finanz-Rechercheagenten.

Nutzt die Claude Messages API mit dem serverseitigen ``web_search``-Tool, um
Anlagekandidaten (Aktien, ETFs, Krypto) zu recherchieren und nach vier
Kriterien zu bewerten: Fundamentaldaten, technische Indikatoren, News &
Sentiment sowie qualitative Faktoren (Geschaeftsmodell/Risiko).
"""

from __future__ import annotations

import dataclasses
import datetime as dt

import anthropic

DEFAULT_MODEL = "claude-opus-5"
DEFAULT_MAX_SEARCHES = 15
DEFAULT_MAX_TOKENS = 32000
MAX_PAUSE_RESTARTS = 3

CRITERIA = ("fundamentaldaten", "technik", "news_sentiment", "qualitativ")

CRITERIA_LABELS = {
    "fundamentaldaten": "Fundamentaldaten",
    "technik": "Technische Indikatoren",
    "news_sentiment": "News & Sentiment",
    "qualitativ": "Qualitativ (Geschaeftsmodell/Risiko)",
}

ASSET_CLASS_LABELS = {
    "stocks": "Einzelaktien",
    "etfs": "ETFs/Fonds",
    "crypto": "Kryptowaehrungen",
    "mixed": "Aktien, ETFs und/oder Kryptowaehrungen (je nach Anfrage)",
}


@dataclasses.dataclass
class Source:
    url: str
    title: str


@dataclasses.dataclass
class AgentResult:
    report_markdown: str
    sources: list[Source]
    search_count: int
    model: str


def build_system_prompt(asset_class: str, weights: dict[str, float], count: int) -> str:
    weight_lines = "\n".join(
        f"- {CRITERIA_LABELS[k]}: {weights[k] * 100:.0f}%" for k in CRITERIA
    )
    return f"""Du bist ein sorgfaeltiger Finanz-Rechercheagent. Deine Aufgabe ist es, mit \
dem web_search-Tool aktuelle, oeffentlich verfuegbare Informationen aus dem Internet \
zu recherchieren, um {ASSET_CLASS_LABELS[asset_class]} zu finden und zu bewerten, \
die zur Anfrage des Nutzers passen.

Vorgehen:
1. Recherchiere passende Kandidaten zur Anfrage (z.B. ueber Marktuebersichten, Screener-Ergebnisse, Finanznews).
2. Waehle die {count} vielversprechendsten Kandidaten aus.
3. Recherchiere fuer jeden Kandidaten gezielt aktuelle Daten zu allen vier Kriterien unten.
4. Bewerte jeden Kandidaten pro Kriterium mit einer Punktzahl von 1 (sehr schwach) bis 10 (sehr stark) \
mit kurzer Begruendung, und berechne daraus einen gewichteten Gesamtscore (0-10).

Bewertungskriterien und Gewichtung:
{weight_lines}

- Fundamentaldaten: z.B. KGV, Umsatz-/Gewinnwachstum, Verschuldungsgrad, Eigenkapitalrendite, Dividendenrendite \
(bei ETFs: TER, Diversifikation, Tracking-Differenz; bei Krypto: Tokenomics, Liquiditaet, On-Chain-Kennzahlen).
- Technische Indikatoren: Kurstrend, gleitende Durchschnitte, Momentum, Volatilitaet.
- News & Sentiment: aktuelle Nachrichtenlage, Analystenmeinungen, allgemeine Marktstimmung der letzten Wochen.
- Qualitativ: Geschaeftsmodell, Wettbewerbsvorteile, Managementqualitaet, erkennbare Risiken.

Nutze das web_search-Tool mehrfach und gezielt (mehrere praezise Suchanfragen statt einer sehr allgemeinen). \
Stuetze jede Kennzahl und Einschaetzung auf tatsaechlich recherchierte, aktuelle Informationen - erfinde keine \
Zahlen. Wenn du zu einem Kandidaten keine verlaessliche Information findest, sage das explizit statt zu raten.

Gib die Antwort ausschliesslich als Markdown-Report in deutscher Sprache in folgender Struktur aus:

1. Ueberschrift und ein bis zwei Saetze Zusammenfassung der Anfrage.
2. Eine Ranking-Tabelle aller Kandidaten sortiert nach Gesamtscore (Spalten: Rang, Name/Ticker, \
Fundamentaldaten, Technik, News & Sentiment, Qualitativ, Gesamtscore).
3. Fuer jeden Kandidaten einen eigenen Abschnitt mit den vier Einzelbewertungen inkl. kurzer Begruendung \
und den wichtigsten recherchierten Fakten (mit Quellenangabe als Linktext).
4. Einen abschliessenden Hinweis, dass dies keine Anlageberatung ist und eine eigene Pruefung erforderlich bleibt.

Formatiere Quellenverweise inline als Markdown-Links, z.B. [Quelle](https://...)."""


def build_user_prompt(query: str, asset_class: str, count: int) -> str:
    scope = ASSET_CLASS_LABELS[asset_class]
    return (
        f"Suche und bewerte {count} {scope}, die zu folgendem Anlagefokus passen:\n\n"
        f"{query}\n\n"
        f"Heutiges Datum: {dt.date.today().isoformat()}."
    )


def _run_with_pause_handling(
    client: anthropic.Anthropic,
    model: str,
    system: str,
    user_content: str,
    tools: list[dict],
    max_tokens: int,
):
    messages = [{"role": "user", "content": user_content}]
    restarts = 0
    while True:
        with client.messages.stream(
            model=model,
            max_tokens=max_tokens,
            system=system,
            tools=tools,
            thinking={"type": "adaptive"},
            output_config={"effort": "high"},
            messages=messages,
        ) as stream:
            final = stream.get_final_message()

        if final.stop_reason != "pause_turn":
            return final

        restarts += 1
        if restarts > MAX_PAUSE_RESTARTS:
            raise RuntimeError(
                "Die Recherche wurde mehrfach unterbrochen (pause_turn) und konnte "
                "nicht abgeschlossen werden."
            )
        messages = [
            {"role": "user", "content": user_content},
            {"role": "assistant", "content": final.content},
        ]


def _extract_report(final) -> tuple[str, list[Source], int]:
    text_parts = []
    sources: dict[str, str] = {}
    search_count = 0

    for block in final.content:
        if block.type == "text":
            text_parts.append(block.text)
        elif block.type == "server_tool_use" and block.name == "web_search":
            search_count += 1
        elif block.type == "web_search_tool_result":
            content = block.content
            if isinstance(content, list):
                for result in content:
                    if getattr(result, "type", None) == "web_search_result":
                        sources[result.url] = result.title or result.url

    report_markdown = "\n".join(text_parts).strip()
    source_list = [Source(url=u, title=t) for u, t in sources.items()]
    return report_markdown, source_list, search_count


def research_and_evaluate(
    query: str,
    asset_class: str = "mixed",
    weights: dict[str, float] | None = None,
    count: int = 5,
    max_searches: int = DEFAULT_MAX_SEARCHES,
    model: str = DEFAULT_MODEL,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> AgentResult:
    if weights is None:
        weights = {k: 1 / len(CRITERIA) for k in CRITERIA}

    client = anthropic.Anthropic()
    system = build_system_prompt(asset_class, weights, count)
    user_content = build_user_prompt(query, asset_class, count)
    tools = [
        {
            "type": "web_search_20260209",
            "name": "web_search",
            "max_uses": max_searches,
        }
    ]

    final = _run_with_pause_handling(client, model, system, user_content, tools, max_tokens)
    report_markdown, sources, search_count = _extract_report(final)

    if not report_markdown:
        raise RuntimeError(
            f"Keine Textantwort erhalten (stop_reason={final.stop_reason!r})."
        )

    return AgentResult(
        report_markdown=report_markdown,
        sources=sources,
        search_count=search_count,
        model=final.model,
    )
