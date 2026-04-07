"""Typer CLI for the Rocket Brands Prospect Scraper."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from config.settings import DEFAULT_CSV, has_proxycurl, has_serper
from config.verticals import VERTICALS
from core.models import Vertical
from core.storage import append_csv, load_csv, save_csv
from pipeline import (
    discover_vertical,
    enrich_prospects,
    run_discovery,
    score_prospect,
)

app = typer.Typer(add_completion=False, help="Rocket Brands Prospect Scraper")
console = Console()


def _score_color(score: int) -> str:
    if score >= 70:
        return "green"
    if score >= 40:
        return "yellow"
    return "red"


def _render_table(prospects: list, title: str = "Prospects") -> Table:
    table = Table(title=title)
    table.add_column("Company", style="cyan", no_wrap=True)
    table.add_column("Domain", style="blue")
    table.add_column("Vertical", style="magenta")
    table.add_column("Email", style="white")
    table.add_column("Affiliate", justify="center")
    table.add_column("Score", justify="right")
    for p in prospects[:50]:
        table.add_row(
            p.company_name[:40],
            p.domain[:30],
            p.vertical.value,
            p.primary_email[:35],
            "yes" if p.has_affiliate_program else "",
            f"[{_score_color(p.score)}]{p.score}[/]",
        )
    return table


@app.command()
def discover(
    vertical: str = typer.Option("all", help="Vertical name or 'all'"),
    pages: int = typer.Option(2, help="SERP pages per query"),
    source: Optional[str] = typer.Option(None, help="Single source: google_search|google_maps|google_play"),
    query: Optional[str] = typer.Option(None, help="Direct query (requires --source)"),
    output: Path = typer.Option(DEFAULT_CSV, help="Output CSV path"),
    no_enrich: bool = typer.Option(False, help="Skip website enrichment"),
    linkedin: bool = typer.Option(False, help="Enrich with LinkedIn (Proxycurl)"),
    max_prospects: Optional[int] = typer.Option(None, help="Cap total new prospects"),
):
    """Discover new prospects."""
    console.print(f"[bold cyan]Rocket Scraper — discover[/] vertical={vertical} pages={pages}")
    console.print(f"Serper API: {'[green]yes[/]' if has_serper() else '[yellow]no (raw scraping)[/]'}")
    console.print(f"Proxycurl:  {'[green]yes[/]' if has_proxycurl() else '[yellow]no[/]'}")

    # Direct single-source mode
    if source and query:
        from sources import google_maps, google_play, google_search
        v_enum = Vertical(vertical) if vertical in VERTICALS else Vertical.UNKNOWN
        with Progress(SpinnerColumn(), TextColumn("{task.description}"), console=console) as prog:
            prog.add_task(f"Running {source}...", total=None)
            if source == "google_search":
                results = google_search.discover(query, v_enum, num_results=pages * 10)
            elif source == "google_maps":
                results = google_maps.discover(query, v_enum)
            elif source == "google_play":
                results = google_play.discover(query, num=pages * 20, vertical=v_enum)
            else:
                console.print(f"[red]Unknown source: {source}[/]")
                raise typer.Exit(1)
        if not no_enrich:
            results = enrich_prospects(results, deep_web=True, use_linkedin=linkedin)
        else:
            for p in results:
                p.score = score_prospect(p)
        append_csv(output, results)
        console.print(_render_table(results, title=f"{source} results"))
        return

    # Full discovery pipeline
    new = run_discovery(
        vertical=vertical,
        pages=pages,
        output=output,
        enrich=not no_enrich,
        use_linkedin=linkedin,
        max_prospects=max_prospects,
    )
    console.print(_render_table(new, title="New prospects"))
    console.print(f"[bold green]Done.[/] {len(new)} new prospects written to {output}")


@app.command()
def enrich(
    input: Path = typer.Option(..., help="Input CSV"),
    output: Optional[Path] = typer.Option(None, help="Output CSV (defaults to overwriting input)"),
    linkedin: bool = typer.Option(False, help="Enrich with LinkedIn"),
    deep: bool = typer.Option(True, help="Deep website crawl"),
    only_unenriched: bool = typer.Option(True, help="Skip already-enriched rows"),
):
    """Enrich existing prospects in a CSV."""
    prospects = load_csv(input)
    if only_unenriched:
        targets = [p for p in prospects if not p.enriched]
    else:
        targets = prospects
    console.print(f"Enriching {len(targets)} of {len(prospects)} prospects...")

    enriched = enrich_prospects(targets, deep_web=deep, use_linkedin=linkedin)

    # Merge back
    by_key = {(p.domain or p.company_name): p for p in prospects}
    for p in enriched:
        by_key[(p.domain or p.company_name)] = p
    merged = list(by_key.values())

    out = output or input
    save_csv(out, merged)
    console.print(_render_table(enriched, title="Enriched"))
    console.print(f"[bold green]Saved {len(merged)} prospects to {out}[/]")


@app.command("scrape-directory")
def scrape_directory_cmd(
    url: str = typer.Option(..., help="Directory page URL"),
    example: str = typer.Option(..., help="One example item from the page"),
    vertical: str = typer.Option("casino", help="Vertical for tagging"),
    output: Path = typer.Option(DEFAULT_CSV, help="Output CSV"),
):
    """Scrape a listing/directory page using AutoScraper."""
    from sources.directories import scrape_directory
    v_enum = Vertical(vertical) if vertical in VERTICALS else Vertical.UNKNOWN
    prospects = scrape_directory(url, example=example, vertical=v_enum)
    for p in prospects:
        p.score = score_prospect(p)
    append_csv(output, prospects)
    console.print(_render_table(prospects, title=f"Directory: {url}"))


@app.command()
def stats(
    input: Path = typer.Option(DEFAULT_CSV, help="CSV file to analyze"),
):
    """Show stats for a prospect CSV."""
    prospects = load_csv(input)
    if not prospects:
        console.print(f"[yellow]No prospects in {input}[/]")
        return

    total = len(prospects)
    with_email = sum(1 for p in prospects if p.primary_email)
    with_contacts = sum(1 for p in prospects if p.contacts)
    with_affiliate = sum(1 for p in prospects if p.has_affiliate_program)
    with_linkedin = sum(1 for p in prospects if p.socials.linkedin)
    high = sum(1 for p in prospects if p.score >= 70)
    mid = sum(1 for p in prospects if 40 <= p.score < 70)

    table = Table(title=f"Stats — {input}")
    table.add_column("Metric")
    table.add_column("Count", justify="right")
    table.add_column("Pct", justify="right")
    def row(label, n):
        pct = f"{100 * n / total:.0f}%" if total else "-"
        table.add_row(label, str(n), pct)
    row("Total prospects", total)
    row("With primary email", with_email)
    row("With contacts", with_contacts)
    row("With affiliate program", with_affiliate)
    row("With LinkedIn", with_linkedin)
    row("High score (70+)", high)
    row("Mid score (40-69)", mid)

    by_vertical: dict[str, int] = {}
    for p in prospects:
        by_vertical[p.vertical.value] = by_vertical.get(p.vertical.value, 0) + 1
    for v, n in sorted(by_vertical.items(), key=lambda x: -x[1]):
        row(f"  vertical: {v}", n)

    console.print(table)


@app.command()
def export(
    input: Path = typer.Option(DEFAULT_CSV, help="Input CSV or DB"),
    output: Path = typer.Option(..., help="Output CSV"),
    min_score: int = typer.Option(0, help="Minimum lead score"),
    vertical: Optional[str] = typer.Option(None, help="Filter by vertical"),
):
    """Export filtered prospects to a new CSV."""
    prospects = load_csv(input)
    filtered = [p for p in prospects if p.score >= min_score]
    if vertical:
        filtered = [p for p in filtered if p.vertical.value == vertical]
    filtered.sort(key=lambda p: p.score, reverse=True)
    save_csv(output, filtered)
    console.print(f"[green]Exported {len(filtered)} prospects to {output}[/]")


@app.command("config")
def config_cmd(action: str = typer.Argument("show")):
    """Show current config."""
    if action == "show":
        console.print(f"SERPER_API_KEY: {'set' if has_serper() else 'NOT set'}")
        console.print(f"PROXYCURL_API_KEY: {'set' if has_proxycurl() else 'NOT set'}")
        console.print(f"Verticals: {', '.join(VERTICALS.keys())}")
        console.print(f"Default CSV: {DEFAULT_CSV}")


if __name__ == "__main__":
    app()
