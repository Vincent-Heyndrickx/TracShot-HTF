"""Demo voor de viewer: speelt een NEP-debat af in runs/demo/, met live tekst. Geen LLM, geen Kennisbron.

Alle tekst en ID's hieronder zijn verzonnen opvultekst (ID's 9xx) om de viewer te testen; dit is geen Council-run.

    python voorbeelden/demo_live.py                 # schrijft runs/demo/ (stopt na ~40 s)
    VIEWER_PORT=8101 python viewer.py runs/demo     # in een tweede terminal, open http://127.0.0.1:8101
Optie: --snel (geen pauzes, alleen eindtoestand).
"""
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

UIT = Path(__file__).resolve().parent.parent / "runs" / "demo"
SNEL = "--snel" in sys.argv
RUN_ID = datetime.now().astimezone().isoformat(timespec="seconds") + "_demo0000"
LEDEN = ["archmage", "beast_master", "engineer", "guardian_keeper", "historian", "oracle"]
PAD = "https://mcp.example/{}/mcp"


def schrijf(naam, data):
    UIT.mkdir(parents=True, exist_ok=True)
    tmp = UIT / (naam + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    for _ in range(20):
        try:
            return os.replace(tmp, UIT / naam)
        except PermissionError:  # Windows: de viewer leest het bestand net
            time.sleep(0.02)
    os.replace(tmp, UIT / naam)


def wacht(s):
    if not SNEL:
        time.sleep(s)


trace = {"run_id": RUN_ID, "status": "bezig", "raadsleden": LEDEN, "beurten": [], "geschillen": [],
         "verbruik": {}, "modellen": {"raadsleden": "demo/klein", "koning": "demo/groot", "toolmodus": "python"}}


def beurt(spreker, soort, **v):
    trace["beurten"].append({"nr": len(trace["beurten"]) + 1, "ronde": sum(b["soort"] == "bericht" for b in trace["beurten"]) + 1,
                             "spreker": spreker, "soort": soort, **v})
    schrijf("trace.json", trace)


def live_stream(spreker, tekst, **extra):
    """Laat tekst woord per woord verschijnen in live.json."""
    woorden = tekst.split(" ")
    for i in range(1, len(woorden) + 1, 2 if SNEL else 1):
        schrijf("live.json", {"run_id": RUN_ID, "spreker": spreker, **extra, "tekst": " ".join(woorden[:i])})
        wacht(0.06)


def koning(aan, vraag, reden, open_vragen):
    trace["aan_het_woord"] = "koning"
    schrijf("live.json", {"run_id": RUN_ID, "spreker": "koning", "soort": "routering"})
    wacht(0.8)
    for i in range(1, len(vraag.split()) + 1):
        schrijf("live.json", {"run_id": RUN_ID, "spreker": "koning", "soort": "routering", "aan": aan, "vraag": " ".join(vraag.split()[:i])})
        wacht(0.04)
    schrijf("live.json", {"run_id": RUN_ID, "spreker": "koning", "soort": "routering", "aan": aan, "vraag": vraag, "reden": reden})
    wacht(0.6)
    beurt("koning", "routering", aan=aan, vraag=vraag, reden=reden, open_vragen=open_vragen)


def raadslid(rol, tools, tekst):
    trace["aan_het_woord"] = rol
    schrijf("live.json", {"run_id": RUN_ID, "spreker": rol, "soort": "bericht", "stap": "denkt"})
    wacht(0.8)
    for tool, args in tools:
        schrijf("live.json", {"run_id": RUN_ID, "spreker": rol, "soort": "bericht", "stap": "bron", "tool": tool})
        wacht(0.7)
        beurt(rol, "toolcall", tool=tool, argumenten=args, pad=PAD.format(rol))
    live_stream(rol, tekst, soort="bericht", stap="schrijft")
    beurt(rol, "bericht", tekst=tekst)


(UIT / "verdict.json").unlink(missing_ok=True)
schrijf("trace.json", trace)

koning("engineer", "[demo] Wat tonen jouw logs rond het moment dat de storing begon?",
       "[demo] Het mechanisme is nog volledig onbekend en de Engineer heeft meetbare logs.",
       ["[demo] Wat gebeurde er vlak voor de eerste storing?", "[demo] Hoe verspreidt de storing zich?"])
raadslid("engineer", [("zoek", {"term": "demo"}), ("toon", {"ids": ["ENG-901", "ENG-902"]})],
         "[demo] Opvultekst: mijn logs tonen een wijziging op dag 3 (ENG-901) en daarna een piek (ENG-902). Dit is geen echte bron.")
koning("guardian_keeper", "[demo] Klopt de piek die de Engineer noemt met jouw wachtrapporten?",
       "[demo] De Engineer heeft een eigen belang bij het datanet: een andere Rol moet dit toetsen.",
       ["[demo] Hoe verspreidt de storing zich?", "[demo] Bevestigt een tweede Rol de piek op dag 3?"])
raadslid("guardian_keeper", [("zoek_betekenis", {"vraag": "demo", "aantal": 5})],
         "[demo] Opvultekst: de wachtrapporten zien een lek vanaf dag 4 (GUA-903), een dag na ENG-901. Dat past bij elkaar.")
koning("historian", "[demo] Is dit patroon eerder voorgekomen in het archief?",
       "[demo] Voor het verloop hebben we een vergelijking met het verleden nodig.",
       ["[demo] Hoe verspreidt de storing zich?", "[demo] Is het patroon eerder voorgekomen?"])
raadslid("historian", [("lees_kennisbron", {})],
         "[demo] Opvultekst: een vergelijkbaar patroon staat in de kroniek (HIS-904), met een cyclus van zeven dagen.")
beurt("koning", "routering", aan=None, vraag=None,
      reden="[demo] Ingreep, mechanisme en verloop zijn elk door twee Rollen gedragen. Verder vragen voegt niets toe.", open_vragen=[])
trace["aan_het_woord"] = "koning"
live_stream("koning", "[demo] De Raad is het eens over een wijziging op dag 3 met een terugkerend patroon.", soort="verdict")

verdict = {
    "run_id": RUN_ID,
    "samenvatting": "[demo] Opvultekst voor de viewer: een wijziging op dag 3 (ENG-901) veroorzaakte een lek (GUA-903) dat volgens het archief terugkeert (HIS-904).",
    "oorzaak": {
        "ingreep": {"bewering": "[demo] Wijziging op dag 3.", "bewijs": ["ENG-901"], "zekerheid": 0.8},
        "mechanisme": {"bewering": "[demo] De wijziging veroorzaakt een lek in de schilden.", "bewijs": ["ENG-902", "GUA-903"], "zekerheid": 0.65},
        "verloop": {"bewering": None, "bewijs": []},
    },
    "acties": [{"actie": "[demo] De wijziging terugdraaien.", "reden": "[demo] Stopt de oorzaak.", "bewijs": ["ENG-901"]},
               {"actie": "[demo] De schilden herstellen.", "reden": "[demo] Herstelt de schade.", "bewijs": ["GUA-903"]},
               {"actie": "[demo] Wijzigingen voortaan laten toetsen.", "reden": "[demo] Voorkomt herhaling."}],
    "risicos": [{"risico": "[demo] Terugdraaien geeft een korte storing.", "mitigatie": "[demo] Buiten de piekuren doen."}],
    "voorspelling": {"dag": 10, "bewering": "[demo] Het archief toont een cyclus van zeven dagen.", "bewijs": ["HIS-904"]},
}
trace["geschillen"] = [{"onderwerp": "[demo] Is de piek een oorzaak of een gevolg?",
                        "standpunten": {"engineer": "[demo] Een gevolg van iets buiten het datanet.", "guardian_keeper": "[demo] De oorzaak van het lek."},
                        "uitkomst": "[demo] Oorzaak: het lek volgt de piek.", "bewijs": ["ENG-902", "GUA-903"]}]
beurt("koning", "bericht", tekst="[demo] Besluit: zie het Verdict.")
trace["status"], trace["aan_het_woord"] = "klaar", None
schrijf("live.json", {"run_id": RUN_ID, "spreker": None})
schrijf("trace.json", trace)
schrijf("verdict.json", verdict)
print(f"Demo klaar in {UIT}")
