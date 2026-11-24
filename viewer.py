"""Debatviewer: toont trace.json, verdict.json en live.json live in je browser.

Start met `uv run viewer` (leest de root van deze repo) of `uv run viewer <map-van-trace.json>`.
Poort via VIEWER_PORT (standaard 8100).

Live: de browser opent één Server-Sent-Events-verbinding (/events). De server kijkt lokaal of
trace.json, verdict.json of live.json veranderde en stuurt alleen dan de nieuwe inhoud door.
Zonder SSE (oude browser, proxy) valt de pagina terug op gewoon ophalen.
"""
import http.server
import json
import os
import sys
import time
import webbrowser
from pathlib import Path

ROOT = Path(__file__).parent
BESTANDEN = ("trace.json", "verdict.json", "live.json")
TIK = 0.1          # seconden tussen twee controles van de bestanden (alleen lokaal, per open viewer)
HARTSLAG = 15      # seconden: houdt proxies (nginx) wakker als er even niets verandert


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    doel = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ROOT
    map_ = doel.parent if doel.is_file() else doel
    port = int(os.getenv("VIEWER_PORT", "8100"))

    def lees(naam):
        """(sleutel, compacte json-tekst) of (sleutel, None) als het bestand half geschreven is."""
        pad = map_ / naam
        try:
            st = pad.stat()
        except FileNotFoundError:
            return None, "null"
        sleutel = (st.st_mtime_ns, st.st_size)
        try:
            data = json.loads(pad.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return sleutel, None
        return sleutel, json.dumps(data, ensure_ascii=False, separators=(",", ":"))

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            pad = self.path.split("?")[0]
            if pad in ("/", "/index.html"):
                return self.stuur(ROOT / "viewer.html", "text/html; charset=utf-8")
            if pad == "/events":
                return self.events()
            if pad[1:] in BESTANDEN:
                return self.stuur(map_ / pad[1:], "application/json; charset=utf-8")
            self.send_error(404)

        def stuur(self, bestand, soort):
            if not bestand.exists():
                return self.send_error(404)
            data = bestand.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", soort)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def events(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Accel-Buffering", "no")  # nginx: niet bufferen
            self.end_headers()
            gezien, hartslag = {}, time.monotonic()
            try:
                self.wfile.write(b"retry: 1000\n\n")
                while True:
                    for naam in BESTANDEN:
                        sleutel, data = lees(naam)
                        if data is None or gezien.get(naam, "nooit") == sleutel:
                            continue  # half geschreven of onveranderd: volgende tik
                        gezien[naam] = sleutel
                        self.wfile.write(f"event: {naam[:-5]}\ndata: {data}\n\n".encode("utf-8"))
                        self.wfile.flush()
                        hartslag = time.monotonic()
                    if time.monotonic() - hartslag > HARTSLAG:
                        self.wfile.write(b": hartslag\n\n")
                        self.wfile.flush()
                        hartslag = time.monotonic()
                    time.sleep(TIK)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
                return  # browser weg

        def log_message(self, *args):
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.daemon_threads = True
    url = f"http://127.0.0.1:{port}/"
    print(f"Debatviewer op {url} (leest {map_}). Stop met Ctrl+C.")
    webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
