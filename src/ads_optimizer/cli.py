from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from ads_optimizer.agent import OptimizationAgent
from ads_optimizer.setup_guide import render_setup_checklist

app = typer.Typer(
    add_completion=False,
    help="Google Ads optimization agent — audit, recommend, optionally apply.",
)
console = Console()


def _print_recommendations(recs) -> None:
    table = Table(title=f"Recommendations ({len(recs)})")
    table.add_column("Severity", style="bold")
    table.add_column("Action")
    table.add_column("Entity")
    table.add_column("Reason")
    for r in recs:
        style = {"high": "red", "medium": "yellow", "low": "green"}[r.severity.value]
        table.add_row(
            f"[{style}]{r.severity.value}[/{style}]",
            r.action.value,
            f"{r.entity_type}: {r.entity_name}",
            r.reason,
        )
    console.print(table)


@app.command("init")
def init_cmd(
    developer_token: Optional[str] = typer.Option(None, help="Google Ads developer token"),
    client_id: Optional[str] = typer.Option(None, help="OAuth Desktop client id"),
    client_secret: Optional[str] = typer.Option(None, "--client-secret", help="OAuth client secret"),
    customer_id: Optional[str] = typer.Option(None, help="Client customer id (10 digits)"),
    login_customer_id: Optional[str] = typer.Option(None, help="MCC id if you sign in via a manager"),
    with_analytics: bool = typer.Option(False, "--with-analytics", help="Also request GA4 scopes"),
    skip_oauth: bool = typer.Option(False, "--skip-oauth", help="Write keys only; do not open the browser"),
    openrouter_api_key: Optional[str] = typer.Option(None, help="Optional OpenRouter key for AI Assistant"),
) -> None:
    """Write Google Ads credentials to .env and optionally sign in with Google."""
    from ads_optimizer.envfile import ENV_PATH, ensure_env_file
    from ads_optimizer.setup_wizard import SETUP_GUIDE, oauth_and_save, save_setup, setup_status

    ensure_env_file()
    console.print("[bold]Google Ads setup[/bold] — credentials go into .env (no YAML required).\n")
    for block in SETUP_GUIDE:
        console.print(f"[cyan]{block['title']}[/cyan]")
        console.print(f"  {block['summary']}")
        for step in block["steps"]:
            console.print(f"  • {step}")
        for link in block["links"]:
            console.print(f"    {link['label']}: {link['url']}")
        console.print()

    token = developer_token or typer.prompt("Developer token")
    cid = client_id or typer.prompt("OAuth Client ID")
    secret = client_secret or typer.prompt("OAuth Client secret", hide_input=True)
    fields = {
        "developer_token": token,
        "client_id": cid,
        "client_secret": secret,
    }
    if customer_id:
        fields["customer_id"] = customer_id
    elif typer.confirm("Enter a customer ID now? (No = first accessible account after sign-in)", default=False):
        fields["customer_id"] = typer.prompt("Customer ID (10 digits, no dashes)")
    if login_customer_id:
        fields["login_customer_id"] = login_customer_id
    if openrouter_api_key:
        fields["openrouter_api_key"] = openrouter_api_key
    save_setup(fields)
    console.print(f"Wrote {ENV_PATH}")

    if skip_oauth:
        refresh = typer.prompt("Refresh token (leave empty to skip)", default="")
        if refresh:
            save_setup({"refresh_token": refresh})
    else:
        console.print("\nA browser window will open. Sign in and allow access.\n")
        try:
            result = oauth_and_save(with_analytics=with_analytics)
        except Exception as exc:  # noqa: BLE001
            console.print(f"[red]Google sign-in failed:[/red] {exc}")
            raise typer.Exit(code=1) from exc
        if result.get("picked_customer_id"):
            console.print(f"Using customer {result['picked_customer_id']}")
        if result.get("account_error"):
            console.print(f"[yellow]Signed in, but listing accounts failed:[/yellow] {result['account_error']}")

    status = setup_status()
    if status.get("ready"):
        console.print("[green]Ready.[/green] Start the UI: gads-agent ui")
    else:
        console.print("[yellow]Credentials incomplete.[/yellow] Re-run `gads-agent init` or open Setup in the UI.")


@app.command("setup")
def setup_cmd() -> None:
    """Print launch checklist for an efficient Google Ads account structure."""
    table = Table(title="Google Ads setup checklist")
    table.add_column("Priority")
    table.add_column("Area")
    table.add_column("Item")
    table.add_column("Why")
    for item in render_setup_checklist():
        style = {
            "critical": "red",
            "high": "yellow",
            "medium": "cyan",
            "low": "green",
        }[item.priority]
        table.add_row(
            f"[{style}]{item.priority}[/{style}]",
            item.area,
            item.item,
            item.why,
        )
    console.print(table)


