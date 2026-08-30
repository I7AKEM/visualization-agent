#!/usr/bin/env python3
"""Install one reviewed CI binary locally after an exact SHA-256 check."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import stat
import tarfile
import tempfile
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]
LOCK_PATH = ROOT / "infra" / "dev" / "ci-tools.lock.json"


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("tool")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--archive", type=Path, help="verify and install an already-downloaded archive"
    )
    args = parser.parse_args()
    lock = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
    record = lock.get("binary_tools", {}).get(args.tool)
    if not isinstance(record, dict):
        raise SystemExit(f"tool {args.tool!r} is absent from {LOCK_PATH}")
    url = record["url"]
    if urlparse(url).scheme != "https":
        raise SystemExit("CI tool download must use HTTPS")
    expected = record["sha256"]
    if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{64}", expected):
        raise SystemExit("CI tool lock needs a 64-hex SHA-256 value")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f"wp01-{args.tool}-") as temporary:
        archive_path = Path(temporary) / "download"
        if args.archive:
            shutil.copyfile(args.archive, archive_path)
        else:
            request = urllib.request.Request(
                url, headers={"User-Agent": "visualization-agent-wp01-ci"}
            )
            with (
                urllib.request.urlopen(request, timeout=60) as response,
                archive_path.open("wb") as destination,
            ):
                if urlparse(response.geturl()).scheme != "https":
                    raise SystemExit("CI tool download redirected away from HTTPS")
                shutil.copyfileobj(response, destination)
        observed = digest(archive_path)
        if observed != expected:
            raise SystemExit(
                f"{args.tool} digest mismatch: expected sha256:{expected}, "
                f"observed sha256:{observed}"
            )
        member_name = record["archive_member"]
        with tarfile.open(archive_path, mode="r:gz") as archive:
            member = archive.getmember(member_name)
            if not member.isfile() or member.name != Path(member.name).name:
                raise SystemExit(f"unsafe or non-file archive member: {member.name}")
            source = archive.extractfile(member)
            if source is None:
                raise SystemExit(f"unable to read archive member: {member.name}")
            output = args.output_dir / args.tool
            with output.open("wb") as destination:
                shutil.copyfileobj(source, destination)
            output.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
    print(f"PASS: installed {args.tool} {record['version']} locally from sha256:{expected}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
