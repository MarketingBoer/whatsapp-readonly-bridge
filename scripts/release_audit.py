#!/usr/bin/env python3
from __future__ import annotations
"""Source and image release audit helpers."""

import argparse
import json
import re
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path


FORBIDDEN_TRACKED = {
    ".env",
    "mcp_server.py",
    "tests/test_mcp_server.py",
}
FORBIDDEN_PATTERNS = (
    re.compile(r"(^|/)inbox(/|$)"),
    re.compile(r"(^|/)__pycache__(/|$)"),
    re.compile(r"(^|/)\.memsearch(/|$)"),
)
CORE_NETWORK_EXCEPTIONS = {
    "digest.py",
    "examples/discord-webhook.py",
    "scripts/smoke-test.py",
}
CORE_FORBIDDEN_RE = re.compile(
    r"graph\.facebook\.com|access[_-]?token|send.*whatsapp|reply.*whatsapp|"
    r"urllib\.request|urlopen|HTTPConnection",
    re.IGNORECASE,
)


def audit_source(root: Path) -> list[str]:
    findings: list[str] = []
    tracked = _tracked_files(root)
    for rel in tracked:
        if rel in FORBIDDEN_TRACKED or any(p.search(rel) for p in FORBIDDEN_PATTERNS):
            findings.append(f"forbidden tracked path: {rel}")

    dockerfile = root / "Dockerfile"
    if dockerfile.exists():
        findings.extend(check_dockerfile(dockerfile.read_text(encoding="utf-8")))
    else:
        findings.append("missing Dockerfile")

    workflows = list((root / ".github" / "workflows").glob("*.yml"))
    for workflow in workflows:
        findings.extend(check_workflow_refs(workflow.read_text(encoding="utf-8"),
                                            workflow.name))

    for rel in tracked:
        if (not rel.endswith(".py") or rel in CORE_NETWORK_EXCEPTIONS
                or rel.startswith("tests/")):
            continue
        text = (root / rel).read_text(encoding="utf-8")
        for line_no, line in enumerate(text.splitlines(), start=1):
            if CORE_FORBIDDEN_RE.search(line):
                findings.append(f"forbidden core boundary: {rel}:{line_no}")
    return findings


def check_dockerfile(text: str) -> list[str]:
    findings = []
    if not re.search(r"^FROM\s+python:[^@\s]+@sha256:[0-9a-f]{64}", text, re.M):
        findings.append("Dockerfile base is not digest pinned")
    if re.search(r"^\s*USER\s+root\b", text, re.M) or "USER 10001:10001" not in text:
        findings.append("Dockerfile does not use fixed non-root user")
    if re.search(r"WA_(VERIFY_TOKEN|APP_SECRET)\s*=", text):
        findings.append("Dockerfile contains bridge secret environment")
    if re.search(r"^\s*COPY\s+\.\s+", text, re.M):
        findings.append("Dockerfile uses broad COPY")
    return findings


def check_workflow_refs(text: str, name: str = "workflow") -> list[str]:
    findings = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        if "uses:" in line and "docker://" not in line:
            if not re.search(r"@[0-9a-f]{40}\b", line):
                findings.append(f"{name}:{line_no}: action ref is not pinned")
    return findings


def check_image_inspection(config: dict, history: list[dict], files: list[str]) -> list[str]:
    findings = []
    user = str(config.get("Config", {}).get("User", ""))
    if user in {"", "0", "root"}:
        findings.append("image user is root or empty")
    env = "\n".join(config.get("Config", {}).get("Env", []))
    hist = "\n".join(item.get("CreatedBy", "") for item in history)
    if re.search(r"WA_(VERIFY_TOKEN|APP_SECRET)|change-me|your-", env + "\n" + hist):
        findings.append("image config/history contains secret-like values")
    labels = config.get("Config", {}).get("Labels", {}) or {}
    for label in ("org.opencontainers.image.source",
                  "org.opencontainers.image.licenses",
                  "org.opencontainers.image.description"):
        if label not in labels:
            findings.append(f"missing OCI label: {label}")
    forbidden_files = [
        f for f in files
        if f.startswith("/app/")
        and re.search(r"(^|/)(\.git|\.env|tests|docs|mcp_server\.py|__pycache__)", f)
    ]
    if forbidden_files:
        findings.append("image filesystem contains forbidden paths")
    return findings


def _tracked_files(root: Path) -> list[str]:
    try:
        result = subprocess.run(
            ["git", "ls-files"],
            cwd=root,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except Exception:
        return [str(path.relative_to(root)) for path in root.rglob("*") if path.is_file()]
    return [line for line in result.stdout.splitlines() if line]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-only", action="store_true")
    parser.add_argument("--image")
    parser.add_argument("--root", default=".")
    args = parser.parse_args(argv)
    findings = []
    if args.image:
        findings.extend(audit_image(args.image))
    else:
        findings.extend(audit_source(Path(args.root).resolve()))
    for finding in findings:
        print(f"ERROR: {finding}")
    if not findings:
        print("PASS: release audit")
    return 1 if findings else 0


def audit_image(image: str) -> list[str]:
    findings: list[str] = []
    try:
        inspect = json.loads(_run(["docker", "image", "inspect", image]))[0]
        history = json.loads(_run(["docker", "history", "--no-trunc", "--format", "{{json .}}", image], json_lines=True))
    except Exception as exc:
        return [f"docker inspect failed: {type(exc).__name__}"]

    files: list[str] = []
    container_id = None
    with tempfile.TemporaryDirectory() as tmp:
        archive = Path(tmp) / "fs.tar"
        try:
            container_id = _run(["docker", "create", image]).strip()
            with archive.open("wb") as handle:
                subprocess.run(["docker", "export", container_id], check=True,
                               stdout=handle, stderr=subprocess.PIPE)
            with tarfile.open(archive) as tar:
                files = ["/" + member.name for member in tar.getmembers()]
        except Exception as exc:
            findings.append(f"docker filesystem inspection failed: {type(exc).__name__}")
        finally:
            if container_id:
                subprocess.run(["docker", "rm", "-f", container_id],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    findings.extend(check_image_inspection(inspect, history, files))
    return findings


def _run(cmd: list[str], json_lines: bool = False) -> str:
    result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True)
    if not json_lines:
        return result.stdout
    items = [json.loads(line) for line in result.stdout.splitlines() if line]
    return json.dumps(items)


if __name__ == "__main__":
    raise SystemExit(main())
