"""Outreach CLI — generate, preview, send, follow-up, reply-tracking."""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

import typer
from loguru import logger
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from config.settings import DEFAULT_CSV
from core.storage import load_csv
from outreach.config import (
    PROSPECTS_CSV,
    TRACKING_BASE_URL,
    has_groq,
    load_gmail_accounts,
)
from outreach.generator import generate_email
from outreach.models import Campaign, EmailRecord, EmailStatus, SequenceStep
from outreach.scheduler import queue_due_followups
from outreach.sender import GmailSender, is_business_hours
from outreach.storage import (
    add_unsubscribe,
    connect,
    create_campaign,
    emails_by_campaign,
    get_campaign,
    list_campaigns,
    mark_replied,
    save_email,
    update_campaign_counts,
)
from outreach.warmth import check_account_health

app = typer.Typer(add_completion=False, help="Rocket Brands Outreach CLI")
console = Console()


def _resolve_campaign(identifier: str) -> Campaign:
    conn = connect()
    try:
        camp = get_campaign(conn, identifier)
        if not camp:
            console.print(f"[red]No campaign found: {identifier}[/]")
            raise typer.Exit(1)
        return camp
    finally:
        conn.close()


@app.command()
def generate(
    campaign: str = typer.Option(..., help="Campaign name"),
    vertical: str = typer.Option("all", help="Filter prospects by vertical"),
    min_score: int = typer.Option(20, help="Minimum prospect lead score"),
    limit: Optional[int] = typer.Option(None, help="Max emails to generate"),
    prospects_csv: Path = typer.Option(PROSPECTS_CSV, help="Path to prospects CSV"),
):
    """Generate AI-personalized email drafts for prospects in the CSV."""
    console.print(f"[bold cyan]Outreach — generate[/] campaign={campaign}")
    console.print(f"Groq API: {'[green]yes[/]' if has_groq() else '[yellow]no (template fallback)[/]'}")

    if not prospects_csv.exists():
        console.print(f"[red]Prospects CSV not found: {prospects_csv}[/]")
        raise typer.Exit(1)

    prospects = load_csv(prospects_csv)
    # Filter
    filtered = [p for p in prospects if p.primary_email and p.score >= min_score]
    if vertical != "all":
        filtered = [p for p in filtered if p.vertical.value == vertical]
    if limit:
        filtered.sort(key=lambda x: x.score, reverse=True)
        filtered = filtered[:limit]
    console.print(f"Selected {len(filtered)} prospects (score >= {min_score}, has email)")

    if not filtered:
        console.print("[yellow]No prospects match the filter[/]")
        return

    conn = connect()
    try:
        camp = get_campaign(conn, campaign)
        if not camp:
            camp = create_campaign(conn, campaign, vertical=vertical)
        console.print(f"Campaign: [cyan]{camp.name}[/] ({camp.id[:8]})")

        # Skip prospects that already have an initial email in this campaign
        existing_initial = {
            e.prospect_email.lower()
            for e in emails_by_campaign(conn, camp.id)
            if e.sequence_step == SequenceStep.INITIAL
        }

        generated: list[EmailRecord] = []
        with console.status(f"Generating {len(filtered)} emails...") as status:
            for i, p in enumerate(filtered, 1):
                if p.primary_email.lower() in existing_initial:
                    continue
                prospect_dict = {
                    "company_name": p.company_name,
                    "vertical": p.vertical.value,
                    "website": p.website,
                    "description": p.description,
                    "has_affiliate_program": "yes" if p.has_affiliate_program else "no",
                    "contact_1_name": p.contacts[0].name if p.contacts else "",
                    "contact_1_title": p.contacts[0].title if p.contacts else "",
                }
                try:
                    content = generate_email(prospect_dict, step="initial")
                except Exception as e:
                    console.print(f"[yellow]Skip {p.company_name}: {e}[/]")
                    continue

                rec = EmailRecord(
                    campaign_id=camp.id,
                    prospect_company=p.company_name,
                    prospect_email=p.primary_email,
                    prospect_vertical=p.vertical.value,
                    prospect_website=p.website,
                    prospect_description=p.description[:300],
                    prospect_score=p.score,
                    prospect_contact_name=p.contacts[0].name if p.contacts else "",
                    prospect_contact_title=p.contacts[0].title if p.contacts else "",
                    subject=content["subject"],
                    body_text=content["body_text"],
                    body_html=content["body_html"],
                    status=EmailStatus.QUEUED,
                )
                save_email(conn, rec)
                generated.append(rec)
                status.update(f"Generating {i}/{len(filtered)}... ({len(generated)} done)")

        update_campaign_counts(conn, camp.id)
    finally:
        conn.close()

    console.print(f"[bold green]Generated {len(generated)} new email drafts[/]")
    console.print(f"Preview with: [cyan]python outreach_cli.py preview --campaign \"{campaign}\"[/]")


