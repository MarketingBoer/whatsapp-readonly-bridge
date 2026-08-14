import tempfile
import unittest
from pathlib import Path

from scripts import release_audit


class ReleaseAuditTests(unittest.TestCase):
    def test_dockerfile_rejects_unpinned_root_secret_and_broad_copy(self):
        findings = release_audit.check_dockerfile(
            "FROM python:3.12-alpine\nUSER root\nENV WA_VERIFY_TOKEN=change-me\nCOPY . /app\n"
        )
        self.assertGreaterEqual(len(findings), 4)

    def test_workflow_symbolic_refs_are_rejected(self):
        findings = release_audit.check_workflow_refs(
            "steps:\n  - uses: actions/checkout@v4\n", "ci.yml"
        )
        self.assertEqual(findings, ["ci.yml:2: action ref is not pinned"])

    def test_source_audit_rejects_forbidden_paths_and_core_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "bridge.py").write_text("import urllib.request\n", encoding="utf-8")
            (root / ".env").write_text("SECRET=x\n", encoding="utf-8")
            (root / "Dockerfile").write_text("FROM python:3.12-alpine\nCOPY . /app\n",
                                              encoding="utf-8")
            findings = release_audit.audit_source(root)
        self.assertTrue(any("forbidden tracked path" in f for f in findings))
        self.assertTrue(any("forbidden core boundary" in f for f in findings))
        self.assertTrue(any("Dockerfile" in f for f in findings))

    def test_image_inspection_rejects_root_secret_labels_and_forbidden_files(self):
        findings = release_audit.check_image_inspection(
            {"Config": {"User": "", "Env": ["WA_APP_SECRET=your-secret"], "Labels": {}}},
            [{"CreatedBy": "ENV WA_VERIFY_TOKEN=change-me"}],
            ["/app/.env", "/app/tests/test.py"],
        )
        self.assertTrue(any("root" in f for f in findings))
        self.assertTrue(any("secret-like" in f for f in findings))
        self.assertTrue(any("OCI" in f for f in findings))
        self.assertTrue(any("forbidden paths" in f for f in findings))


if __name__ == "__main__":
    unittest.main()
