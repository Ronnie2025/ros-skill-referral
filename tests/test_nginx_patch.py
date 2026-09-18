#!/usr/bin/env python3
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "site"))
from patch_nginx import patch


class NginxPatchTests(unittest.TestCase):
    def test_inserts_in_http_and_https_server_blocks(self):
        source = """server {
    listen 80;
    server_name dbskill.site;
    location / { return 301 https://dbskill.site$request_uri; }
}
server {
    listen 443 ssl;
    server_name dbskill.site;
    location / { try_files $uri =404; }
}
"""
        snippet = (ROOT / "site" / "nginx-referral.location.conf").read_text()
        result = patch(source, snippet)
        self.assertEqual(result.count("location ^~ /referral/"), 2)
        self.assertEqual(patch(result, snippet), result)

    def test_rejects_unrelated_vhost(self):
        with self.assertRaises(ValueError):
            patch("server {\n server_name other.example;\n}\n", "location /referral/ {}\n")


if __name__ == "__main__":
    unittest.main()
