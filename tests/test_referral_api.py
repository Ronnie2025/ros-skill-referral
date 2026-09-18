#!/usr/bin/env python3
import json
import os
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
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

    def test_rejects_invalid_and_oversized_fields(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self.post({"event": "hack", "installation_id": "a", "event_id": "b"})
        self.assertEqual(ctx.exception.code, 400)
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self.post(
                {
                    "event": "setup_success",
                    "installation_id": "../etc/passwd",
                    "event_id": "evt-x",
                }
            )
        self.assertEqual(ctx.exception.code, 400)


if __name__ == "__main__":
    unittest.main()
