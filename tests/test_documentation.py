import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BANNED = re.compile(
    r"zero ban risk|no ban risk|ban-proof|free forever|always free|"
    r"entire stack costs nothing|no compliance issues|GDPR-friendly|"
    r"GDPR compliant|every incoming message|all incoming messages|"
    r"hundreds per minute|works alongside WhatsApp Business App|"
    r"every WhatsApp bridge|production-ready|used in production",
    re.IGNORECASE,
)


class ReadmeTests(unittest.TestCase):
    def test_readme_structure_and_links(self):
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        required = [
            "Receive inbound WhatsApp messages through Meta's official Cloud API",
            "Quick Start", "Meta prerequisites", "Configuration", "Docker",
            "Direct Python", "systemd", "Examples", "Architecture",
            "Security and privacy", "Pricing", "Coexistence", "Limitations",
            "FAQ", "Contributing", "Security", "License", "```mermaid",
        ]
        for needle in required:
            self.assertIn(needle, text)
        for rel in re.findall(r"\[[^\]]+\]\(([^):#]+(?:\.md|\.jsonl|\.txt|\.py|\.service)?)\)", text):
            if rel.startswith("http"):
                continue
            self.assertTrue((ROOT / rel).exists(), rel)

    def test_conservative_claims(self):
        paths = [ROOT / "README.md"]
        for optional in ("SECURITY.md", "CONTRIBUTING.md", "docs/releases/v1.0.0.md"):
            path = ROOT / optional
            if path.exists():
                paths.append(path)
        for path in paths:
            for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                self.assertIsNone(BANNED.search(line), f"{path}:{line_no}:{line}")


class SchemaAndLaunchTests(unittest.TestCase):
    def test_sample_schema(self):
        keys = {"ts", "message_id", "message_timestamp", "from", "name", "type",
                "text", "phone_number_id", "raw"}
        seen = set()
        for line in (ROOT / "examples/sample-inbox.jsonl").read_text(encoding="utf-8").splitlines():
            record = json.loads(line)
            self.assertEqual(set(record), keys)
            self.assertNotIn(record["message_id"], seen)
            seen.add(record["message_id"])

    def test_launch_files_exist_and_are_drafts(self):
        files = [
            "launch/hackernews.md", "launch/reddit-selfhosted.md",
            "launch/reddit-opensource.md", "launch/reddit-python.md",
            "launch/devto.md", "launch/linkedin.md", "launch/x.md",
            "launch/producthunt.md", "launch/launch-checklist.md",
            "launch/social-preview.md", "launch/competitive-research.md",
        ]
        for rel in files:
            text = (ROOT / rel).read_text(encoding="utf-8")
            self.assertIn("Status: Draft - do not post automatically", text)
        self.assertIn("AI-generated copy", (ROOT / "launch/reddit-opensource.md").read_text(encoding="utf-8"))
        self.assertIn("Showcase Thread", (ROOT / "launch/reddit-python.md").read_text(encoding="utf-8"))
        self.assertIn("published: false", (ROOT / "launch/devto.md").read_text(encoding="utf-8"))
        self.assertIn("DEFER UNTIL VALIDATED", (ROOT / "launch/producthunt.md").read_text(encoding="utf-8"))
        checklist = (ROOT / "launch/launch-checklist.md").read_text(encoding="utf-8")
        for needle in ("Last verified: 2026-08-14", "T-1", "Launch", "After", "STOP"):
            self.assertIn(needle, checklist)


if __name__ == "__main__":
    unittest.main()
