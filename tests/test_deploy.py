"""Checks that the project is configured correctly for Render + Gunicorn.

Run from the project root:
    python3 -m unittest discover -s tests -t . -v
"""

import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def render_value(key):
    """Read a top-level 'key: value' from the single service in render.yaml."""
    text = (ROOT / "render.yaml").read_text(encoding="utf-8")
    match = re.search(rf"^\s+(?:-\s+)?{key}:\s*(.+?)\s*(#.*)?$", text, re.MULTILINE)
    return match.group(1) if match else None


class RequirementsTests(unittest.TestCase):
    def test_flask_and_gunicorn_are_listed(self):
        names = [re.split(r"[<>=!~ ]", line, maxsplit=1)[0].lower()
                 for line in (ROOT / "requirements.txt").read_text().splitlines()
                 if line.strip() and not line.startswith("#")]
        self.assertIn("flask", names)
        self.assertIn("gunicorn", names)

    def test_python_version_is_pinned(self):
        version = (ROOT / ".python-version").read_text().strip()
        self.assertRegex(version, r"^3\.\d+(\.\d+)?$")


class RenderBlueprintTests(unittest.TestCase):
    def test_service_basics(self):
        self.assertEqual(render_value("type"), "web")
        self.assertEqual(render_value("runtime"), "python")
        self.assertEqual(render_value("plan"), "free")
        self.assertEqual(render_value("buildCommand"), "pip install -r requirements.txt")
        self.assertEqual(render_value("healthCheckPath"), "/")

    def test_start_command(self):
        start = render_value("startCommand")
        self.assertTrue(start.startswith("gunicorn "), start)
        self.assertIn("--bind 0.0.0.0:$PORT", start)
        # Games live in one process's memory, so there must be exactly one worker.
        self.assertIn("--workers 1", start)
        self.assertTrue(start.endswith(" server:app"), start)

    def test_start_command_target_exists(self):
        import server
        self.assertTrue(callable(server.app))

    def test_health_check_path_responds(self):
        import server
        response = server.app.test_client().get(render_value("healthCheckPath"))
        self.addCleanup(response.close)
        self.assertEqual(response.status_code, 200)


class ProductionSafetyTests(unittest.TestCase):
    def test_debug_is_off_when_imported(self):
        # Gunicorn imports server:app and never runs the __main__ block.
        import server
        self.assertFalse(server.app.debug)

    def test_no_hardcoded_debug_true(self):
        source = (ROOT / "server.py").read_text()
        self.assertNotRegex(source, r"debug\s*=\s*True")

    def test_no_secrets_or_env_files_tracked(self):
        for name in [".env", ".env.local", "secrets.json"]:
            self.assertFalse((ROOT / name).exists(), f"{name} should not be in the repo")
        self.assertIn(".env", (ROOT / ".gitignore").read_text())


if __name__ == "__main__":
    unittest.main()