@app.command()
def preview(
    campaign: str = typer.Option(..., help="Campaign name"),
    limit: int = typer.Option(5, help="How many to preview"),
):
    """Preview generated email drafts."""
    camp = _resolve_campaign(campaign)
    conn = connect()
    try:
        emails = emails_by_campaign(conn, camp.id, status="queued", limit=limit)
    finally:
        conn.close()

    if not emails:
        console.print("[yellow]No queued emails to preview[/]")
        return

    for e in emails:
        panel = Panel(
            f"[bold]To:[/] {e.prospect_email}  [dim]({e.prospect_company}, score={e.prospect_score})[/]\n"
            f"[bold]Subject:[/] {e.subject}\n\n"
            f"{e.body_text}",
            title=f"{e.sequence_step.value}",
            border_style="cyan",
        )
        console.print(panel)


@app.command()
def send(
    campaign: str = typer.Option(..., help="Campaign name"),
    dry_run: bool = typer.Option(False, help="Print what would send without sending"),
    ignore_business_hours: bool = typer.Option(False, help="Override business-hours restriction"),
    limit: Optional[int] = typer.Option(None, help="Max emails to send this run"),
):
    """Send queued emails for a campaign (respects rate limits + business hours)."""
    camp = _resolve_campaign(campaign)
    accounts = load_gmail_accounts()
    if not accounts and not dry_run:
        console.print("[red]No Gmail accounts configured. Set GMAIL_USER_1 / GMAIL_APP_PASSWORD_1 in .env[/]")
        raise typer.Exit(1)

    if not ignore_business_hours and not is_business_hours() and not dry_run:
        console.print(
            "[yellow]Outside business hours (8am-6pm Mon-Fri). "
            "Pass --ignore-business-hours to override.[/]"
        )
        raise typer.Exit(0)

    conn = connect()
    try:
        queued = emails_by_campaign(conn, camp.id, status="queued", limit=limit)
    finally:
        conn.close()

    if not queued:
        console.print("[yellow]No queued emails to send[/]")
        return

    console.print(f"[cyan]Sending {len(queued)} emails[/] from {len(accounts)} account(s){' (DRY RUN)' if dry_run else ''}")
    sender = GmailSender(accounts)
    results = asyncio.run(
        sender.send_batch(
            queued,
            tracking_base_url=TRACKING_BASE_URL,
            enforce_business_hours=not ignore_business_hours,
            dry_run=dry_run,
        )
    )

    counts: dict = {}
    for r in results:
        counts[r.get("status", "?")] = counts.get(r.get("status", "?"), 0) + 1
    console.print(f"[bold green]Done.[/] {counts}")

    conn = connect()
    try:
        update_campaign_counts(conn, camp.id)
    finally:
        conn.close()


@app.command()
def status(
    campaign: Optional[str] = typer.Option(None, help="Campaign name (omit for all)"),
):
    """Show campaign status and metrics."""
    conn = connect()
    try:
        if campaign:
            camps = [_resolve_campaign(campaign)]
        else:
            camps = list_campaigns(conn)
        for c in camps:
            update_campaign_counts(conn, c.id)
    finally:
        conn.close()

    conn = connect()
    try:
        camps = list_campaigns(conn)
    finally:
        conn.close()

    if campaign:
        camps = [c for c in camps if c.name == campaign or c.id == campaign]

    if not camps:
        console.print("[yellow]No campaigns yet[/]")
        return

    table = Table(title="Campaigns")
    table.add_column("Name")
    table.add_column("Vertical")
    table.add_column("Status")
    table.add_column("Total", justify="right")
    table.add_column("Sent", justify="right")
    table.add_column("Opens", justify="right")
    table.add_column("Clicks", justify="right")
    table.add_column("Replies", justify="right")
    table.add_column("Bounces", justify="right")
    for c in camps:
        table.add_row(
            c.name, c.vertical, c.status.value,
            str(c.total_emails), str(c.sent_count),
            str(c.open_count), str(c.click_count),
            str(c.reply_count), str(c.bounce_count),
        )
    console.print(table)


