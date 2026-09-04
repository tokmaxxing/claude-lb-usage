from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FORMATTER = ROOT / "plugins" / "claude-lb-usage" / "bin" / "claude-lb-usage"

spec = importlib.util.spec_from_file_location("claude_lb_usage_installer", ROOT / "install.py")
if spec is None or spec.loader is None:
    raise RuntimeError("Could not load install.py")
installer = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = installer
spec.loader.exec_module(installer)


class InstallerTests(unittest.TestCase):
    def test_shell_entrypoint_installs_and_uninstalls(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config_dir = Path(temporary) / "claude-config"
            env = {**os.environ, "CLAUDE_CONFIG_DIR": str(config_dir)}

            installed = subprocess.run(
                [ROOT / "install.sh"],
                check=True,
                capture_output=True,
                text=True,
                env=env,
            )
            self.assertIn("Installed claude-lb usage integration", installed.stdout)
            self.assertTrue((config_dir / installer.FORMATTER_NAME).is_file())

            removed = subprocess.run(
                [ROOT / "install.sh", "--uninstall"],
                check=True,
                capture_output=True,
                text=True,
                env=env,
            )
            self.assertIn("Removed claude-lb usage integration", removed.stdout)
            self.assertFalse((config_dir / installer.FORMATTER_NAME).exists())

    def test_user_install_preserves_unrelated_settings(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            claude_dir = home / ".claude"
            claude_dir.mkdir()
            settings_path = claude_dir / "settings.json"
            settings_path.write_text(
                json.dumps(
                    {
                        "theme": "dark",
                        "env": {
                            "ANTHROPIC_BASE_URL": "https://claude-lb.example.com",
                            "ANTHROPIC_AUTH_TOKEN": "existing-secret",
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            result = installer.install(home=home)

            settings = json.loads(settings_path.read_text(encoding="utf-8"))
            self.assertEqual(settings["theme"], "dark")
            self.assertEqual(
                settings["env"],
                {
                    "ANTHROPIC_BASE_URL": "https://claude-lb.example.com",
                    "ANTHROPIC_AUTH_TOKEN": "existing-secret",
                },
            )
            self.assertEqual(settings["statusLine"]["refreshInterval"], 60)
            self.assertEqual(settings["statusLine"]["command"], str(result.formatter_path))
            self.assertEqual(result.formatter_path.stat().st_mode & 0o777, 0o700)

    def test_project_install_uses_project_claude_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = root / "project"
            project.mkdir()

            result = installer.install(scope="project", cwd=project, home=root)

            self.assertEqual(result.settings_path, project / ".claude" / "settings.json")
            self.assertEqual(result.formatter_path, project / ".claude" / installer.FORMATTER_NAME)

    def test_foreign_statusline_is_not_replaced(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            claude_dir = home / ".claude"
            claude_dir.mkdir()
            settings_path = claude_dir / "settings.json"
            original = '{"statusLine": {"type": "command", "command": "custom-status"}}\n'
            settings_path.write_text(original, encoding="utf-8")

            with self.assertRaisesRegex(installer.SetupError, "--no-statusline"):
                installer.install(home=home)

            self.assertEqual(settings_path.read_text(encoding="utf-8"), original)
            self.assertFalse((claude_dir / installer.FORMATTER_NAME).exists())

    def test_no_statusline_installs_formatter_without_touching_settings(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            claude_dir = home / ".claude"
            claude_dir.mkdir()
            settings_path = claude_dir / "settings.json"
            original = '{"statusLine": {"type": "command", "command": "custom-status"}}\n'
            settings_path.write_text(original, encoding="utf-8")

            result = installer.install(home=home, statusline=False)

            self.assertFalse(result.statusline_installed)
            self.assertTrue(result.formatter_path.is_file())
            self.assertEqual(settings_path.read_text(encoding="utf-8"), original)

    def test_uninstall_removes_only_managed_content(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            claude_dir = home / ".claude"
            claude_dir.mkdir()
            settings_path = claude_dir / "settings.json"
            settings_path.write_text('{"theme": "dark"}\n', encoding="utf-8")
            result = installer.install(home=home)

            removed = installer.uninstall(home=home)

            self.assertIn(result.formatter_path, removed)
            self.assertFalse(result.formatter_path.exists())
            self.assertEqual(json.loads(settings_path.read_text(encoding="utf-8")), {"theme": "dark"})

    def test_install_removes_legacy_managed_skill(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            legacy_skill = home / ".claude" / "skills" / "lb-usage" / "SKILL.md"
            legacy_skill.parent.mkdir(parents=True)
            legacy_skill.write_text(f"<!-- {installer.MANAGED_MARKER} -->\n", encoding="utf-8")

            installer.install(home=home, statusline=False)

            self.assertFalse(legacy_skill.exists())


class _UsageHandler(BaseHTTPRequestHandler):
    request_path = ""
    api_key = ""
    payload: dict[str, Any] = {
        "request_count": 2,
        "total_tokens": 1500,
        "cached_input_tokens": 10,
        "total_cost_usd": 0.25,
        "limits": [
            {
                "limit_type": "cost_usd",
                "limit_window": "monthly",
                "max_value": 10_000_000,
                "current_value": 2_500_000,
                "remaining_value": 7_500_000,
                "used_percent": 25,
                "model_filter": None,
                "reset_at": "2026-10-01T00:00:00Z",
            }
        ],
    }

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        type(self).request_path = self.path
        type(self).api_key = self.headers.get("x-api-key", "")
        body = json.dumps(self.payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        return


class _RedirectSourceHandler(BaseHTTPRequestHandler):
    target_url = ""

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        self.send_response(302)
        self.send_header("Location", self.target_url)
        self.end_headers()

    def log_message(self, format: str, *args: object) -> None:
        return


class _RedirectTargetHandler(BaseHTTPRequestHandler):
    request_count = 0
    api_key = ""

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        type(self).request_count += 1
        type(self).api_key = self.headers.get("x-api-key", "")
        self.send_response(204)
        self.end_headers()

    def log_message(self, format: str, *args: object) -> None:
        return


class FormatterTests(unittest.TestCase):
    def test_formatter_uses_api_key_and_renders_compact_full_and_json(self) -> None:
        server = ThreadingHTTPServer(("127.0.0.1", 0), _UsageHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            env = os.environ.copy()
            for name in (
                "CLAUDE_PLUGIN_OPTION_BASE_URL",
                "CLAUDE_PLUGIN_OPTION_API_KEY",
                "ANTHROPIC_BASE_URL",
                "ANTHROPIC_AUTH_TOKEN",
                "ANTHROPIC_API_KEY",
            ):
                env.pop(name, None)
            env["CLAUDE_LB_BASE_URL"] = f"http://127.0.0.1:{server.server_port}/v1"
            env["CLAUDE_LB_API_KEY"] = "test-secret"

            compact = subprocess.run([FORMATTER], check=True, capture_output=True, text=True, env=env)
            full = subprocess.run([FORMATTER, "--full"], check=True, capture_output=True, text=True, env=env)
            raw = subprocess.run([FORMATTER, "--json"], check=True, capture_output=True, text=True, env=env)
            hook = subprocess.run([FORMATTER, "--hook"], check=True, capture_output=True, text=True, env=env)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

        self.assertEqual(compact.stdout.strip(), "LB: $7.5 left · 25% used")
        self.assertIn("Claude LB Usage", full.stdout)
        self.assertIn("Current month (all models)", full.stdout)
        self.assertIn("████████░░░░░░░░░░░░░░░░░░░░░░░░  25% used", full.stdout)
        self.assertIn("$2.50 / $10.00 spent · $7.50 left", full.stdout)
        self.assertNotIn("Requests:", full.stdout)
        self.assertEqual(json.loads(raw.stdout), _UsageHandler.payload)
        hook_result = json.loads(hook.stdout)
        self.assertEqual(hook_result["decision"], "block")
        self.assertIn("Claude LB Usage", hook_result["reason"])
        self.assertIn("$2.50 / $10.00 spent · $7.50 left", hook_result["reason"])
        self.assertEqual(_UsageHandler.request_path, "/v1/usage/self")
        self.assertEqual(_UsageHandler.api_key, "test-secret")

    def test_formatter_does_not_forward_api_key_through_redirects(self) -> None:
        target = ThreadingHTTPServer(("127.0.0.1", 0), _RedirectTargetHandler)
        source = ThreadingHTTPServer(("127.0.0.1", 0), _RedirectSourceHandler)
        _RedirectSourceHandler.target_url = f"http://127.0.0.1:{target.server_port}/capture"
        _RedirectTargetHandler.request_count = 0
        _RedirectTargetHandler.api_key = ""
        threads = [
            threading.Thread(target=target.serve_forever, daemon=True),
            threading.Thread(target=source.serve_forever, daemon=True),
        ]
        for thread in threads:
            thread.start()
        try:
            env = os.environ.copy()
            env["CLAUDE_LB_BASE_URL"] = f"http://127.0.0.1:{source.server_port}"
            env["CLAUDE_LB_API_KEY"] = "must-not-be-forwarded"
            result = subprocess.run([FORMATTER], check=True, capture_output=True, text=True, env=env)
        finally:
            source.shutdown()
            target.shutdown()
            source.server_close()
            target.server_close()
            for thread in threads:
                thread.join(timeout=2)

        self.assertEqual(result.stdout.strip(), "LB: usage unavailable")
        self.assertEqual(_RedirectTargetHandler.request_count, 0)
        self.assertEqual(_RedirectTargetHandler.api_key, "")

    def test_formatter_accepts_secure_plugin_options(self) -> None:
        env = os.environ.copy()
        for name in ("CLAUDE_LB_BASE_URL", "CLAUDE_LB_API_KEY", "ANTHROPIC_BASE_URL", "ANTHROPIC_AUTH_TOKEN"):
            env.pop(name, None)
        env["CLAUDE_PLUGIN_OPTION_BASE_URL"] = "http://127.0.0.1:1"
        env["CLAUDE_PLUGIN_OPTION_API_KEY"] = "plugin-secret"

        result = subprocess.run([FORMATTER], check=True, capture_output=True, text=True, env=env)

        self.assertEqual(result.stdout.strip(), "LB: usage unavailable")
        self.assertNotIn("plugin-secret", result.stdout)
        self.assertNotIn("plugin-secret", result.stderr)


class MetadataTests(unittest.TestCase):
    def test_marketplace_and_plugin_metadata_are_consistent(self) -> None:
        marketplace = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
        manifest = json.loads(
            (ROOT / "plugins" / "claude-lb-usage" / ".claude-plugin" / "plugin.json").read_text(
                encoding="utf-8"
            )
        )

        entry = marketplace["plugins"][0]
        self.assertEqual(entry["name"], manifest["name"])
        self.assertEqual(entry["version"], manifest["version"])
        self.assertNotIn("userConfig", manifest)
        skill = ROOT / "plugins" / "claude-lb-usage" / "skills" / "usage" / "SKILL.md"
        self.assertTrue(skill.is_file())
        hooks = json.loads(
            (ROOT / "plugins" / "claude-lb-usage" / "hooks" / "hooks.json").read_text(encoding="utf-8")
        )
        expansion = hooks["hooks"]["UserPromptExpansion"]
        self.assertEqual(expansion[0]["matcher"], "^claude-lb-usage:usage$")
        handler = expansion[0]["hooks"][0]
        self.assertEqual(handler["command"], "${CLAUDE_PLUGIN_ROOT}/bin/claude-lb-usage")
        self.assertEqual(handler["args"], ["--hook"])


if __name__ == "__main__":
    unittest.main()
