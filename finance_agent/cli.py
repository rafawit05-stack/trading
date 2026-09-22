"""Kommandozeilen-Interface fuer den Finanz-Rechercheagenten."""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

import anthropic

from .agent import CRITERIA, DEFAULT_MAX_SEARCHES, DEFAULT_MODEL, research_and_evaluate

REPORTS_DIR = Path("reports")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="finance-agent",
        description=(
            "Finanz-Rechercheagent: durchsucht das Internet nach Aktien, ETFs "
            "oder Krypto-Assets und bewertet sie nach Fundamentaldaten, "
            "technischen Indikatoren, News/Sentiment und qualitativen Kriterien."
        ),
    )
    parser.add_argument(
        "query",
        help=(
            "Anlagefokus in Freitext, z.B. 'unterbewertete deutsche "
            "Tech-Aktien' oder 'nachhaltige Schwellenlaender-ETFs'"
        ),
    )
    parser.add_argument(
        "--asset-class",
        choices=["stocks", "etfs", "crypto", "mixed"],
        default="mixed",
        help="Asset-Klasse, auf die die Suche eingeschraenkt wird (Standard: mixed)",
    )
    parser.add_argument(
        "--count", type=int, default=5, help="Anzahl der zu bewertenden Kandidaten (Standard: 5)"
    )
    parser.add_argument(
        "--weight-fundamentals", type=float, default=25.0, help="Gewichtung Fundamentaldaten in %%"
    )
    parser.add_argument(
        "--weight-technical", type=float, default=25.0, help="Gewichtung technische Indikatoren in %%"
    )
    parser.add_argument(
        "--weight-news", type=float, default=25.0, help="Gewichtung News & Sentiment in %%"
    )
    parser.add_argument(
        "--weight-qualitative", type=float, default=25.0, help="Gewichtung qualitative Faktoren in %%"
    )
    parser.add_argument(
        "--max-searches",
        type=int,
        default=DEFAULT_MAX_SEARCHES,
        help=f"Maximale Anzahl an Websuchen (Standard: {DEFAULT_MAX_SEARCHES})",
    )
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Claude-Modell (Standard: {DEFAULT_MODEL})")
    parser.add_argument(
        "--output", "-o", type=Path, default=None, help="Pfad fuer die Markdown-Reportdatei"
    )
    return parser.parse_args(argv)


def _weights_from_args(args: argparse.Namespace) -> dict[str, float]:
    raw = {
        "fundamentaldaten": args.weight_fundamentals,
        "technik": args.weight_technical,
        "news_sentiment": args.weight_news,
        "qualitativ": args.weight_qualitative,
    }
    total = sum(raw.values())
    if total <= 0:
        raise SystemExit("Fehler: Die Summe der Gewichte muss groesser als 0 sein.")
    return {k: v / total for k, v in raw.items()}


def _default_output_path(query: str) -> Path:
    timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    return REPORTS_DIR / f"finanzreport_{timestamp}.md"


def _render_full_report(query: str, args: argparse.Namespace, weights: dict[str, float], result) -> str:
    header = [
        f"# Finanzreport: {query}",
        "",
        f"- Erstellt am: {dt.datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"- Asset-Klasse: {args.asset_class}",
        f"- Modell: {result.model}",
        f"- Durchgefuehrte Websuchen: {result.search_count}",
        "- Gewichtung: "
        + ", ".join(f"{k}={v * 100:.0f}%" for k, v in weights.items()),
        "",
        "---",
        "",
    ]

    footer = []
    if result.sources:
        footer.append("")
        footer.append("## Recherchierte Quellen")
        footer.append("")
        for source in result.sources:
            footer.append(f"- [{source.title}]({source.url})")

    return "\n".join(header) + result.report_markdown + "\n".join(footer)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    weights = _weights_from_args(args)

    print(f"Recherchiere: {args.query!r} ({args.asset_class}, {args.count} Kandidaten) ...", file=sys.stderr)

    try:
        result = research_and_evaluate(
            query=args.query,
            asset_class=args.asset_class,
            weights=weights,
            count=args.count,
            max_searches=args.max_searches,
            model=args.model,
        )
    except anthropic.AuthenticationError:
        print(
            "Fehler: Authentifizierung fehlgeschlagen. Ist ANTHROPIC_API_KEY gesetzt "
            "oder 'ant auth login' ausgefuehrt?",
            file=sys.stderr,
        )
        return 1
    except anthropic.RateLimitError as exc:
        retry_after = exc.response.headers.get("retry-after", "60") if exc.response else "60"
        print(f"Fehler: Rate-Limit erreicht. Erneut versuchen in {retry_after}s.", file=sys.stderr)
        return 1
    except anthropic.APIStatusError as exc:
        print(f"Fehler bei der API-Anfrage ({exc.status_code}): {exc.message}", file=sys.stderr)
        return 1
    except anthropic.APIConnectionError:
        print("Fehler: Netzwerkverbindung zur Claude API fehlgeschlagen.", file=sys.stderr)
        return 1

    report = _render_full_report(args.query, args, weights, result)

    output_path = args.output or _default_output_path(args.query)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report, encoding="utf-8")

    print(f"Report gespeichert unter: {output_path}", file=sys.stderr)
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
