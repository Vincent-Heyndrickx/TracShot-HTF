"""Debatviewer: toont trace.json, verdict.json en live.json live in je browser.

Start met `uv run viewer` (leest de root van deze repo) of `uv run viewer <map-van-trace.json>`.
Poort via VIEWER_PORT (standaard 8100).

Live: de browser opent één Server-Sent-Events-verbinding (/events). De server kijkt lokaal of
trace.json, verdict.json of live.json veranderde en stuurt alleen dan de nieuwe inhoud door.
Zonder SSE (oude browser, proxy) valt de pagina terug op gewoon ophalen.

Run starten vanuit de viewer: POST /start start `council.py` in deze map (POST /stop stopt een run die de viewer startte).
Lokaal (rechtstreeks op 127.0.0.1, zonder proxy) mag dat altijd. Via een proxy (bv. nginx op de VPS) alleen met de
startsleutel uit VIEWER_START_KEY (omgeving of .env); zonder sleutel kan niemand van buitenaf een run starten.
"""
import hmac
import http.server
import json
import os
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

ROOT = Path(__file__).parent
BESTANDEN = ("trace.json", "verdict.json", "live.json")
TIK = 0.1          # seconden tussen twee controles van de bestanden (alleen lokaal, per open viewer)
STIL_TRACE = 120   # seconden: een trace met status "bezig" die zo lang niet veranderde, telt niet meer als lopend
HARTSLAG = 15      # seconden: houdt proxies (nginx) wakker als er even niets verandert


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    doel = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ROOT
    map_ = doel.parent if doel.is_file() else doel
    port = int(os.getenv("VIEWER_PORT", "8100"))

    def startsleutel():
        sleutel = os.getenv("VIEWER_START_KEY", "").strip()
        if not sleutel and (ROOT / ".env").exists():
            for regel in (ROOT / ".env").read_text(encoding="utf-8", errors="replace").splitlines():
                if regel.strip().startswith("VIEWER_START_KEY="):
                    sleutel = regel.split("=", 1)[1].strip().strip('"').strip("'")
        return sleutel

    run = {"proces": None, "log": None, "einde": 0.0}
    slot = threading.Lock()

    def eigen_run_bezig():
        p = run["proces"]
        if p is None:
            return False
        if p.poll() is None:
            return True
        if not run["einde"]:
            run["einde"] = time.time()  # onze run is gestopt: een "bezig" die ze achterliet telt niet meer
        return False

    def andere_run_bezig():
        """Een run die niet door deze viewer gestart werd (bv. vanuit een terminal) en nog leeft."""
        try:
            st = (map_ / "trace.json").stat()
            trace = json.loads((map_ / "trace.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return False
        if run["einde"] and st.st_mtime <= run["einde"] + 1:
            return False
        return trace.get("status") == "bezig" and time.time() - st.st_mtime < STIL_TRACE

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
            if pad == "/run":
                return self.json(self.runstaat())
            self.send_error(404)

        def lokaal(self):
            return (self.client_address[0] in ("127.0.0.1", "::1")
                    and not self.headers.get("X-Forwarded-For") and not self.headers.get("X-Real-IP"))

        def toegestaan(self):
            if self.lokaal():
                return True
            sleutel = startsleutel()
            return bool(sleutel) and hmac.compare_digest(self.headers.get("X-Start-Key", "").encode(), sleutel.encode())

        def runstaat(self):
            return {"eigen": eigen_run_bezig(), "bezig": eigen_run_bezig() or andere_run_bezig(),
                    "lokaal": self.lokaal(), "sleutel_kan": bool(startsleutel())}

        def json(self, data, code=200):
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            pad = self.path.split("?")[0]
            if pad not in ("/start", "/stop"):
                return self.send_error(404)
            if not self.toegestaan():
                return self.json({"fout": "Geen toegang: een run starten of stoppen vraagt de startsleutel."}, 403)
            with slot:
                if pad == "/stop":
                    if not eigen_run_bezig():
                        return self.json({"fout": "Er loopt geen run die de viewer startte."}, 409)
                    run["proces"].terminate()
                    return self.json({"ok": True, "bericht": "De run wordt gestopt."})
                if eigen_run_bezig() or andere_run_bezig():
                    return self.json({"fout": "Er loopt al een run. Wacht tot ze klaar is."}, 409)
                env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
                env.pop("VIEWER_START_KEY", None)
                if map_ != ROOT:
                    env["COUNCIL_OUTPUT_DIR"] = str(map_)
                if run["log"]:
                    run["log"].close()
                run["log"] = open(map_ / "council.log", "w", encoding="utf-8")
                run["einde"] = 0.0
                run["proces"] = subprocess.Popen([sys.executable, str(ROOT / "council.py")], cwd=ROOT, env=env,
                                                 stdout=run["log"], stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
            print(f"Run gestart vanuit de viewer (pid {run['proces'].pid}), uitvoer in {map_ / 'council.log'}")
            return self.json({"ok": True, "bericht": "De run is gestart."})

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
