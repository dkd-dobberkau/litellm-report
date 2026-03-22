# LiteLLM Spend Report

Kommandozeilen-Script zum Abrufen und Anzeigen von Kostendaten aus dem LiteLLM Proxy — aufgeschlüsselt nach Virtual Keys, Teams, Projekten (Tags) und Tagen.

## Voraussetzungen

- Python 3.8+
- [uv](https://docs.astral.sh/uv/) (empfohlen) oder pip
- Zugang zum LiteLLM Proxy (URL + Master Key)

```bash
uv venv && source .venv/bin/activate
uv pip install requests tabulate
```

## Konfiguration

Zwei Umgebungsvariablen müssen gesetzt sein:

```bash
export LITELLM_PROXY_URL=https://dein-proxy-host   # default: http://localhost:4000
export LITELLM_MASTER_KEY=sk-...
```

Den Master Key findest du je nach Setup:
- in der `.env`-Datei des Proxys (`LITELLM_MASTER_KEY=...`)
- im `config.yaml` unter `general_settings.master_key`
- oder per `docker inspect <container> | grep LITELLM_MASTER_KEY`

## Verwendung

```bash
python litellm_report.py [--keys] [--teams] [--tags] [--daily] [--all]
                         [--start YYYY-MM-DD] [--end YYYY-MM-DD]
```

### Optionen

| Flag | Beschreibung |
|---|---|
| `--keys` | Spend pro Virtual Key |
| `--teams` | Spend pro Team |
| `--tags` | Spend pro Tag / Projekt |
| `--daily` | Täglicher Spend im Zeitraum |
| `--all` | Alle vier Reports auf einmal |
| `--start` | Startdatum (default: 30 Tage zurück) |
| `--end` | Enddatum (default: heute) |

### Beispiele

```bash
# Alle Reports, letzten 30 Tage
python litellm_report.py --all

# Nur Keys und Teams
python litellm_report.py --keys --teams

# Tag-Auswertung für März 2026
python litellm_report.py --tags --start 2026-03-01 --end 2026-03-31

# Tagesdetails für eine bestimmte Woche
python litellm_report.py --daily --start 2026-03-10 --end 2026-03-16
```

## Ausgabe

```
🔌 Proxy: https://dein-proxy-host
📆 Zeitraum: 2026-03-01 → 2026-03-31

📊 Spend pro Virtual Key
╭──────────────────┬──────────────────┬──────────────╮
│ Key / Alias      │ Team             │ Kosten (USD) │
├──────────────────┼──────────────────┼──────────────┤
│ dev-team-key     │ team-development │ $1.234,56    │
│ consulting-key   │ team-consulting  │ $456,78      │
╰──────────────────┴──────────────────┴──────────────╯

👥 Spend pro Team
╭──────────────────┬──────────────────┬───────────────╮
│ Team             │ Kosten (USD)     │ Budget (USD)  │
├──────────────────┼──────────────────┼───────────────┤
│ team-development │ $1.234,56        │ $1.500,00     │
│ team-consulting  │ $456,78          │ —             │
╰──────────────────┴──────────────────┴───────────────╯
```

## Fehlermeldungen

**„Keine Team-Daten gefunden"** — Teams sind im Proxy noch nicht angelegt. Virtual Keys müssen einer `team_id` zugeordnet sein.

**„Keine Tag-Daten gefunden"** — Requests enthalten noch keine Tags. Tags werden per `extra_body.metadata.tags` im API-Call mitgegeben:

```python
response = client.chat.completions.create(
    model="claude-sonnet",
    messages=[...],
    extra_body={
        "metadata": {
            "tags": ["project:kula", "team:development", "env:production"]
        }
    }
)
```

**„Keine Verbindung"** — `LITELLM_PROXY_URL` prüfen oder VPN-Zugang sicherstellen.

## Tag-Konvention (Empfehlung)

Für einheitliches Reporting empfiehlt sich folgende Konvention:

```
project:<name>    →  project:kula, project:starfruit, project:kunde-xyz
team:<name>       →  team:development, team:consulting
env:<name>        →  env:production, env:dev, env:staging
```

## Weiterführende Links

- [LiteLLM Spend Tracking Docs](https://docs.litellm.ai/docs/proxy/cost_tracking)
- [Request Tags](https://docs.litellm.ai/docs/proxy/request_tags)
- [Budget & Rate Limits](https://docs.litellm.ai/docs/proxy/users)
