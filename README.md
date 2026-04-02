# LiteLLM Spend Report & Budget-Management

Kommandozeilen-Tools zum Abrufen von Kostendaten, Verwalten von Budgets und Monitoring der Budget-Auslastung für den LiteLLM Proxy.

## Voraussetzungen

- Python 3.8+
- [uv](https://docs.astral.sh/uv/) (empfohlen) oder pip
- Zugang zum LiteLLM Proxy (URL + Master Key)

```bash
uv venv && source .venv/bin/activate
uv pip install requests tabulate python-dotenv
```

## Konfiguration

Umgebungsvariablen in `.env` oder als Export:

```bash
LITELLM_PROXY_URL=https://dein-proxy-host   # default: http://localhost:4000
LITELLM_MASTER_KEY=sk-...

# Optional für Budget-Alerts per E-Mail
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=litellm@example.com
SMTP_PASSWORD=...
SMTP_FROM=litellm@example.com
```

## Scripts

### litellm_report.py — Spend-Reports

```bash
python litellm_report.py [--keys] [--users] [--teams] [--tags] [--daily] [--all]
                         [--start YYYY-MM-DD] [--end YYYY-MM-DD]
                         [--markdown] [--output DATEI]
```

| Flag | Beschreibung |
|---|---|
| `--keys` | Spend pro Virtual Key |
| `--users` | Heavy-User-Analyse (Spend pro User aggregiert) |
| `--teams` | Spend pro Team |
| `--tags` | Spend pro Tag / Projekt |
| `--daily` | Täglicher Spend im Zeitraum |
| `--all` | Alle Reports auf einmal |
| `--start` | Startdatum (default: 30 Tage zurück) |
| `--end` | Enddatum (default: heute) |
| `--markdown` | Ausgabe als Markdown-Tabellen |
| `--output` / `-o` | Ausgabe in Datei schreiben (`.md` → automatisch Markdown) |

```bash
python litellm_report.py --all
python litellm_report.py --users
python litellm_report.py --tags --start 2026-03-01 --end 2026-03-31
python litellm_report.py --all -o report.md
```

### litellm_budget.py — Budget-Konfiguration

Erstellt oder aktualisiert Keys/Teams mit Budget-Limits und modellspezifischen Budgets.

```bash
python litellm_budget.py info              # Budget-Konfiguration anzeigen
python litellm_budget.py key-neu           # Neuen Key mit Budget erstellen
python litellm_budget.py key-update sk-... # Bestehenden Key aktualisieren
python litellm_budget.py team-neu "Name"   # Neues Team mit Budget erstellen
```

Budget-Einstellungen werden direkt im Script konfiguriert (`GESAMT_BUDGET`, `MODELL_BUDGETS`).

### litellm_assign_users.py — User-Zuordnung

Weist bestehenden Virtual Keys eine `user_id` (E-Mail-Adresse) zu, basierend auf dem Key-Alias.

```bash
python litellm_assign_users.py           # Preview (keine Änderungen)
python litellm_assign_users.py --apply   # Zuordnung durchführen
```

Die Zuordnung wird über `USER_MAP` im Script konfiguriert (key_alias → E-Mail).

### litellm_budget_alert.py — Budget-Monitoring

Prüft die Budget-Auslastung pro Kalendermonat und sendet E-Mail-Warnungen bei Schwellenwerten (80%, 90%, 100%).

```bash
python litellm_budget_alert.py --dry-run              # Preview, keine E-Mails
python litellm_budget_alert.py                         # Alerts senden
python litellm_budget_alert.py --month 2026-03         # Bestimmten Monat prüfen
python litellm_budget_alert.py --threshold 80          # Nur ab 80% anzeigen
```

Monatsbudgets werden über `MONTHLY_BUDGETS` im Script konfiguriert.

### litellm_reset_spend.py — Spend-Reset

Setzt den Spend aller Keys mit Budget auf $0 zurück. Gedacht für einen monatlichen Cronjob.

```bash
python litellm_reset_spend.py            # Alle Keys zurücksetzen
```

### Cronjobs (optional)

```cron
# Budget-Alert täglich um 8:00
0 8 * * * cd /path/to/litellm-report && python litellm_budget_alert.py

# Spend-Reset am 1. jeden Monats um 00:05
5 0 1 * * cd /path/to/litellm-report && python litellm_reset_spend.py
```

## Budget-Stufen

| Stufe | Budget/Monat | Beschreibung |
|-------|-------------|--------------|
| Power-User | $500 | Keys mit hohem Verbrauch |
| Regular | $200 | Regelmäßige Nutzer |
| Light | $50 | Gelegentliche Nutzer |
| Service | $50–300 | Geteilte Keys (Chat, Qodo, etc.) |

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
