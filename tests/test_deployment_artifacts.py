import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class RuntimeArtifactTests(unittest.TestCase):
    def test_dockerfile_runtime_contract(self):
        text = (ROOT / "Dockerfile").read_text(encoding="utf-8")
        self.assertRegex(text, r"FROM python:3\.12\.\d+-alpine\d+\.\d+@sha256:[0-9a-f]{64}")
        self.assertIn("PYTHONUNBUFFERED=1", text)
        self.assertIn("WA_INBOX=/data/messages.jsonl", text)
        self.assertIn("USER 10001:10001", text)
        self.assertIn("STOPSIGNAL SIGTERM", text)
        self.assertIn("HEALTHCHECK", text)
        self.assertNotIn("WA_VERIFY_TOKEN", text)
        self.assertNotIn("WA_APP_SECRET", text)
        self.assertNotIn("COPY .", text)
        for label in ("org.opencontainers.image.source",
                      "org.opencontainers.image.licenses",
                      "org.opencontainers.image.description",
                      "org.opencontainers.image.title",
                      "org.opencontainers.image.version",
                      "org.opencontainers.image.revision"):
            self.assertIn(label, text)

    def test_dockerignore_is_deny_by_default(self):
        lines = (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()
        self.assertEqual(lines[0], "**")
        self.assertIn("!bridge.py", lines)
        self.assertIn("!.env.example", lines)
        self.assertIn(".env", lines)
        self.assertIn("mcp_server.py", lines)
        self.assertIn("tests", lines)

    def test_compose_and_systemd_contracts(self):
        compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
        self.assertIn("ghcr.io/marketingboer/whatsapp-readonly-bridge:latest", compose)
        self.assertIn("${WA_VERIFY_TOKEN:?WA_VERIFY_TOKEN is required}", compose)
        self.assertIn("${WA_APP_SECRET:?WA_APP_SECRET is required}", compose)
        self.assertIn("${WA_HOST:-127.0.0.1}:${WA_HOST_PORT:-3100}:3100", compose)
        self.assertIn("read_only: true", compose)
        self.assertIn("cap_drop:", compose)
        self.assertIn("no-new-privileges:true", compose)
        override = (ROOT / "docker-compose.build.yml").read_text(encoding="utf-8")
        self.assertIn("build:", override)
        self.assertNotIn("build:", compose)

        unit = (ROOT / "whatsapp-bridge.service").read_text(encoding="utf-8")
        for needle in ("DynamicUser=yes", "StateDirectory=whatsapp-readonly-bridge",
                       "EnvironmentFile=/etc/whatsapp-readonly-bridge.env",
                       "ProtectSystem=strict", "NoNewPrivileges=yes",
                       "TimeoutStopSec=20s"):
            self.assertIn(needle, unit)
        self.assertNotIn("WA_VERIFY_TOKEN=", unit)
        self.assertNotIn("WA_APP_SECRET=", unit)


class CIArtifactTests(unittest.TestCase):
    def test_actions_are_pinned_to_full_shas(self):
        workflows = list((ROOT / ".github" / "workflows").glob("*.yml"))
        self.assertTrue(workflows)
        for workflow in workflows:
            for line in workflow.read_text(encoding="utf-8").splitlines():
                if "uses:" in line and "docker://" not in line:
                    self.assertRegex(line, r"@[0-9a-f]{40}\b")


class PublishArtifactTests(unittest.TestCase):
    def test_publish_workflow_is_tag_only_semver_and_multiarch(self):
        workflow = (ROOT / ".github" / "workflows" / "publish-container.yml").read_text(encoding="utf-8")
        self.assertIn("^v(0|[1-9][0-9]*)", workflow)
        self.assertIn("linux/amd64,linux/arm64", workflow)
        self.assertIn("packages: write", workflow)
        self.assertIn("provenance", workflow)
        self.assertIn("sbom", workflow)
        self.assertNotIn("softprops/action-gh-release", workflow)


if __name__ == "__main__":
    unittest.main()
