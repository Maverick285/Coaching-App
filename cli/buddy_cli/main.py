"""buddy — terminal client for the Phase 0 backend."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

import click
import httpx
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

from buddy_cli.config import load_cli_config

console = Console()


def _client():
    cfg = load_cli_config()
    headers = {"Authorization": f"Bearer {cfg.auth_token}"}
    return httpx.Client(base_url=cfg.backend_url, headers=headers, timeout=120), cfg


@click.group(help="Buddy CLI — talk to the backend from your terminal.")
def cli() -> None:
    pass


# ---- chat -----------------------------------------------------------------


@cli.command()
@click.option("--session", "session_id", default=None, help="Continue an existing session.")
@click.option("--reasoning/--no-reasoning", default=False, help="Force the reasoning tier.")
def chat(session_id: str | None, reasoning: bool) -> None:
    """Open an interactive REPL with the buddy."""
    client, cfg = _client()
    sid = session_id
    console.print(Panel.fit("Buddy chat. Ctrl-D or /exit to quit.", border_style="dim"))
    while True:
        try:
            line = Prompt.ask("[bold cyan]you[/]")
        except (EOFError, KeyboardInterrupt):
            console.print()
            break
        if not line.strip():
            continue
        if line.strip().lower() in {"/exit", "/quit", ":q"}:
            break
        try:
            r = client.post(
                "/converse",
                json={
                    "session_id": sid,
                    "message": line,
                    "force_reasoning_tier": reasoning,
                },
            )
            r.raise_for_status()
        except httpx.HTTPError as exc:
            console.print(f"[red]Error:[/] {exc}")
            continue
        data = r.json()
        sid = data["session_id"]
        console.print(
            Panel(
                Markdown(data["response"]),
                title=f"[dim]{data['model_used']}  ${data['cost_estimate']:.4f}[/]",
                border_style="green",
            )
        )


# ---- intake ---------------------------------------------------------------


@cli.command()
def intake() -> None:
    """Run the persona calibration intake conversationally."""
    client, _ = _client()
    r = client.post("/intake/start")
    r.raise_for_status()
    state = r.json()
    intake_id = state["intake_id"]
    while True:
        console.print(
            Panel(
                state["question"],
                title=f"Step {state['step']}/{state['total_steps']}",
                border_style="cyan",
            )
        )
        answer = _multiline_prompt("your answer (end with a blank line)")
        r = client.post(
            "/intake/turn", json={"intake_id": intake_id, "answer": answer}
        )
        r.raise_for_status()
        state = r.json()
        if state["finished"]:
            break

    console.print("[bold]Synthesizing PERSONA.md and MEMORY.md...[/]")
    r = client.post("/intake/finalize", json={"intake_id": intake_id})
    r.raise_for_status()
    out = r.json()
    console.print(Panel(Markdown(out["persona_md"]), title="PERSONA.md", border_style="green"))
    console.print(Panel(Markdown(out["memory_md"]), title="MEMORY.md", border_style="green"))
    console.print(
        "[dim]Both files written. Edit them with `buddy memory edit PERSONA.md` or `MEMORY.md`.[/]"
    )


def _multiline_prompt(label: str) -> str:
    console.print(f"[dim]{label}[/]")
    lines: list[str] = []
    while True:
        try:
            line = input("> ")
        except EOFError:
            break
        if line == "":
            if lines:
                break
            continue
        lines.append(line)
    return "\n".join(lines)


# ---- memory --------------------------------------------------------------


@cli.group()
def memory() -> None:
    """Memory file operations."""


@memory.command("list")
def memory_list() -> None:
    client, _ = _client()
    r = client.get("/memory/files")
    r.raise_for_status()
    table = Table(title="Memory files")
    table.add_column("Path")
    table.add_column("Type")
    table.add_column("Bytes", justify="right")
    table.add_column("Indexed?", justify="center")
    for f in r.json()["files"]:
        table.add_row(
            f["path"],
            f["document_type"],
            str(f["bytes"]),
            "✓" if f["indexed"] else "·",
        )
    console.print(table)


@memory.command("read")
@click.argument("path")
def memory_read(path: str) -> None:
    client, _ = _client()
    r = client.get(f"/memory/file/{path}")
    r.raise_for_status()
    data = r.json()
    console.print(Panel(Markdown(data["content"]), title=data["path"], border_style="cyan"))


@memory.command("edit")
@click.argument("path")
def memory_edit(path: str) -> None:
    client, cfg = _client()
    r = client.get(f"/memory/file/{path}")
    if r.status_code == 404:
        body = ""
    else:
        r.raise_for_status()
        body = r.json()["content"]

    with tempfile.NamedTemporaryFile("w+", suffix=".md", delete=False) as tmp:
        tmp.write(body)
        tmp_path = Path(tmp.name)
    try:
        subprocess.run([cfg.editor, str(tmp_path)], check=True)  # noqa: S603
        new_body = tmp_path.read_text(encoding="utf-8")
    finally:
        os.unlink(tmp_path)

    if new_body == body:
        console.print("[dim]No changes.[/]")
        return
    r = client.put(
        f"/memory/file/{path}",
        json={"content": new_body, "commit_message": f"cli: edit {path}"},
    )
    r.raise_for_status()
    console.print(f"[green]Saved {path}.[/]")


# ---- search --------------------------------------------------------------


@cli.command()
@click.argument("query")
@click.option("--limit", default=10, type=int)
def search(query: str, limit: int) -> None:
    """Search memory directly."""
    client, _ = _client()
    r = client.post("/memory/search", json={"query": query, "limit": limit})
    r.raise_for_status()
    for hit in r.json()["hits"]:
        console.print(
            Panel(
                Markdown(hit["content"] or ""),
                title=f"[dim]{hit['document_path']} #chunk{hit['chunk_index']} score={hit['score']:.3f}[/]",
                border_style="magenta",
            )
        )


# ---- dreams --------------------------------------------------------------


@cli.command()
def dreams() -> None:
    """Review pending dream proposals; show recent auto-applied changes."""
    client, _ = _client()
    r = client.get("/memory/dreams")
    r.raise_for_status()
    payload = r.json()
    pending = payload["pending"]
    auto = payload["auto_applied_recent"]

    if not pending:
        console.print("[dim]No proposals pending review.[/]")
    for p in pending:
        console.print(
            Panel(
                Markdown(
                    f"**{p['summary']}**  →  `{p['target_path']}`\n\n"
                    f"_Kind: {p['proposal_kind']}_\n\n"
                    f"{p['rationale']}\n\n---\n\n```markdown\n{p['proposed_content']}\n```"
                ),
                title=f"Proposal {p['id'][:8]}",
                border_style="yellow",
            )
        )
        choice = Prompt.ask("[a]pprove / [r]eject / [s]kip", choices=["a", "r", "s"], default="s")
        if choice == "a":
            client.post(
                "/memory/dreams",
                json={"action": "approve", "proposal_id": p["id"]},
            )
            console.print("[green]approved[/]")
        elif choice == "r":
            client.post(
                "/memory/dreams",
                json={"action": "reject", "proposal_id": p["id"]},
            )
            console.print("[red]rejected[/]")
        else:
            console.print("[dim]skipped[/]")

    if auto:
        console.print()
        console.print("[bold]Auto-applied recently:[/]")
        for p in auto:
            console.print(f"  • {p['summary']} → {p['target_path']} ({p['proposal_kind']})")


# ---- explain -------------------------------------------------------------


@cli.command()
@click.argument("session_id")
@click.argument("message_id")
def explain(session_id: str, message_id: str) -> None:
    """Show what memory was used for a given response."""
    client, _ = _client()
    r = client.post(
        "/memory/explain",
        json={"session_id": session_id, "message_id": message_id},
    )
    r.raise_for_status()
    for item in r.json()["memory_loaded"]:
        score = f" score={item['score']:.3f}" if item.get("score") else ""
        console.print(f"  • [cyan]{item['file']}[/]  ({item['reason']}{score})")


# ---- usage ---------------------------------------------------------------


@cli.command()
def usage() -> None:
    """Show API usage and budget status."""
    client, _ = _client()
    r = client.get("/usage")
    r.raise_for_status()
    data = r.json()
    table = Table(title="API usage")
    table.add_column("Bucket")
    table.add_column("Tokens in", justify="right")
    table.add_column("Tokens out", justify="right")
    table.add_column("Cost (USD)", justify="right")
    for bucket_key in ("today", "month_to_date", "last_7_days"):
        b = data[bucket_key]
        table.add_row(bucket_key, str(b["tokens_in"]), str(b["tokens_out"]), f"${b['cost_usd']:.4f}")
    console.print(table)
    console.print(
        f"Soft cap: ${data['soft_cap_usd']:.2f} ({'EXCEEDED' if data['soft_cap_exceeded'] else 'ok'})  "
        f"Hard cap: ${data['hard_cap_usd']:.2f} ({'EXCEEDED' if data['hard_cap_exceeded'] else 'ok'})"
    )


# ---- history -------------------------------------------------------------


@cli.command()
@click.option("--limit", default=20, type=int)
def history(limit: int) -> None:
    """List recent conversations."""
    client, _ = _client()
    r = client.get("/conversations", params={"limit": limit})
    r.raise_for_status()
    table = Table(title="Recent conversations")
    table.add_column("Session")
    table.add_column("Last message")
    table.add_column("Msgs", justify="right")
    table.add_column("Title")
    for s in r.json()["sessions"]:
        table.add_row(
            s["session_id"][:8],
            s["last_message_at"],
            str(s["message_count"]),
            s["title"][:60],
        )
    console.print(table)


# ---- clone ---------------------------------------------------------------


@cli.command()
def clone() -> None:
    """Print the git clone command for the memory repo."""
    client, _ = _client()
    r = client.get("/memory/clone-instructions")
    r.raise_for_status()
    data = r.json()
    console.print(data["instructions"])


# ---- Phase 2: goals, tasks, log, grade, journal --------------------------


@cli.group()
def goal() -> None:
    """Goal CRUD."""


@goal.command("list")
def goal_list() -> None:
    client, _ = _client()
    r = client.get("/goals")
    r.raise_for_status()
    table = Table(title="Goals")
    table.add_column("ID", justify="right")
    table.add_column("Pri", justify="right")
    table.add_column("State")
    table.add_column("Pace")
    table.add_column("Statement")
    for g in r.json()["goals"]:
        pace = (
            f"{g['pace_target_amount']:g} {g['pace_target_unit']}"
            if g["pace_target_amount"]
            else "-"
        )
        table.add_row(str(g["id"]), str(g["priority"]), g["state"], pace, g["statement"][:60])
    console.print(table)


@goal.command("show")
@click.argument("goal_id", type=int)
def goal_show(goal_id: int) -> None:
    client, _ = _client()
    r = client.get(f"/goals/{goal_id}")
    r.raise_for_status()
    data = r.json()
    g = data["goal"]
    console.print(
        Panel(
            f"[bold]{g['statement']}[/]\n\n"
            f"State: {g['state']}  Priority: {g['priority']}  Approach: {g['approach']}\n"
            f"Pace: {g['pace_target_amount']:g} {g['pace_target_unit']}\n"
            f"Today: {data['today_progress']:g} → grade {data['today_grade']:.2f}\n"
            f"MVP threshold: {g['mvp_threshold'] or '(none)'}",
            title=f"Goal {goal_id}",
            border_style="cyan",
        )
    )
    if data["tasks"]:
        table = Table(title="Tasks")
        table.add_column("ID", justify="right")
        table.add_column("State")
        table.add_column("Description")
        for t in data["tasks"]:
            table.add_row(str(t["id"]), t["state"], t["description"][:60])
        console.print(table)
    if data["intentions"]:
        for i in data["intentions"]:
            console.print(
                f"  [magenta]{i['cue_type']}:[/] if {i['cue_text']} → then {i['response_text']}"
            )


@goal.command("add")
@click.option("--statement", prompt=True)
@click.option("--priority", default=3, type=click.IntRange(1, 5))
@click.option("--pace-unit", default="")
@click.option("--pace-amount", default=0.0, type=float)
@click.option("--pace-description", default="")
@click.option("--mvp", default="")
def goal_add(statement, priority, pace_unit, pace_amount, pace_description, mvp) -> None:
    client, _ = _client()
    r = client.post(
        "/goals",
        json={
            "statement": statement,
            "priority": priority,
            "pace_target_unit": pace_unit,
            "pace_target_amount": pace_amount,
            "pace_target_description": pace_description,
            "mvp_threshold": mvp,
        },
    )
    r.raise_for_status()
    console.print(f"[green]Created goal {r.json()['id']}.[/]")


@goal.command("woop")
@click.option("--wish", prompt=True, help="What do you want?")
@click.option("--obstacle", default=None, help="Initial obstacle in current reality")
@click.option("--pace-unit", default=None, help="Suggested pace unit")
def goal_woop(wish, obstacle, pace_unit) -> None:
    """Run WOOP planning on a wish; print the proposed structure."""
    client, _ = _client()
    payload = {"wish": wish}
    if obstacle:
        payload["initial_obstacle"] = obstacle
    if pace_unit:
        payload["desired_pace_unit"] = pace_unit
    r = client.post("/goals/woop", json=payload)
    r.raise_for_status()
    data = r.json()
    body = (
        f"**Wish:** {data['wish']}\n\n"
        f"**Outcome:** {data['outcome']}\n\n"
        f"**Obstacles:**\n" + "\n".join(f"- {o}" for o in data["obstacles"]) + "\n\n"
        f"**Plan (if-then):**\n" + "\n".join(f"- {p}" for p in data["plan"]) + "\n\n"
        f"**Suggested tasks:**\n" + "\n".join(f"- {t}" for t in data["suggested_tasks"]) + "\n\n"
        f"**Suggested pace:** {data['suggested_pace_amount']:g} {data['suggested_pace_unit']} — {data['suggested_pace_description']}"
    )
    console.print(Panel(Markdown(body), title="WOOP", border_style="cyan"))


@goal.command("state")
@click.argument("goal_id", type=int)
@click.argument("new_state", type=click.Choice(["proposed", "active", "paused", "completed", "abandoned"]))
def goal_state(goal_id, new_state) -> None:
    client, _ = _client()
    r = client.patch(f"/goals/{goal_id}", json={"state": new_state})
    r.raise_for_status()
    console.print(f"[green]Goal {goal_id} → {new_state}[/]")


@cli.group()
def task() -> None:
    """Task CRUD."""


@task.command("list")
@click.option("--goal", "goal_id", type=int, default=None)
@click.option("--state", default=None)
def task_list(goal_id, state) -> None:
    client, _ = _client()
    params = {}
    if goal_id is not None:
        params["goal_id"] = goal_id
    if state:
        params["state"] = state
    r = client.get("/tasks", params=params)
    r.raise_for_status()
    table = Table(title="Tasks")
    table.add_column("ID", justify="right")
    table.add_column("Goal", justify="right")
    table.add_column("State")
    table.add_column("Description")
    for t in r.json()["tasks"]:
        table.add_row(str(t["id"]), str(t["goal_id"]), t["state"], t["description"][:60])
    console.print(table)


@task.command("done")
@click.argument("task_id", type=int)
def task_done(task_id) -> None:
    client, _ = _client()
    r = client.patch(f"/tasks/{task_id}", json={"state": "done"})
    r.raise_for_status()
    console.print(f"[green]Task {task_id} done.[/]")


@cli.command()
@click.argument("text", nargs=-1, required=True)
@click.option("--goal", "goal_id", type=int, default=None, help="Skip attribution; log directly.")
@click.option("--units", default=None, type=float)
@click.option("--unit-label", default="")
def log(text, goal_id, units, unit_label) -> None:
    """Log progress. Either pass --goal/--units for direct, or free-form for attribution."""
    client, _ = _client()
    text_str = " ".join(text)
    if goal_id is not None and units is not None:
        r = client.post(
            "/progress/log",
            json={
                "goal_id": goal_id,
                "attributed_units": units,
                "unit_label": unit_label,
                "raw_text": text_str,
            },
        )
        r.raise_for_status()
        console.print(f"[green]Logged {units} {unit_label} on goal {goal_id}.[/]")
    else:
        r = client.post("/progress/freeform", json={"text": text_str})
        r.raise_for_status()
        data = r.json()
        for a in data["attributions"]:
            console.print(
                f"  [cyan]goal {a['goal_id']}[/]: {a['units']:g} {a['unit_label']} (conf {a['confidence']:.2f}) — {a['rationale']}"
            )
        if data["unattributed_text"]:
            console.print(f"  [dim]unattributed:[/] {data['unattributed_text']}")


@cli.command()
def grade() -> None:
    """Show today's par-1 grade with the system explanation."""
    client, _ = _client()
    r = client.get("/grade/today")
    r.raise_for_status()
    data = r.json()
    console.print(
        Panel(
            f"[bold]Today: {data['system_score']:.2f}[/]"
            + (" [red](zero day)[/]" if data["is_zero_day"] else "")
            + f"\n\n{data['explanation']}",
            title=str(data["grade_date"]),
            border_style="green" if not data["is_zero_day"] else "red",
        )
    )
    if data["per_goal"]:
        table = Table(title="Per-goal")
        table.add_column("Goal", justify="right")
        table.add_column("Score", justify="right")
        table.add_column("Today")
        table.add_column("Pace")
        for p in data["per_goal"]:
            table.add_row(
                str(p["goal_id"]),
                f"{p['score']:.2f}",
                f"{p['progress_today']:g} {p['pace_target_unit']}",
                f"{p['pace_target_amount']:g} {p['pace_target_unit']}",
            )
        console.print(table)


