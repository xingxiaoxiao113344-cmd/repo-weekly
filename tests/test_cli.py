"""End-to-end local command tests; these never contact GitHub."""

from contextlib import redirect_stderr, redirect_stdout
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from repo_weekly.cli import main


def snapshot_data():
    return {
        "schema_version": 1,
        "repository": {
            "full_name": "example/demo-repository",
            "html_url": "https://github.com/example/demo-repository",
            "description": "Fictional test data",
        },
        "window": {
            "since": "2026-10-15T00:00:00Z",
            "until": "2026-10-22T00:00:00Z",
        },
        "generated_at": "2026-10-22T00:00:00Z",
        "issues": [],
        "pull_requests": [],
        "releases": [],
        "coverage": {"complete": True, "warnings": []},
    }


class CLITests(unittest.TestCase):
    def run_cli(self, arguments):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = main(arguments)
        return code, stdout.getvalue(), stderr.getvalue()

    def write_snapshot(self, directory, data=None):
        path = Path(directory) / "snapshot.json"
        path.write_text(json.dumps(data or snapshot_data()), encoding="utf-8")
        return str(path)

    def test_json_works_before_or_after_the_command(self):
        for arguments in (["--json", "demo"], ["demo", "--json"]):
            with self.subTest(arguments=arguments):
                code, stdout, _ = self.run_cli(arguments)
                self.assertEqual(code, 0)
                payload = json.loads(stdout)
                self.assertTrue(payload["ok"])
                self.assertIn("markdown", payload["data"])

    def test_demo_is_explicitly_fictional_and_does_not_call_the_api(self):
        with patch("repo_weekly.github.GitHubClient.get", side_effect=AssertionError("Unexpected network")):
            code, stdout, _ = self.run_cli(["--json", "demo"])
        self.assertEqual(code, 0)
        report = json.loads(stdout)["data"]["markdown"].lower()
        self.assertRegex(report, r"fictional|synthetic|demonstration")

    def run_with_legacy_output_encoding(self, arguments):
        environment = os.environ.copy()
        environment["PYTHONIOENCODING"] = "cp1252:strict"
        environment["PYTHONUTF8"] = "0"
        result = subprocess.run(
            [sys.executable, "-m", "repo_weekly", *arguments],
            env=environment,
            capture_output=True,
            timeout=15,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        output = result.stdout.decode("utf-8")
        self.assertIn("≤", output)
        self.assertIn("修复中文输出的编码说明", output)
        return output

    def test_markdown_output_is_utf8_when_environment_uses_cp1252(self):
        self.run_with_legacy_output_encoding(["demo", "--lang", "en"])

    def test_json_output_is_utf8_when_environment_uses_cp1252(self):
        output = self.run_with_legacy_output_encoding(["--json", "demo", "--lang", "zh"])
        self.assertTrue(json.loads(output)["ok"])

    def test_offline_doctor_reports_no_network_check(self):
        with patch.dict(os.environ, {}, clear=True), patch(
            "repo_weekly.github.GitHubClient.get", side_effect=AssertionError("Unexpected network")
        ):
            code, stdout, _ = self.run_cli(["doctor", "--offline", "--json"])
        self.assertEqual(code, 0)
        data = json.loads(stdout)["data"]
        self.assertTrue(data["offline"])
        self.assertTrue(data["fixture_available"])
        self.assertFalse(data["network_checked"])
        self.assertFalse(data["auth_available"])

    def test_doctor_does_not_print_authentication_token(self):
        token = "test-token-that-must-never-appear"
        with patch.dict(os.environ, {"GITHUB_TOKEN": token}, clear=True):
            code, stdout, stderr = self.run_cli(["--json", "doctor", "--offline"])
        self.assertEqual(code, 0)
        self.assertNotIn(token, stdout + stderr)
        data = json.loads(stdout)["data"]
        self.assertTrue(data["auth_available"])
        self.assertEqual(data["auth_source"], "GITHUB_TOKEN")

    def test_unknown_command_has_structured_json_error(self):
        code, stdout, stderr = self.run_cli(["--json", "not-a-command"])
        self.assertEqual(code, 2)
        payload = json.loads(stdout)
        self.assertFalse(payload["ok"])
        self.assertIn("code", payload["error"])
        self.assertIn("message", payload["error"])
        self.assertNotIn("Traceback", stdout + stderr)

    def test_offline_report_includes_snapshot_counts_and_markdown(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_snapshot(directory)
            with patch("repo_weekly.github.GitHubClient.get", side_effect=AssertionError("Unexpected network")):
                code, stdout, _ = self.run_cli([
                    "report", "example/demo-repository", "--data", path, "--json"
                ])
        self.assertEqual(code, 0)
        data = json.loads(stdout)["data"]
        self.assertEqual(data["summary"]["issues_opened"], 0)
        self.assertEqual(data["snapshot"]["repository"]["full_name"], "example/demo-repository")
        self.assertIn("markdown", data)
        self.assertIn("output", data)

    def test_explicit_window_flags_cannot_be_ignored_with_saved_data(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_snapshot(directory)
            for flags in (["--days", "3"], ["--until", "2026-10-22"]):
                with self.subTest(flags=flags):
                    code, stdout, _ = self.run_cli([
                        "--json", "report", "example/demo-repository", "--data", path, *flags
                    ])
                    self.assertEqual(code, 2)
                    self.assertFalse(json.loads(stdout)["ok"])

    def test_existing_output_is_preserved_without_force(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "weekly.md"
            output.write_text("keep this existing report", encoding="utf-8")
            code, stdout, _ = self.run_cli(["demo", "--json", "--output", str(output)])
            self.assertNotEqual(code, 0)
            self.assertFalse(json.loads(stdout)["ok"])
            self.assertEqual(output.read_text(encoding="utf-8"), "keep this existing report")

    def test_force_can_replace_existing_output(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "weekly.md"
            output.write_text("old report", encoding="utf-8")
            code, stdout, _ = self.run_cli([
                "demo", "--json", "--lang", "zh", "--output", str(output), "--force"
            ])
            self.assertEqual(code, 0)
            self.assertTrue(json.loads(stdout)["ok"])
            self.assertNotEqual(output.read_text(encoding="utf-8"), "old report")

    def test_partial_snapshot_still_emits_report_with_distinct_exit_code(self):
        with tempfile.TemporaryDirectory() as directory:
            snapshot = snapshot_data()
            snapshot["coverage"] = {"complete": False, "warnings": ["Page limit reached"]}
            path = self.write_snapshot(directory, snapshot)
            code, stdout, _ = self.run_cli([
                "--json", "report", "example/demo-repository", "--data", path
            ])
        self.assertEqual(code, 3)
        data = json.loads(stdout)["data"]
        self.assertFalse(data["snapshot"]["coverage"]["complete"])
        self.assertIn("Page limit reached", data["markdown"])

    def test_invalid_data_produces_an_error_instead_of_a_traceback(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "broken.json"
            path.write_text("{not json", encoding="utf-8")
            code, stdout, stderr = self.run_cli([
                "report", "example/demo-repository", "--data", str(path), "--json"
            ])
        self.assertNotEqual(code, 0)
        self.assertFalse(json.loads(stdout)["ok"])
        self.assertNotIn("Traceback", stdout + stderr)

    def test_invalid_item_state_is_reported_as_structured_input_error(self):
        with tempfile.TemporaryDirectory() as directory:
            snapshot = snapshot_data()
            snapshot["issues"] = [{
                "number": 1,
                "title": "Invalid saved state",
                "html_url": "https://github.com/example/demo-repository/issues/1",
                "state": [],
                "created_at": "2026-10-16T00:00:00Z",
                "updated_at": "2026-10-17T00:00:00Z",
                "closed_at": None,
            }]
            path = self.write_snapshot(directory, snapshot)
            code, stdout, stderr = self.run_cli([
                "report", "example/demo-repository", "--data", path, "--json"
            ])
        self.assertEqual(code, 2)
        self.assertFalse(json.loads(stdout)["ok"])
        self.assertNotIn("Traceback", stdout + stderr)


if __name__ == "__main__":
    unittest.main()
