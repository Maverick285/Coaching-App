"""buddy-agent — command-line entrypoint for the PC agent.

Usage:
    buddy-agent run                     # run in the foreground
    buddy-agent ping                    # one-shot snapshot + status check
    buddy-agent categorize <app> <cat>  # add a user mapping
    buddy-agent show-config             # print effective config

Config resolution order (later wins):
    1. ~/.config/buddy-agent/config.toml
    2. environment: BUDDY_BACKEND_URL, BUDDY_AUTH_TOKEN
    3. CLI flags
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path

try:
    import tomllib  # py311+
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore

from .agent import Agent, AgentConfig
from .categories import KNOWN_CATEGORIES_FALLBACK, add_user_mapping, categorize
from .platform import get_adapter

CONFIG_PATH = (
    Path(os.environ.get("XDG_CONFIG_HOME") or (Path.home() / ".config"))
    / "buddy-agent"
    / "config.toml"
)


@dataclass
class CLIConfig:
    backend_url: str
    auth_token: str
    poll_interval_seconds: int = 10
    report_interval_seconds: int = 10


def _load_cli_config(args: argparse.Namespace) -> CLIConfig:
    backend = ""
    token = ""
    poll = 10
    report = 10
    if CONFIG_PATH.exists():
        with CONFIG_PATH.open("rb") as f:
            data = tomllib.load(f)
        backend = data.get("backend_url", "") or backend
        token = data.get("auth_token", "") or token
        poll = int(data.get("poll_interval_seconds", poll))
        report = int(data.get("report_interval_seconds", report))

    backend = os.environ.get("BUDDY_BACKEND_URL", backend) or backend
    token = os.environ.get("BUDDY_AUTH_TOKEN", token) or token

    if getattr(args, "backend_url", None):
        backend = args.backend_url
    if getattr(args, "auth_token", None):
        token = args.auth_token
    if getattr(args, "poll_interval", None):
        poll = args.poll_interval
    if getattr(args, "report_interval", None):
        report = args.report_interval

    if not backend or not token:
        sys.exit(
            "Missing config. Either set BUDDY_BACKEND_URL + BUDDY_AUTH_TOKEN env vars, "
            f"or create {CONFIG_PATH} with backend_url + auth_token, or pass --backend-url / --auth-token."
        )
    return CLIConfig(
        backend_url=backend.rstrip("/"),
        auth_token=token,
        poll_interval_seconds=poll,
        report_interval_seconds=report,
    )


def _add_common_flags(p: argparse.ArgumentParser) -> None:
    p.add_argument("--backend-url")
    p.add_argument("--auth-token")
    p.add_argument("--poll-interval", type=int, dest="poll_interval")
    p.add_argument("--report-interval", type=int, dest="report_interval")


def cmd_run(args: argparse.Namespace) -> None:
    logging.basicConfig(
        format="%(asctime)s %(levelname)-5s %(name)s %(message)s",
        level=logging.INFO,
    )
    cfg = _load_cli_config(args)
    agent = Agent(
        AgentConfig(
            backend_url=cfg.backend_url,
            auth_token=cfg.auth_token,
            poll_interval_seconds=cfg.poll_interval_seconds,
            report_interval_seconds=cfg.report_interval_seconds,
        )
    )
    try:
        agent.run_forever()
    except KeyboardInterrupt:
        print()
        print("stopped")
    finally:
        agent.close()


def cmd_ping(args: argparse.Namespace) -> None:
    cfg = _load_cli_config(args)
    adapter = get_adapter()
    snap = adapter.snapshot()
    cat = categorize(snap.process_name) if snap.process_name else "idle"
    print(f"platform:        {adapter.name}")
    print(f"process_name:    {snap.process_name!r}")
    print(f"window_title:    {snap.window_title!r}  (NOT sent upstream)")
    print(f"category:        {cat}")
    print(f"idle_seconds:    {snap.idle_seconds}")

    agent = Agent(AgentConfig(backend_url=cfg.backend_url, auth_token=cfg.auth_token))
    try:
        sid, distractors, poll = agent.status()
        print(f"active_session:  {sid}")
        print(f"distractor_cats: {sorted(distractors)}")
        print(f"poll_interval:   {poll}s")
    finally:
        agent.close()


def cmd_categorize(args: argparse.Namespace) -> None:
    if args.category not in KNOWN_CATEGORIES_FALLBACK:
        sys.exit(
            f"Category {args.category!r} is not in the known set. "
            f"Allowed: {', '.join(KNOWN_CATEGORIES_FALLBACK)}"
        )
    add_user_mapping(args.process, args.category)
    print(f"mapped {args.process!r} → {args.category}")


def cmd_show_config(args: argparse.Namespace) -> None:
    cfg = _load_cli_config(args)
    print(f"backend_url:    {cfg.backend_url}")
    print(f"auth_token:     {'*' * 8}{cfg.auth_token[-4:] if len(cfg.auth_token) >= 4 else ''}")
    print(f"poll_interval:  {cfg.poll_interval_seconds}s")
    print(f"report_interval: {cfg.report_interval_seconds}s")
    print(f"config_path:    {CONFIG_PATH}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="buddy-agent")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_run = sub.add_parser("run", help="Run the agent in the foreground.")
    _add_common_flags(p_run)
    p_run.set_defaults(func=cmd_run)

    p_ping = sub.add_parser("ping", help="One-shot diagnostic snapshot.")
    _add_common_flags(p_ping)
    p_ping.set_defaults(func=cmd_ping)

    p_cat = sub.add_parser("categorize", help="Add a process → category mapping.")
    p_cat.add_argument("process", help="Executable name, e.g. 'spotify.exe'")
    p_cat.add_argument(
        "category",
        help=f"One of: {', '.join(KNOWN_CATEGORIES_FALLBACK)}",
    )
    p_cat.set_defaults(func=cmd_categorize)

    p_show = sub.add_parser("show-config", help="Print effective config.")
    _add_common_flags(p_show)
    p_show.set_defaults(func=cmd_show_config)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
