#!/usr/bin/env python3
from __future__ import annotations

import argparse
import contextlib
import json
import os
import shlex
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

MANAGED_MARKER = "managed-by: claude-lb-usage"
FORMATTER_NAME = "claude-lb-usage-statusline"
REPOSITORY_ROOT = Path(__file__).resolve().parent
FORMATTER_SOURCE = REPOSITORY_ROOT / "plugins" / "claude-lb-usage" / "bin" / "claude-lb-usage"


class SetupError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class Installation:
    settings_path: Path
    skill_path: Path
    formatter_path: Path
    statusline_installed: bool


def install(
    *,
    scope: Literal["user", "project"] = "user",
    force: bool = False,
    statusline: bool = True,
    cwd: Path | None = None,
    home: Path | None = None,
    config_dir: Path | None = None,
) -> Installation:
    claude_dir = _claude_dir(scope=scope, cwd=cwd, home=home, config_dir=config_dir)
    settings_path = _settings_path(claude_dir)
    formatter_path = claude_dir / FORMATTER_NAME
    skill_path = claude_dir / "skills" / "lb-usage" / "SKILL.md"

    if not FORMATTER_SOURCE.is_file():
        raise SetupError(f"Bundled formatter is missing: {FORMATTER_SOURCE}")

    settings = _load_settings(settings_path)
    desired_statusline = _statusline_config(formatter_path)
    existing_statusline = settings.get("statusLine")
    if (
        statusline
        and existing_statusline is not None
        and existing_statusline != desired_statusline
        and not _is_managed_statusline(existing_statusline, formatter_path)
        and not force
    ):
        raise SetupError(
            f"Refusing to replace existing Claude Code statusLine in {settings_path}; "
            "use --no-statusline or rerun with --force."
        )

    _refuse_foreign_file(skill_path, "lb-usage skill", force=force)
    _refuse_foreign_file(formatter_path, "usage formatter", force=force)

    formatter = FORMATTER_SOURCE.read_text(encoding="utf-8")
    skill = _render_standalone_skill(formatter_path)
    if statusline:
        settings["statusLine"] = desired_statusline

    _atomic_write(formatter_path, formatter, mode=0o700)
    _atomic_write(skill_path, skill, mode=0o600)
    if statusline:
        _atomic_write(settings_path, json.dumps(settings, ensure_ascii=False, indent=2) + "\n", mode=0o600)

    return Installation(
        settings_path=settings_path,
        skill_path=skill_path,
        formatter_path=formatter_path,
        statusline_installed=statusline,
    )


def uninstall(
    *,
    scope: Literal["user", "project"] = "user",
    cwd: Path | None = None,
    home: Path | None = None,
    config_dir: Path | None = None,
) -> list[Path]:
    claude_dir = _claude_dir(scope=scope, cwd=cwd, home=home, config_dir=config_dir)
    settings_path = _settings_path(claude_dir)
    formatter_path = claude_dir / FORMATTER_NAME
    skill_path = claude_dir / "skills" / "lb-usage" / "SKILL.md"
    removed: list[Path] = []

    settings = _load_settings(settings_path)
    if _is_managed_statusline(settings.get("statusLine"), formatter_path):
        del settings["statusLine"]
        _atomic_write(settings_path, json.dumps(settings, ensure_ascii=False, indent=2) + "\n", mode=0o600)
        removed.append(settings_path)

    for path in (skill_path, formatter_path):
        if path.is_file() and MANAGED_MARKER in path.read_text(encoding="utf-8"):
            path.unlink()
            removed.append(path)

    _remove_empty_directory(skill_path.parent)
    _remove_empty_directory(skill_path.parent.parent)
    return removed


def _claude_dir(
    *,
    scope: Literal["user", "project"],
    cwd: Path | None,
    home: Path | None,
    config_dir: Path | None,
) -> Path:
    if scope == "project":
        return (cwd or Path.cwd()).resolve() / ".claude"
    if scope != "user":
        raise SetupError(f"Unsupported scope: {scope}")
    configured = config_dir or _configured_claude_dir()
    if configured is not None:
        return configured.expanduser().resolve()
    return (home or Path.home()).expanduser().resolve() / ".claude"


def _configured_claude_dir() -> Path | None:
    value = os.getenv("CLAUDE_CONFIG_DIR", "").strip()
    return Path(value) if value else None


def _settings_path(claude_dir: Path) -> Path:
    path = claude_dir / "settings.json"
    return path.resolve(strict=False) if path.is_symlink() else path


def _load_settings(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SetupError(f"Cannot read valid Claude Code settings from {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise SetupError(f"Claude Code settings must contain a JSON object: {path}")
    return cast(dict[str, object], value)


def _statusline_config(formatter_path: Path) -> dict[str, object]:
    return {
        "type": "command",
        "command": shlex.quote(str(formatter_path)),
        "padding": 0,
        "refreshInterval": 60,
    }


def _is_managed_statusline(value: object, formatter_path: Path) -> bool:
    return isinstance(value, dict) and value.get("command") == shlex.quote(str(formatter_path))


def _refuse_foreign_file(path: Path, description: str, *, force: bool) -> None:
    if not path.exists() or force:
        return
    try:
        managed = MANAGED_MARKER in path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SetupError(f"Cannot inspect existing {description} at {path}: {exc}") from exc
    if not managed:
        raise SetupError(f"Refusing to replace existing {description} at {path}; rerun with --force.")


def _render_standalone_skill(formatter_path: Path) -> str:
    command = f"{shlex.quote(str(formatter_path))} --full"
    return f"""---
name: lb-usage
description: Show this customer's claude-lb API-key usage, remaining limits, and reset times.
disable-model-invocation: true
---

<!-- {MANAGED_MARKER} -->

## Live claude-lb usage

!`{command}`

Return the live usage output above verbatim. Do not infer missing limits or substitute upstream account quota.
"""


def _atomic_write(path: Path, content: str, *, mode: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            delete=False,
        ) as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
            temporary_name = handle.name
        os.chmod(temporary_name, mode)
        os.replace(temporary_name, path)
        temporary_name = None
    finally:
        if temporary_name is not None:
            Path(temporary_name).unlink(missing_ok=True)


def _remove_empty_directory(path: Path) -> None:
    with contextlib.suppress(OSError):
        path.rmdir()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Install the standalone claude-lb usage integration for Claude Code.")
    parser.add_argument("--scope", choices=("user", "project"), default="user")
    parser.add_argument("--force", action="store_true", help="Replace foreign files or status-line configuration.")
    parser.add_argument("--no-statusline", action="store_true", help="Install /lb-usage without changing statusLine.")
    parser.add_argument(
        "--uninstall",
        action="store_true",
        help="Remove only files and settings managed by this installer.",
    )
    return parser


def main() -> None:
    args = _parser().parse_args()
    try:
        if args.uninstall:
            removed = uninstall(scope=args.scope)
            if removed:
                print("Removed claude-lb usage integration:")
                for path in removed:
                    print(f"- {path}")
            else:
                print("No managed claude-lb usage integration was found.")
            return

        result = install(
            scope=args.scope,
            force=args.force,
            statusline=not args.no_statusline,
        )
    except SetupError as exc:
        raise SystemExit(str(exc)) from exc

    print("Installed claude-lb usage integration:")
    print(f"- skill: {result.skill_path}")
    print(f"- formatter: {result.formatter_path}")
    if result.statusline_installed:
        print(f"- settings: {result.settings_path}")
    print("Launch Claude Code with CLAUDE_LB_BASE_URL and CLAUDE_LB_API_KEY set, then run /lb-usage.")


if __name__ == "__main__":
    main()
