#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
import urllib.request


ACCEPT = "application/vnd.oci.image.index.v1+json, application/vnd.docker.distribution.manifest.list.v2+json"


def fetch_token(repository: str, opener=urllib.request.urlopen) -> str:
    service = "ghcr.io"
    scope = f"repository:{repository}:pull"
    url = "https://ghcr.io/token?" + urllib.parse.urlencode({
        "service": service,
        "scope": scope,
    })
    with opener(url, timeout=10) as response:
        data = json.loads(response.read())
    return data["token"]


def fetch_manifest(repository: str, tag: str, token: str,
                   opener=urllib.request.urlopen) -> tuple[str, dict]:
    request = urllib.request.Request(
        f"https://ghcr.io/v2/{repository}/manifests/{tag}",
        headers={"Authorization": f"Bearer {token}", "Accept": ACCEPT},
    )
    with opener(request, timeout=10) as response:
        digest = response.headers.get("Docker-Content-Digest", "")
        manifest = json.loads(response.read())
    return digest, manifest


def verify(repository: str, tags: list[str], platforms: set[tuple[str, str]],
           opener=urllib.request.urlopen) -> list[str]:
    findings = []
    token = fetch_token(repository, opener)
    expected_digest = None
    for tag in tags:
        digest, manifest = fetch_manifest(repository, tag, token, opener)
        if expected_digest is None:
            expected_digest = digest
        elif digest != expected_digest:
            findings.append(f"tag {tag} digest differs")
        present = {
            (item.get("platform", {}).get("os"), item.get("platform", {}).get("architecture"))
            for item in manifest.get("manifests", [])
            if item.get("platform", {}).get("os") != "unknown"
        }
        missing = platforms - present
        if missing:
            findings.append(f"tag {tag} missing platforms: {sorted(missing)}")
    return findings


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("repository")
    parser.add_argument("tags", nargs="+")
    parser.add_argument("--platform", action="append", default=["linux/amd64", "linux/arm64"])
    args = parser.parse_args(argv)
    platforms = {tuple(item.split("/", 1)) for item in args.platform}
    findings = verify(args.repository, args.tags, platforms)
    for finding in findings:
        print(f"ERROR: {finding}")
    if not findings:
        print("PASS: GHCR tags verified")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
