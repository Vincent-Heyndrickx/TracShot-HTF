# Dev-regels: branches, main en runs

Voor iedereen die code aanpast: Vincent, Nathan, Claude en de GPT/OpenClaw-agents.
Doel: niet op elkaars bestanden botsen, en `main` altijd draaibaar houden.

## Het principe

| Wat | Waar | Waarvoor |
|---|---|---|
| **Run-copy** | `/srv/tracshot-htf` op de VPS, altijd op `main` | Alleen runs (`uv run council`), viewer, validate. **Hier nooit code aanpassen.** |
| **Eigen branch** | eigen clone of worktree, per persoon/agent | Alle codewijzigingen |
| **`main`** | GitHub `origin/main` | De gedeelde waarheid. Elke wijziging komt hier via een eigen branch. |

## Branchnamen

`<wie>/<onderwerp>`, kort, kleine letters:

- `claude/koning-prompt`, `claude/toolmodus`
- `gpt/viewer-avatars`, `gpt/vault`
- `nathan/openclaw-agents`, `vincent/pitch`

Eén branch per onderwerp. Klaar = naar main, en daarna een nieuwe branch voor het volgende.

## Werkwijze (elke keer)

```bash
# 1. Start altijd vanaf de laatste main
git fetch origin
git switch -c <wie>/<onderwerp> origin/main

# 2. Werk en commit klein en vaak
git add <bestanden>          # nooit .env, kennisbronnen/, runs/, vault/
git commit -m "Korte, duidelijke boodschap"

# 3. Vóór het pushen: bijwerken met wat anderen ondertussen op main zetten
git fetch origin
git rebase origin/main       # conflict? Los het op in JOUW branch, nooit op main

# 4. Controleren
uv run python -c "import council"     # importeert zonder fouten
uv run validate voorbeeld >/dev/null; echo ok   # validator draait (voorbeeld is bewust rood)

# 5. Naar main pushen (alleen fast-forward) en de branch ook bewaren
git push origin HEAD:main
git push origin <wie>/<onderwerp>
```

Wordt `git push origin HEAD:main` geweigerd (`non-fast-forward`)? Dan heeft iemand anders net gepusht.
Doe stap 3 opnieuw (fetch + rebase) en push dan opnieuw. **Nooit `--force` naar main.**

## Run-copy bijwerken (na elke push naar main)

```bash
cd /srv/tracshot-htf
git pull --ff-only origin main
uv sync -q                   # alleen nodig als pyproject.toml/uv.lock veranderde
```

`git pull --ff-only` faalt? Dan heeft iemand in de run-copy zelf iets aangepast. Niet blind overschrijven:
eerst `git status` en `git diff` bekijken, de wijziging naar een eigen branch verhuizen, pas daarna opnieuw pullen.

## Botsingen vermijden

- **Meld waar je aan werkt**, in de vault (`vault/`) of in de teamchat: branch + bestanden.
- **Eén eigenaar per bestand tegelijk.** Moeten twee mensen in hetzelfde bestand (vooral `council.py`), spreek af wie eerst gaat,
  of werk in verschillende functies en houd de commits klein.
- Herformatteer geen code die je niet aanpast (geen massale whitespace-, import- of line-ending-wijzigingen): dat geeft valse conflicts.
- Line endings: altijd LF. Op Windows: `git config core.autocrlf input`.

## Wat nooit in een commit hoort

- `.env` of tokens (teamkey, OpenClaw-gateway-token, OAuth)
- `kennisbronnen/`, `LEESMIJ.md` uit pack.zip, `runs/`, `vault/`, `instructions.md`
- Inhoud uit de Kennisbronnen in code of prompts (record-ID's, feiten): spelregel van de challenge

## Officiële run en inleveren (vóór 16:00)

- De run die we inleveren gebeurt **alleen in de run-copy op `main`**, zonder `COUNCIL_OUTPUT_DIR`, zodat `trace.json` en
  `verdict.json` in de root komen.
- `uv run validate` moet groen zijn. Daarna commit je `trace.json` en `verdict.json` via een eigen branch
  (`<wie>/verdict-run`) en push je die naar main.
- `trace.json` nooit met de hand bewerken. In `verdict.json` mogen alleen kleine fixes (bv. koppeltekens).
- Afspraak: vanaf **15:30** geen codewijzigingen meer op main, alleen nog de officiële run.