@app.command("mcp-setup")
def mcp_setup_cmd() -> None:
    """Wire official Google Ads MCP (read-only) into Cursor via .env / google-ads.yaml."""
    candidates = [
        Path(__file__).resolve().parents[2] / "scripts" / "setup_google_ads_mcp.py",
        Path.cwd() / "scripts" / "setup_google_ads_mcp.py",
    ]
    script = next((p for p in candidates if p.exists()), None)
    if script is None:
        console.print("[red]scripts/setup_google_ads_mcp.py not found[/red]")
        raise typer.Exit(code=1)
    raise SystemExit(subprocess.call([sys.executable, str(script)]))


@app.command("audit")
def audit_cmd(
    export: Optional[Path] = typer.Option(
        None, "--export", help="Optional path for JSON report"
    ),
) -> None:
    """Fetch metrics and print optimization recommendations (no mutations)."""
    agent = OptimizationAgent()
    recs = agent.audit()
    _print_recommendations(recs)
    path = agent.export_report(recs, export)
    console.print(f"Report saved: {path}")


@app.command("optimize")
def optimize_cmd(
    apply: bool = typer.Option(
        False,
        "--apply",
        help="Apply safe mutations (pause keywords/ads, add negatives, change bids).",
    ),
    export: Optional[Path] = typer.Option(
        None, "--export", help="Optional path for JSON report"
    ),
) -> None:
    """Run audit and optionally apply recommendations. Default is dry-run."""
    if apply:
        confirm = typer.confirm(
            "Apply mutations to the live Google Ads account?",
            default=False,
        )
        if not confirm:
            raise typer.Abort()

    agent = OptimizationAgent()
    recs, results = agent.optimize(apply=apply)
    _print_recommendations(recs)

    result_table = Table(title="Apply results")
    result_table.add_column("OK")
    result_table.add_column("Action")
    result_table.add_column("Entity")
    result_table.add_column("Message")
    for item in results:
        result_table.add_row(
            "yes" if item.success else "no",
            item.recommendation.action.value,
            item.recommendation.entity_name,
            item.message,
        )
    console.print(result_table)

    path = agent.export_report(recs, export)
    mode = "APPLY" if apply else "DRY-RUN"
    console.print(f"[{mode}] Report saved: {path}")


@app.command("chat")
def chat_cmd(
    message: str = typer.Argument(..., help="Сообщение агенту"),
    model: Optional[str] = typer.Option(None, help="OpenRouter model id"),
) -> None:
    """Управление системой через LLM (OpenRouter + tools)."""
    from ads_optimizer.chat_agent import ChatAgent
    from ads_optimizer.openrouter import get_openrouter

    llm = get_openrouter()
    if not llm.configured:
        console.print("[red]Задайте OPENROUTER_API_KEY в .env[/red]")
        raise typer.Exit(code=1)
    chosen = model or llm.settings.openrouter_default_model
    result = ChatAgent().chat([{"role": "user", "content": message}], model=chosen)
    if result.get("tool_trace"):
        console.print("[dim]tools:[/dim]", ", ".join(t["tool"] for t in result["tool_trace"]))
    console.print(result.get("message") or "")


@app.command("models")
def models_cmd() -> None:
    """Топ-20 моделей OpenRouter с поддержкой tools."""
    from ads_optimizer.openrouter import get_openrouter

    items = get_openrouter().list_top_models(20)
    table = Table(title="Top OpenRouter models (tools)")
    table.add_column("#")
    table.add_column("ID")
    table.add_column("Name")
    for i, m in enumerate(items, 1):
        table.add_row(str(i), m.get("id", ""), m.get("name", ""))
    console.print(table)


@app.command("ui")
def ui_cmd(
    host: str = typer.Option("127.0.0.1", help="Bind host"),
    port: int = typer.Option(8787, help="Bind port"),
) -> None:
    """Launch the web dashboard. Demo mode until Setup / gads-agent init."""
    import uvicorn

    console.print(f"Open http://{host}:{port}")
    uvicorn.run("ads_optimizer.webapp:app", host=host, port=port, reload=False)


@app.command("accounts")
def accounts_cmd() -> None:
    """List accessible Google Ads accounts (mcp-google-ads list_accounts)."""
    from ads_optimizer.service import AdsService

    svc = AdsService()
    table = Table(title=f"Accounts ({'demo' if svc.demo else 'live'})")
    table.add_column("ID")
    table.add_column("Name / resource")
    for acc in svc.list_accounts():
        table.add_row(acc.get("id", ""), acc.get("name") or acc.get("resource_name", ""))
    console.print(table)


@app.command("gaql")
def gaql_cmd(
    query: str = typer.Argument(..., help="GAQL query"),
    customer_id: Optional[str] = typer.Option(None, help="Override customer ID"),
) -> None:
    """Run arbitrary GAQL (mcp-google-ads run_gaql)."""
    from ads_optimizer.service import AdsService
    import json

    result = AdsService().gaql(query, customer_id)
    console.print_json(json.dumps(result))


if __name__ == "__main__":
    app()
