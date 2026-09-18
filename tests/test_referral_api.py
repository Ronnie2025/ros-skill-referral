#!/usr/bin/env python3
import json
import importlib.util
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "site"))


class ReferralApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["REFERRAL_ROOT"] = self.tmp.name
        os.environ["REFERRAL_DB"] = str(Path(self.tmp.name) / "events.db")
        os.environ["REFERRAL_SALT_FILE"] = str(Path(self.tmp.name) / "salt")
        os.environ["REFERRAL_PUBLIC"] = str(ROOT / "site" / "public")
        os.environ["REFERRAL_HOST"] = "127.0.0.1"
        os.environ["REFERRAL_PORT"] = "0"
        for module in list(sys.modules):
            if module == "referral_api" or module.startswith("referral_api."):
                del sys.modules[module]
        import referral_api

        self.api = referral_api
        self.server = referral_api.ThreadingHTTPServer(("127.0.0.1", 0), referral_api.Handler)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        time.sleep(0.05)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.api.CONN.close()
        self.tmp.cleanup()

    def url(self, path: str) -> str:
        return f"http://127.0.0.1:{self.port}{path}"

    def post(self, payload: dict, path: str = "/referral/e"):
        req = urllib.request.Request(
            self.url(path),
            data=json.dumps(payload).encode("utf-8"),
            headers={"content-type": "application/json"},
            method="POST",
        )
        return urllib.request.urlopen(req, timeout=3)

    def test_health_and_dashboard(self):
        with urllib.request.urlopen(self.url("/referral/health"), timeout=3) as res:
            self.assertEqual(res.status, 200)
            self.assertEqual(json.loads(res.read())["ok"], True)
        with urllib.request.urlopen(self.url("/referral/"), timeout=3) as res:
            self.assertIn("去重", res.read().decode("utf-8"))

    def test_dedupes_install_environments_and_retries(self):
        first = {
            "event": "setup_success",
            "referrer": "dontbesilent",
            "source_skill": "dbs-recommend-ros-clip",
            "target_skill": "ros-clip-draft",
            "campaign": "dbs-to-ros-202609",
            "installation_id": "env-1",
            "event_id": "evt-1",
        }
        self.assertEqual(self.post(first).status, 204)
        retry = dict(first)
        retry["event_id"] = "evt-1"
        self.assertEqual(self.post(retry).status, 204)
        second_same_env = dict(first)
        second_same_env["event_id"] = "evt-2"
        self.assertEqual(self.post(second_same_env).status, 204)
        other = dict(first)
        other.update({"installation_id": "env-2", "event_id": "evt-3"})
        self.assertEqual(self.post(other).status, 204)
        with urllib.request.urlopen(self.url("/referral/stats.json"), timeout=3) as res:
            stats = json.loads(res.read())
        self.assertEqual(stats["totals"]["install_environments"], 2)
        self.assertEqual(stats["totals"]["events"], 3)
        self.assertEqual(stats["by_referrer"][0]["referrer"], "dontbesilent")
        self.assertEqual(stats["by_referrer"][0]["environments"], 2)

    def test_filters_test_a_to_test_b_without_legacy_events(self):
        events = [
            ("old", "dbs-recommend-ros-clip", "ros-clip-draft"),
            ("new", "test-a", "test-b"),
        ]
        for event_id, source, target in events:
            self.assertEqual(self.post({
                "event": "setup_success",
                "referrer": "dontbesilent",
                "source_skill": source,
                "target_skill": target,
                "installation_id": event_id,
                "event_id": event_id,
            }).status, 204)
        with urllib.request.urlopen(
            self.url("/referral/stats.json?source_skill=test-a&target_skill=test-b"), timeout=3
        ) as res:
            stats = json.loads(res.read())
        self.assertEqual(stats["filters"], { "source_skill": "test-a", "target_skill": "test-b", "referrer": "", "campaign": ""})
        self.assertEqual(stats["totals"]["install_environments"], 1)
        self.assertEqual(stats["totals"]["events"], 1)
        self.assertEqual(stats["by_referrer"][0]["target_skill"], "test-b")

    def test_http_referrer_campaign_filters_and_required_target(self):
        self.assertEqual(self.post({
            "event": "setup_success", "installation_id": "env-new", "event_id": "evt-new",
            "source_skill": "outline", "target_skill": "slides", "referrer": "creator",
            "campaign": "demo",
        }).status, 204)
        with urllib.request.urlopen(self.url(
            "/referral/stats.json?referrer=creator&campaign=demo&source_skill=outline&target_skill=slides"
        ), timeout=3) as res:
            stats = json.loads(res.read())
        self.assertEqual(stats["totals"]["install_environments"], 1)
        self.assertEqual(stats["filters"]["referrer"], "creator")
        self.assertEqual(stats["filters"]["campaign"], "demo")
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self.post({"event": "setup_success", "installation_id": "env", "event_id": "evt"})
        self.assertEqual(ctx.exception.code, 400)
        ctx.exception.close()
        for query in ["referrer=../bad", "campaign=one&campaign=two"]:
            with self.subTest(query=query), self.assertRaises(urllib.error.HTTPError) as ctx:
                urllib.request.urlopen(self.url("/referral/stats.json?" + query), timeout=3)
            self.assertEqual(ctx.exception.code, 400)
            ctx.exception.close()

    def test_rejects_invalid_and_oversized_fields(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self.post({"event": "hack", "installation_id": "a", "event_id": "b"})
        self.assertEqual(ctx.exception.code, 400)
        ctx.exception.close()
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self.post(
                {
                    "event": "setup_success",
                    "installation_id": "../etc/passwd",
                    "event_id": "evt-x",
                }
            )
        self.assertEqual(ctx.exception.code, 400)
        ctx.exception.close()

    def test_client_reports_once_and_respects_consent_file(self):
        ref_file = Path(self.tmp.name) / "referral.json"
        ref_file.write_text(json.dumps({
            "referrer": "dontbesilent",
            "source_skill": "dbs-recommend-ros-clip",
            "campaign": "test",
        }), encoding="utf-8")
        env = os.environ.copy()
        env.update({
            "ROS_REFERRAL_ENDPOINT": self.url("/referral/e"),
            "ROS_REFERRAL_FILE": str(ref_file),
            "ROS_CLIP_CACHE": str(Path(self.tmp.name) / "client-cache"),
        })
        script = ROOT / "skills" / "ros-clip-draft" / "scripts" / "first-run.sh"
        for _ in range(2):
            subprocess.run(["bash", str(script)], env=env, check=True, capture_output=True, text=True)
        ref_file.unlink()
        subprocess.run(["bash", str(script)], env=env, check=True, capture_output=True, text=True)
        with urllib.request.urlopen(self.url("/referral/stats.json"), timeout=3) as res:
            stats = json.loads(res.read())
        self.assertEqual(stats["totals"]["install_environments"], 1)
        self.assertEqual(stats["totals"]["events"], 1)

    def test_client_uses_python_when_curl_tls_fails(self):
        ref_file = Path(self.tmp.name) / "referral.json"
        ref_file.write_text(json.dumps({
            "referrer": "dontbesilent",
            "source_skill": "dbs-recommend-ros-clip",
        }), encoding="utf-8")
        fake_bin = Path(self.tmp.name) / "bin"
        fake_bin.mkdir()
        fake_curl = fake_bin / "curl"
        fake_curl.write_text("#!/bin/sh\nexit 35\n", encoding="utf-8")
        fake_curl.chmod(0o755)
        env = os.environ.copy()
        env.update({
            "PATH": str(fake_bin) + os.pathsep + env["PATH"],
            "ROS_REFERRAL_ENDPOINT": self.url("/referral/e"),
            "ROS_REFERRAL_FILE": str(ref_file),
            "ROS_CLIP_CACHE": str(Path(self.tmp.name) / "client-cache"),
        })
        script = ROOT / "skills" / "ros-clip-draft" / "scripts" / "report.sh"
        result = subprocess.run(
            ["bash", str(script), "setup_success"],
            env=env, check=True, capture_output=True, text=True,
        )
        self.assertIn("reported setup_success", result.stdout)
        with urllib.request.urlopen(self.url("/referral/stats.json"), timeout=3) as res:
            stats = json.loads(res.read())
        self.assertEqual(stats["totals"]["install_environments"], 1)


class ReferralStatsTests(unittest.TestCase):
    """Exercise attribution without opening a network port."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {
            "REFERRAL_DB": str(Path(self.tmp.name) / "events.db"),
        })
        self.env.start()
        spec = importlib.util.spec_from_file_location("referral_stats_test", ROOT / "site" / "referral_api.py")
        self.api = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.api)
        self.serial = 0

    def tearDown(self):
        self.api.CONN.close()
        self.env.stop()
        self.tmp.cleanup()

    def event(self, installation="env-1", target="editor", source="writer",
              referrer="alice", campaign="launch", event="setup_success", ts=None):
        self.serial += 1
        payload = self.api.parse_event(json.dumps({
            "event_id": f"evt-{self.serial}", "installation_id": installation,
            "target_skill": target, "source_skill": source, "referrer": referrer,
            "campaign": campaign, "event": event,
        }).encode())
        with patch.object(self.api, "utc_now", return_value=ts or "2026-09-18T00:00:00Z"):
            self.api.insert_event(payload, "")

    def test_any_source_target_and_combined_filters(self):
        self.event()
        self.event(target="publisher", source="editor", referrer="bob", campaign="autumn")
        self.event(installation="env-2", referrer="bob")
        all_stats = self.api.stats_payload()
        self.assertEqual(all_stats["totals"]["install_environments"], 3)
        for field, value, expected in [
            ("target_skill", "editor", 2), ("source_skill", "editor", 1),
            ("referrer", "bob", 2), ("campaign", "autumn", 1),
        ]:
            self.assertEqual(self.api.stats_payload(**{field: value})["totals"]["install_environments"], expected)
        filtered = self.api.stats_payload(referrer="bob", target_skill="editor", campaign="launch")
        self.assertEqual(filtered["totals"]["install_environments"], 1)
        self.assertEqual(filtered["options"], all_stats["options"])
        self.assertEqual(filtered["options"]["target_skill"], ["editor", "publisher"])
        self.assertEqual(self.api.stats_payload(referrer="unknown")["totals"]["install_environments"], 0)

    def test_first_attribution_survives_later_source_and_campaign(self):
        self.event()  # Same timestamps deliberately test receipt-order tie breaking.
        self.event(source="other", referrer="bob", campaign="second")
        self.event(source="other", referrer="bob", campaign="second",
                   event="first_use_success", ts="2026-09-18T01:00:00Z")
        original = self.api.stats_payload(source_skill="writer", referrer="alice", campaign="launch")
        self.assertEqual(original["totals"], {"install_environments": 1, "first_use_environments": 1, "events": 1})
        self.assertEqual(original["by_referrer"][0]["first_use_environments"], 1)
        self.assertEqual(original["by_referrer"][0]["last_seen"], "2026-09-18T01:00:00Z")
        later = self.api.stats_payload(source_skill="other")
        self.assertEqual(later["totals"], {"install_environments": 0, "first_use_environments": 0, "events": 2})
        self.assertEqual(later["by_referrer"], [])
        self.assertEqual(later["options"]["referrer"], ["alice", "bob"])

    def test_first_use_requires_install_and_same_target(self):
        self.event(event="install_attempt")
        self.event(event="first_use_success")
        self.event(target="publisher")
        self.assertEqual(self.api.stats_payload()["totals"]["first_use_environments"], 0)
        self.event()
        self.event(event="first_use_success")
        self.assertEqual(self.api.stats_payload()["totals"]["first_use_environments"], 1)

    def test_options_include_attempts_exclude_empty_values(self):
        self.event(source="", campaign="", referrer="", event="install_attempt")
        self.assertEqual(self.api.stats_payload()["options"], {
            "target_skill": ["editor"], "source_skill": [], "referrer": [], "campaign": [],
        })

    def test_target_is_required_and_valid(self):
        for target in [None, "", " ", "../bad", "x" * 81]:
            with self.subTest(target=target), self.assertRaises(ValueError):
                self.api.parse_event(json.dumps({
                    "event": "setup_success", "installation_id": "env", "event_id": "evt",
                    "target_skill": target,
                }).encode())


if __name__ == "__main__":
    unittest.main()