@cli.command()
def streak() -> None:
    """Show the no-zero-day streak with paused days marked."""
    client, _ = _client()
    r = client.get("/streak")
    r.raise_for_status()
    data = r.json()
    console.print(
        f"[bold]Current streak: {data['current_streak_length']} days[/]"
        + (f"  pauses: {len(data['pause_days'])}" if data["pause_days"] else "")
    )
    for d in data["history"][-14:]:
        marker = "·" if d["is_pause"] else ("0" if d["is_zero"] else "✓")
        console.print(f"  {d['date']}: {marker} {d['score']:.2f}")


@cli.command()
def weekly() -> None:
    """Run a weekly review and print the rollup."""
    client, _ = _client()
    r = client.get("/weekly-review")
    r.raise_for_status()
    data = r.json()
    body = (
        f"**Week:** {data['week_start']} → {data['week_end']}\n\n"
        f"**Average grade:** {data['average_day_grade']:.2f}\n\n"
        f"**Patterns:**\n"
        + "\n".join(f"- {p}" for p in data["pattern_observations"])
        + "\n\n**Suggestions:**\n"
        + "\n".join(f"- {s}" for s in data["suggested_adjustments"])
    )
    console.print(Panel(Markdown(body), title="Weekly review", border_style="cyan"))


@cli.command()
@click.option("--day", default=None, help="ISO date; default today.")
def journal(day) -> None:
    """Edit today's journal entry in $EDITOR."""
    import datetime as _dt

    client, cfg = _client()
    target = day or _dt.date.today().isoformat()
    r = client.get(f"/journal/{target}")
    r.raise_for_status()
    body = r.json().get("content", "")

    import tempfile

    with tempfile.NamedTemporaryFile("w+", suffix=".md", delete=False) as tmp:
        tmp.write(body)
        tmp_path = Path(tmp.name)
    try:
        subprocess.run([cfg.editor, str(tmp_path)], check=True)  # noqa: S603
        new = tmp_path.read_text(encoding="utf-8")
    finally:
        os.unlink(tmp_path)
    if new == body:
        console.print("[dim]No changes.[/]")
        return
    r = client.put(f"/journal/{target}", json={"content": new, "mood": "", "tags": []})
    r.raise_for_status()
    console.print(f"[green]Saved journal for {target}.[/]")


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
