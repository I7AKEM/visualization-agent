#!/usr/bin/env python3
"""Capture durable LOCAL-RUNTIME HTTP and process evidence for the WP-01 web shell."""

from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import os
import re
import signal
import socket
import subprocess
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
ASSET = re.compile(rb'(/_next/static/chunks/[^"\\]+[.]js)')


def sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def request(host: str, port: int, path: str) -> tuple[str, list[tuple[str, str]], bytes]:
    connection = http.client.HTTPConnection(host, port, timeout=5)
    connection.request("GET", path, headers={"Connection": "close"})
    response = connection.getresponse()
    version = "HTTP/1.1" if response.version == 11 else f"HTTP/{response.version / 10:.1f}"
    status = f"{version} {response.status} {response.reason}"
    headers = response.getheaders()
    body = response.read()
    connection.close()
    return status, headers, body


def rendered_response(status: str, headers: list[tuple[str, str]]) -> str:
    return status + "\n" + "\n".join(f"{name}: {value}" for name, value in headers) + "\n"


def wait_for_page(
    host: str, port: int, process: subprocess.Popen[str]
) -> tuple[str, list[tuple[str, str]], bytes]:
    deadline = time.monotonic() + 15
    last_error = "server did not respond"
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"server exited before readiness with {process.returncode}")
        try:
            status, headers, body = request(host, port, "/")
            if status.startswith("HTTP/1.1 200"):
                return status, headers, body
            last_error = status
        except OSError as exc:
            last_error = str(exc)
        time.sleep(0.1)
    raise RuntimeError(f"server readiness timed out: {last_error}")


def listener_remains(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as connection:
        connection.settimeout(0.5)
        return connection.connect_ex((host, port)) == 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=34101)
    args = parser.parse_args()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    command = ("corepack", "pnpm", "--filter", "@visualization-agent/web", "start")
    environment = os.environ.copy()
    environment.update(
        {
            "ALLOW_MODEL_REQUESTS": "false",
            "HOSTNAME": args.host,
            "NO_COLOR": "1",
            "PORT": str(args.port),
            "PYDANTIC_AI_ALLOW_MODEL_REQUESTS": "false",
        }
    )
    process = subprocess.Popen(
        command,
        cwd=ROOT,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        start_new_session=True,
    )
    page_status = ""
    page_headers: list[tuple[str, str]] = []
    page_body = b""
    asset_path = ""
    asset_status = ""
    asset_headers: list[tuple[str, str]] = []
    asset_body = b""
    startup_error: str | None = None
    shutdown_error: str | None = None
    forced_kill = False
    process_log = ""
    try:
        page_status, page_headers, page_body = wait_for_page(args.host, args.port, process)
        match = ASSET.search(page_body)
        if match is None:
            raise RuntimeError("page did not reference a generated client chunk")
        asset_path = match.group(1).decode("ascii")
        asset_status, asset_headers, asset_body = request(args.host, args.port, asset_path)
        if not asset_status.startswith("HTTP/1.1 200"):
            raise RuntimeError(f"client asset probe failed: {asset_status}")
    except Exception as exc:  # evidence is still written before the gate fails
        startup_error = str(exc)
    finally:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGINT)
        try:
            process_log, _ = process.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            shutdown_error = "server did not shut down within 10 seconds after SIGINT"
            forced_kill = True
            os.killpg(process.pid, signal.SIGKILL)
            process_log, _ = process.communicate(timeout=5)

    no_listener = not listener_remains(args.host, args.port)
    (output_dir / "startup-shutdown.log").write_text(process_log, encoding="utf-8")
    (output_dir / "page-headers.txt").write_text(
        rendered_response(page_status, page_headers), encoding="utf-8"
    )
    (output_dir / "page-body.html").write_bytes(page_body)
    (output_dir / "asset-headers.txt").write_text(
        rendered_response(asset_status, asset_headers), encoding="utf-8"
    )
    (output_dir / "client-asset.js").write_bytes(asset_body)
    trace: dict[str, Any] = {
        "schema_version": 1,
        "command": list(command),
        "host": args.host,
        "port": args.port,
        "page": {
            "request": "GET / HTTP/1.1",
            "status": page_status,
            "headers_file": "page-headers.txt",
            "body_file": "page-body.html",
            "body_assertion": "<h1>Visualization Agent</h1>",
            "body_assertion_passed": b"<h1>Visualization Agent</h1>" in page_body,
            "bytes": len(page_body),
            "sha256": sha256(page_body),
        },
        "asset": {
            "request": f"GET {asset_path} HTTP/1.1",
            "status": asset_status,
            "headers_file": "asset-headers.txt",
            "body_file": "client-asset.js",
            "bytes": len(asset_body),
            "sha256": sha256(asset_body),
        },
        "shutdown": {
            "signal": "SIGINT",
            "process_exit_code": process.returncode,
            "listener_remaining": not no_listener,
            "forced_kill": forced_kill,
            "error": shutdown_error,
            "log_file": "startup-shutdown.log",
        },
        "startup_error": startup_error,
        "result": "passed"
        if startup_error is None
        and shutdown_error is None
        and b"<h1>Visualization Agent</h1>" in page_body
        and no_listener
        and process.returncode in {130, -signal.SIGINT}
        else "failed",
    }
    (output_dir / "trace.json").write_text(
        json.dumps(trace, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    evidence_files = sorted(
        path for path in output_dir.iterdir() if path.is_file() and path.name != "checksums.sha256"
    )
    (output_dir / "checksums.sha256").write_text(
        "".join(f"{sha256(path.read_bytes())}  {path.name}\n" for path in evidence_files),
        encoding="utf-8",
    )
    print(
        f"{trace['result'].upper()}: page={page_status!r} asset={asset_status!r} "
        f"shutdown={process.returncode} listener_remaining={not no_listener}"
    )
    return 0 if trace["result"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
