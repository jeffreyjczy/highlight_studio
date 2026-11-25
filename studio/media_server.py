"""Local HTTP server for the UI files, video/audio (with Range, so seeking works) and thumbnails.

Bound to 127.0.0.1 on a random port. Media and thumbnail routes need the per-run token,
and only serve files inside the app's folders (recordings, highlights, merged, music)."""
import mimetypes
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import library
from common import STUDIO, is_inside

TOKEN = secrets.token_urlsafe(16)
UI = STUDIO / "ui"
mimetypes.add_type("video/mp4", ".mp4")
mimetypes.add_type("audio/mp4", ".m4a")
mimetypes.add_type("text/javascript", ".js")


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def _send_file(self, path, ctype=None, cache=False):
        size = path.stat().st_size
        ctype = ctype or mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        start, end = 0, size - 1
        rng = self.headers.get("Range")
        if rng and rng.startswith("bytes="):
            a, _, b = rng[6:].split(",")[0].partition("-")
            if a:
                start = int(a)
                end = int(b) if b else end
            else:  # suffix range: last N bytes
                start = max(0, size - int(b))
            end = min(end, size - 1)
            if start > end:
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{size}")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        else:
            self.send_response(200)
        length = end - start + 1
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(length))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Cache-Control", "max-age=86400" if cache else "no-cache")
        self.end_headers()
        if self.command == "HEAD":
            return
        with open(path, "rb") as f:
            f.seek(start)
            left = length
            try:
                while left > 0:
                    chunk = f.read(min(1 << 20, left))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    left -= len(chunk)
            except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
                pass

    def _fail(self, code):
        self.send_response(code)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        if u.path in ("/", "/index.html"):
            return self._send_file(UI / "index.html", "text/html; charset=utf-8")
        if u.path.startswith("/ui/"):
            f = (UI / u.path[4:]).resolve()
            if not is_inside(f, [UI]) or not f.is_file():
                return self._fail(404)
            return self._send_file(f)
        if q.get("k") != TOKEN:
            return self._fail(403)
        p = Path(q.get("p", ""))
        if not is_inside(p) or not p.is_file():
            return self._fail(404)
        try:
            if u.path == "/media":
                return self._send_file(p)
            if u.path == "/thumb":
                idx = q.get("i")
                t = library.thumb(p, frac=float(q.get("f", 0.1)), width=int(q.get("w", 480)),
                                  index=int(idx) if idx is not None else None)
                return self._send_file(t, "image/jpeg", cache=True) if t else self._fail(404)
        except (OSError, ValueError):
            return self._fail(500)
        return self._fail(404)


def start():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv.server_address[1]
