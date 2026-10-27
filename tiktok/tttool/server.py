"""Страницата-инструмент: клип по клип, със сваляне, копиране на текста и отметка."""
import json
import threading
import time
import urllib.parse
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import sofia_time
from .config import Config
from .jobs import Cycle
from .page import render
from .state import State


class App:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.state = State(cfg.state_file)
        self.cycle = Cycle(cfg, self.state)


def make_handler(app: App):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def _authorized(self, query) -> bool:
            token = app.cfg.tool_token
            if not token:
                return True
            if query.get("k", [""])[0] == token:
                return True
            jar = cookies.SimpleCookie(self.headers.get("Cookie", ""))
            return "tt" in jar and jar["tt"].value == token

        def _send(self, code, body: bytes, ctype="text/html; charset=utf-8", extra=None):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            url = urllib.parse.urlparse(self.path)
            query = urllib.parse.parse_qs(url.query)
            if not self._authorized(query):
                return self._send(403, "Нужен е линкът с ключа.".encode())
            extra = {}
            if app.cfg.tool_token and query.get("k"):
                extra["Set-Cookie"] = f"tt={app.cfg.tool_token}; HttpOnly; SameSite=Strict; Path=/"
            if url.path in ("/", "/index.html"):
                return self._send(200, render(app.cfg, app.state, app.cycle).encode("utf-8"), extra=extra)
            if url.path.startswith("/video/"):
                return self._video(url.path[len("/video/"):], "download" in query)
            self._send(404, b"Not found")

        def _video(self, row_id, download):
            row = next((r for r in app.cycle.load() if r.id == row_id), None)
            path = app.cycle.local_file(row) if row else None
            if not path:
                return self._send(404, "Видеото още не е свалено.".encode())
            size = path.stat().st_size
            start, end = 0, size - 1
            rng = self.headers.get("Range", "")
            if rng.startswith("bytes="):
                a, _, b = rng[6:].partition("-")
                start = int(a) if a else max(0, size - int(b))
                end = int(b) if a and b else end
            length = end - start + 1
            self.send_response(206 if rng else 200)
            self.send_header("Content-Type", "video/mp4")
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", str(length))
            if rng:
                self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            if download:
                name = urllib.parse.quote(row.file_name)
                self.send_header("Content-Disposition", f"attachment; filename*=UTF-8''{name}")
            self.end_headers()
            with open(path, "rb") as f:
                f.seek(start)
                remaining = length
                while remaining > 0:
                    chunk = f.read(min(1024 * 1024, remaining))
                    if not chunk:
                        break
                    try:
                        self.wfile.write(chunk)
                    except (ConnectionResetError, BrokenPipeError):
                        return
                    remaining -= len(chunk)

        def do_POST(self):
            url = urllib.parse.urlparse(self.path)
            if not self._authorized(urllib.parse.parse_qs(url.query)):
                return self._send(403, b"Forbidden")
            if url.path != "/api/done":
                return self._send(404, b"Not found")
            try:
                payload = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))))
                row_id, done = str(payload["id"]), bool(payload["done"])
            except (ValueError, KeyError, TypeError):
                return self._send(400, b"Bad request")
            with app.state.lock:
                if done:
                    app.state.data["done"][row_id] = sofia_time.to_local(sofia_time.now_utc())
                else:
                    app.state.data["done"].pop(row_id, None)
            app.state.save()
            app.cycle.notify.log(f"клип {row_id}: {'насрочен' if done else 'отметката е махната'}")
            self._send(200, b'{"ok":true}', "application/json")

    return Handler


def serve(cfg: Config) -> None:
    app = App(cfg)

    def loop():
        while True:
            try:
                app.cycle.run()
            except Exception as e:  # цикълът не бива да спира сървъра
                app.cycle.notify.log(f"Грешка в проверката: {e}")
            time.sleep(cfg.check_minutes * 60)

    threading.Thread(target=loop, daemon=True).start()
    server = ThreadingHTTPServer((cfg.host, cfg.port), make_handler(app))
    app.cycle.notify.log(f"Инструментът работи на {cfg.tool_url}")
    server.serve_forever()