@app.command()
def followup(
    campaign: Optional[str] = typer.Option(None, help="Restrict to a campaign"),
    auto_send: bool = typer.Option(False, help="Send queued follow-ups immediately"),
):
    """Generate follow-ups for emails that are due (3/7/14 days after initial send)."""
    camp_id = None
    if campaign:
        camp_id = _resolve_campaign(campaign).id
    queued = queue_due_followups(campaign_id=camp_id)
    console.print(f"[cyan]Queued {len(queued)} follow-ups[/]")

    if auto_send and queued:
        accounts = load_gmail_accounts()
        sender = GmailSender(accounts)
        asyncio.run(sender.send_batch(queued, tracking_base_url=TRACKING_BASE_URL))


@app.command()
def reply(
    email: str = typer.Argument(..., help="Prospect email that replied"),
):
    """Mark a prospect as replied — stops all further follow-ups."""
    conn = connect()
    try:
        n = mark_replied(conn, email)
    finally:
        conn.close()
    console.print(f"[green]Marked {n} email(s) as replied for {email}[/]")


@app.command()
def unsubscribe(
    email: str = typer.Argument(..., help="Prospect email to unsubscribe"),
):
    """Add a prospect to the unsubscribe list."""
    conn = connect()
    try:
        add_unsubscribe(conn, email)
    finally:
        conn.close()
    console.print(f"[green]Unsubscribed {email}[/]")


@app.command()
def campaigns():
    """List all campaigns."""
    status(campaign=None)


@app.command()
def health():
    """Check Gmail account health (sends today, remaining capacity)."""
    accounts = load_gmail_accounts()
    if not accounts:
        console.print("[yellow]No Gmail accounts configured[/]")
        return
    table = Table(title="Account Health")
    table.add_column("Email")
    table.add_column("Today", justify="right")
    table.add_column("Hour", justify="right")
    table.add_column("Daily Cap", justify="right")
    table.add_column("Remaining", justify="right")
    table.add_column("Status")
    for a in accounts:
        h = check_account_health(a.email)
        status_str = "[green]healthy[/]" if h.healthy else "[red]at cap[/]"
        table.add_row(
            a.email, str(h.sends_today), str(h.sends_hour),
            str(h.daily_cap), str(h.daily_remaining), status_str,
        )
    console.print(table)
    console.print(f"Business hours: {'[green]yes[/]' if is_business_hours() else '[yellow]no[/]'}")


@app.command()
def export(
    campaign: str = typer.Option(..., help="Campaign name"),
    output: Path = typer.Option("campaign_results.csv", help="Output CSV"),
):
    """Export a campaign's emails + metrics to CSV."""
    import csv as csv_mod
    camp = _resolve_campaign(campaign)
    conn = connect()
    try:
        emails = emails_by_campaign(conn, camp.id)
    finally:
        conn.close()

    cols = [
        "prospect_company", "prospect_email", "prospect_vertical", "prospect_score",
        "sequence_step", "status", "subject", "sent_at", "opened_at", "opened_count",
        "clicked_at", "clicked_count", "replied_at", "sender_email", "error",
    ]
    with output.open("w", newline="", encoding="utf-8") as f:
        w = csv_mod.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for e in emails:
            d = e.model_dump()
            row = {c: (d.get(c) if d.get(c) is not None else "") for c in cols}
            # datetime → iso
            for k in ("sent_at", "opened_at", "clicked_at", "replied_at"):
                if row[k]:
                    row[k] = str(row[k])
            w.writerow(row)
    console.print(f"[green]Exported {len(emails)} emails to {output}[/]")


@app.command("track-server")
def track_server(
    host: str = typer.Option("0.0.0.0", help="Bind host"),
    port: int = typer.Option(8502, help="Bind port"),
):
    """Start the tracking pixel server."""
    try:
        import uvicorn  # type: ignore
    except ImportError:
        console.print("[red]uvicorn not installed. pip install uvicorn[/]")
        raise typer.Exit(1)
    console.print(f"[cyan]Starting tracking server on {host}:{port}[/]")
    uvicorn.run("tracking_server:app", host=host, port=port, log_level="info")


if __name__ == "__main__":
    app()
