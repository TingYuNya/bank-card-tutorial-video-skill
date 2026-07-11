from __future__ import annotations

import argparse
import json
import mimetypes
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit


class PreviewHandler(BaseHTTPRequestHandler):
    server_version = "TutorialPreview/1.0"

    @property
    def root(self) -> Path:
        return self.server.project_root  # type: ignore[attr-defined]

    def log_message(self, fmt: str, *args: object) -> None:
        print(f"[http] {self.address_string()} {fmt % args}")

    def send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def resolve_path(self) -> Path | None:
        request_path = unquote(urlsplit(self.path).path)
        relative = request_path.lstrip("/") or "review/storyboard-audit.html"
        candidate = (self.root / relative).resolve()
        try:
            candidate.relative_to(self.root)
        except ValueError:
            return None
        if candidate.is_dir():
            candidate = candidate / "index.html"
        return candidate

    def do_GET(self) -> None:  # noqa: N802
        if self.path.startswith("/api/status"):
            self.send_json(200, {"ok": True, "project": str(self.root)})
            return
        path = self.resolve_path()
        if not path or not path.exists() or not path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND, "File not found")
            return
        self.serve_file(path)

    def do_HEAD(self) -> None:  # noqa: N802
        path = self.resolve_path()
        if not path or not path.exists() or not path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND, "File not found")
            return
        self.serve_file(path, head_only=True)

    def do_POST(self) -> None:  # noqa: N802
        routes = {
            "/api/save-storyboard-review": self.root / "work" / "storyboard-review.json",
            "/api/save-timeline-review": self.root / "work" / "timeline-review.json",
        }
        target = routes.get(urlsplit(self.path).path)
        if target is None:
            self.send_error(HTTPStatus.NOT_FOUND, "Unknown API route")
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 2_000_000:
                raise ValueError("Invalid payload size")
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            self.send_json(200, {"ok": True, "path": target.relative_to(self.root).as_posix()})
        except Exception as exc:
            self.send_json(400, {"ok": False, "error": str(exc)})

    def serve_file(self, path: Path, head_only: bool = False) -> None:
        stat = path.stat()
        size = stat.st_size
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        if path.suffix.lower() in {".json", ".srt", ".ass", ".md"}:
            mime += "; charset=utf-8"
        range_header = self.headers.get("Range")

        if range_header and range_header.startswith("bytes="):
            spec = range_header[len("bytes=") :].split(",", 1)[0]
            start_raw, end_raw = (spec.split("-", 1) + [""])[:2]
            try:
                if start_raw:
                    start = int(start_raw)
                    end = int(end_raw) if end_raw else size - 1
                else:
                    suffix = int(end_raw)
                    start = max(0, size - suffix)
                    end = size - 1
                end = min(end, size - 1)
                if start < 0 or start > end or start >= size:
                    raise ValueError
            except ValueError:
                self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                self.send_header("Content-Range", f"bytes */{size}")
                self.end_headers()
                return
            self.send_response(HTTPStatus.PARTIAL_CONTENT)
            self.send_header("Content-Type", mime)
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            self.send_header("Content-Length", str(end - start + 1))
            self.send_header("Last-Modified", self.date_time_string(stat.st_mtime))
            self.end_headers()
            if not head_only:
                with path.open("rb") as fh:
                    fh.seek(start)
                    remaining = end - start + 1
                    while remaining > 0:
                        chunk = fh.read(min(64 * 1024, remaining))
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                        remaining -= len(chunk)
            return

        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", mime)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(size))
        self.send_header("Last-Modified", self.date_time_string(stat.st_mtime))
        self.end_headers()
        if not head_only:
            with path.open("rb") as fh:
                while chunk := fh.read(64 * 1024):
                    self.wfile.write(chunk)


def main() -> int:
    parser = argparse.ArgumentParser(description="Serve project files with HTTP Range support and review-save APIs.")
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8767)
    args = parser.parse_args()

    root = args.project.resolve()
    if not root.exists() or not root.is_dir():
        raise FileNotFoundError(root)
    server = ThreadingHTTPServer((args.host, args.port), PreviewHandler)
    server.project_root = root  # type: ignore[attr-defined]
    print(f"[serve] http://{args.host}:{args.port}/")
    print(f"[storyboard] http://{args.host}:{args.port}/review/storyboard-audit.html")
    print(f"[timeline] http://{args.host}:{args.port}/review/timeline-preview.html")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
