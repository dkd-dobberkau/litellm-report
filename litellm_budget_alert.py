#!/usr/bin/env python3
"""
LiteLLM Budget-Alert (Monatsbasis)
Prüft Budget-Auslastung pro Kalendermonat und sendet E-Mail-Warnungen
über Microsoft Graph API.

Verwendung:
  python litellm_budget_alert.py              # Aktueller Monat, Alerts senden
  python litellm_budget_alert.py --dry-run    # Nur anzeigen, keine E-Mails
  python litellm_budget_alert.py --month 2026-03  # Bestimmten Monat prüfen
  python litellm_budget_alert.py --threshold 90   # Nur ab 90% anzeigen

Umgebungsvariablen (.env):
  LITELLM_PROXY_URL    URL des Proxys
  LITELLM_MASTER_KEY   Master Key
  AZURE_TENANT_ID      Azure AD Tenant ID
  AZURE_CLIENT_ID      Azure App Registration Client ID
  AZURE_CLIENT_SECRET  Azure App Registration Client Secret
  MAIL_FROM            Absender-Adresse (z.B. litellm@dkd.de)
"""

import argparse
import calendar
import os
import sys
from datetime import datetime

try:
    import requests
    from dotenv import load_dotenv
except ImportError:
    print("Bitte installieren: uv pip install requests python-dotenv")
    sys.exit(1)

load_dotenv()

PROXY_URL = os.environ.get("LITELLM_PROXY_URL", "http://localhost:4000")
MASTER_KEY = os.environ.get("LITELLM_MASTER_KEY", "")

AZURE_TENANT_ID = os.environ.get("AZURE_TENANT_ID", "")
AZURE_CLIENT_ID = os.environ.get("AZURE_CLIENT_ID", "")
AZURE_CLIENT_SECRET = os.environ.get("AZURE_CLIENT_SECRET", "")
MAIL_FROM = os.environ.get("MAIL_FROM", "litellm@dkd.de")

# Prognose-Schwellenwerte (Hochrechnung aufs Monatsende)
# Alert wird gesendet wenn die Prognose einen dieser Werte erreicht
FORECAST_THRESHOLDS = [100, 120]

# Monats-Budget pro Key (USD) — Keys ohne Eintrag werden ignoriert
MONTHLY_BUDGETS = {
    # Power-User ($500)
    "dkdrkaehm":            500.0,
    "dkdehenrich":          500.0,
    "dkdndehl":             500.0,
    # Regular ($200)
    "dkdjammann":           200.0,
    "dkdnreuschling":       200.0,
    "dkdtjanke":            200.0,
    "dkdmfriedrich":        200.0,
    # Light ($50)
    "dkdakolos":             50.0,
    "dkdjheymann":           50.0,
    "dkdczabanski":          50.0,
    "dkdmlubenka":           50.0,
    "dkdoseiffermann":       50.0,
    "dkdtwebler":            50.0,
    "dkdahildebrand":        50.0,
    "dkdgduman":             50.0,
    "dkdtmichael":           50.0,
    "dkddebert":             50.0,
    "dkdohauser":            50.0,
    "dkdltode":              50.0,
    "dkdigolman":            50.0,
    "dkdkmueller":           50.0,
    "dkdfrosnerlehnebach":   50.0,
    "dkdikartolo":           50.0,
    "dkdmgoldbach":          50.0,
    "dkdcsahner":            50.0,
    # Service-Keys
    "chat.dkd.de Developer Accounts": 500.0,
    "chat.dkd.de Management":         150.0,
    "qodo":                            50.0,
    "hosted-solr-node-14":             50.0,
    "Demo Instance User Key":          50.0,
}

MONATSNAMEN = {
    1: "Januar", 2: "Februar", 3: "März", 4: "April",
    5: "Mai", 6: "Juni", 7: "Juli", 8: "August",
    9: "September", 10: "Oktober", 11: "November", 12: "Dezember",
}


def headers():
    return {"Authorization": f"Bearer {MASTER_KEY}", "Content-Type": "application/json"}


def month_range(year, month):
    """Gibt Start- und Enddatum eines Monats zurück."""
    last_day = calendar.monthrange(year, month)[1]
    return f"{year}-{month:02d}-01", f"{year}-{month:02d}-{last_day:02d}"


def get_monthly_spend(api_key_hash, start_date, end_date):
    """Holt den Spend eines Keys für einen Kalendermonat."""
    r = requests.get(
        f"{PROXY_URL}/global/spend/logs",
        headers=headers(),
        params={"api_key": api_key_hash, "start_date": start_date, "end_date": end_date},
        timeout=10,
    )
    if not r.ok:
        return 0.0

    total = 0.0
    for entry in r.json():
        date = entry.get("date", "")
        if start_date <= date <= end_date:
            total += entry.get("spend", 0) or 0
    return total


def month_progress(year, month):
    """Anteil des Monats der bereits vergangen ist (0.0–1.0)."""
    days_in_month = calendar.monthrange(year, month)[1]
    today = datetime.now()
    if today.year == year and today.month == month:
        elapsed = min(today.day, days_in_month)
    elif (today.year, today.month) > (year, month):
        elapsed = days_in_month
    else:
        elapsed = 0
    return elapsed / days_in_month if days_in_month > 0 else 1.0


def get_keys_with_monthly_budget(year, month):
    """Lädt alle Keys mit Monatsbudget und berechnet Spend + Prognose."""
    start_date, end_date = month_range(year, month)
    progress = month_progress(year, month)

    r = requests.get(f"{PROXY_URL}/global/spend/keys", headers=headers(), timeout=10)
    r.raise_for_status()
    all_keys = r.json()

    results = []
    for item in all_keys:
        alias = item.get("key_alias") or ""
        if alias not in MONTHLY_BUDGETS:
            continue

        api_key_hash = item["api_key"]
        budget = MONTHLY_BUDGETS[alias]

        # Key-Details laden für user_id
        r2 = requests.get(
            f"{PROXY_URL}/key/info",
            headers=headers(),
            params={"key": api_key_hash},
            timeout=10,
        )
        user_id = ""
        if r2.ok:
            info = r2.json().get("info", r2.json())
            user_id = info.get("user_id", "")

        # Monats-Spend berechnen
        spend = get_monthly_spend(api_key_hash, start_date, end_date)
        percent = spend / budget * 100 if budget > 0 else 0
        forecast = percent / progress if progress > 0 else percent

        results.append({
            "alias": alias,
            "user_id": user_id or "",
            "spend": spend,
            "max_budget": budget,
            "percent": percent,
            "progress": progress,
            "forecast": forecast,
        })

    return results


def build_email(key_info, monat_label):
    """Erstellt die Alert-E-Mail mit prognosebasiertem Hinweis."""
    alias = key_info["alias"]
    user = key_info["user_id"]
    spend = key_info["spend"]
    budget = key_info["max_budget"]
    percent = key_info["percent"]
    forecast = key_info["forecast"]
    progress = key_info["progress"]
    day_pct = progress * 100

    name = user.split("@")[0].replace(".", " ").title() if user and "@" in user else alias

    if percent >= 100:
        subject = f"LiteLLM {monat_label}: {alias} — Budget aufgebraucht ({percent:.0f}%)"
        hinweis = (
            "Dein Budget für diesen Monat ist aufgebraucht. "
            "Falls du weiterhin Zugriff benötigst, melde dich kurz — "
            "wir finden eine Lösung."
        )
    elif forecast >= 120:
        subject = f"LiteLLM {monat_label}: {alias} — Prognose {forecast:.0f}%"
        hinweis = (
            f"Bei {day_pct:.0f}% des Monats bist du schon bei {percent:.0f}% deines Budgets. "
            f"Wenn es so weitergeht, landest du bei ca. {forecast:.0f}% zum Monatsende. "
            "Vielleicht lohnt es sich, den Verbrauch im Auge zu behalten."
        )
    elif forecast >= 100:
        subject = f"LiteLLM {monat_label}: {alias} — Prognose {forecast:.0f}%"
        hinweis = (
            f"Du bist bei {percent:.0f}% deines Budgets ({day_pct:.0f}% des Monats vergangen) — "
            f"die Hochrechnung liegt bei ca. {forecast:.0f}% zum Monatsende. "
            "Kein Stress, nur ein kurzer Hinweis, damit es keine Überraschungen gibt."
        )
    else:
        subject = f"LiteLLM {monat_label}: {alias} — {percent:.0f}% verbraucht"
        hinweis = (
            f"Alles im grünen Bereich — bei {day_pct:.0f}% des Monats liegst du "
            f"bei {percent:.0f}% deines Budgets (Prognose: {forecast:.0f}%)."
        )

    body = f"""Hi {name},

hier ein kurzer Überblick zu deinem LiteLLM-Key "{alias}" im {monat_label}:

  Verbrauch:      ${spend:,.2f} USD
  Budget:         ${budget:,.2f} USD
  Auslastung:     {percent:.1f}%
  Monatsfortschritt: {day_pct:.0f}%
  Prognose:       {forecast:.0f}% zum Monatsende

{hinweis}

Viele Grüße
LiteLLM Budget-Monitor

---
Automatisch generiert · {PROXY_URL}
"""
    return subject, body


def get_graph_token():
    """Holt ein Access-Token über OAuth2 Client Credentials Flow."""
    r = requests.post(
        f"https://login.microsoftonline.com/{AZURE_TENANT_ID}/oauth2/v2.0/token",
        data={
            "client_id": AZURE_CLIENT_ID,
            "client_secret": AZURE_CLIENT_SECRET,
            "scope": "https://graph.microsoft.com/.default",
            "grant_type": "client_credentials",
        },
        timeout=10,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def send_email(to_addr, subject, body, dry_run=False):
    """Sendet eine E-Mail über Microsoft Graph API."""
    if dry_run:
        print(f"    [DRY-RUN] E-Mail an {to_addr}: {subject}")
        return True

    if not all([AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET]):
        print(f"    ⚠️  Azure nicht konfiguriert — E-Mail an {to_addr} übersprungen")
        return False

    try:
        token = get_graph_token()
        r = requests.post(
            f"https://graph.microsoft.com/v1.0/users/{MAIL_FROM}/sendMail",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json={
                "message": {
                    "subject": subject,
                    "body": {"contentType": "Text", "content": body},
                    "toRecipients": [
                        {"emailAddress": {"address": to_addr}}
                    ],
                },
                "saveToSentItems": False,
            },
            timeout=10,
        )
        r.raise_for_status()
        print(f"    ✓ E-Mail an {to_addr} gesendet")
        return True
    except requests.exceptions.HTTPError as e:
        detail = ""
        try:
            detail = e.response.json().get("error", {}).get("message", "")
        except Exception:
            detail = str(e)
        print(f"    ✗ E-Mail an {to_addr} fehlgeschlagen: {detail}")
        return False
    except Exception as e:
        print(f"    ✗ E-Mail an {to_addr} fehlgeschlagen: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="LiteLLM Budget-Alert (Monatsbasis)")
    parser.add_argument("--dry-run", action="store_true", help="Nur anzeigen, keine E-Mails senden")
    parser.add_argument("--month", metavar="YYYY-MM", help="Monat prüfen (default: aktueller Monat)")
    parser.add_argument("--threshold", type=int, default=0,
                        help="Nur Keys ab diesem Schwellenwert anzeigen (default: 0 = alle)")
    args = parser.parse_args()

    if not MASTER_KEY:
        print("Fehler: LITELLM_MASTER_KEY nicht gesetzt")
        sys.exit(1)

    # Monat bestimmen
    if args.month:
        year, month = map(int, args.month.split("-"))
    else:
        now = datetime.now()
        year, month = now.year, now.month

    monat_label = f"{MONATSNAMEN[month]} {year}"
    start_date, end_date = month_range(year, month)

    print(f"🔍 Budget-Auslastung für {monat_label} ({start_date} → {end_date})\n")

    keys = get_keys_with_monthly_budget(year, month)

    if not keys:
        print("Keine Keys mit Monatsbudget gefunden.")
        print(f"   Budgets in MONTHLY_BUDGETS konfigurieren ({len(MONTHLY_BUDGETS)} definiert)")
        return

    alerts_sent = 0
    for key in sorted(keys, key=lambda k: k["forecast"], reverse=True):
        forecast = key["forecast"]
        percent = key["percent"]
        alias = key["alias"] or "unbekannt"
        user = key["user_id"]

        if forecast < args.threshold:
            continue

        # Status basierend auf Prognose
        if percent >= 100:
            status = "🔴"
        elif forecast >= 120:
            status = "🟠"
        elif forecast >= 100:
            status = "🟡"
        else:
            status = "🟢"

        print(f"  {status} {alias:30s} ${key['spend']:>10,.2f} / ${key['max_budget']:>10,.2f}  ({percent:.1f}% → Prognose {forecast:.0f}%)")

        # E-Mail senden wenn Prognose-Schwellenwert erreicht oder Budget überschritten
        should_alert = percent >= 100 or any(forecast >= t for t in FORECAST_THRESHOLDS)
        if should_alert:
            to_addr = user if user and "@" in user else ""
            if to_addr:
                subject, body = build_email(key, monat_label)
                if send_email(to_addr, subject, body, dry_run=args.dry_run):
                    alerts_sent += 1

    print(f"\n   {len(keys)} Keys geprüft für {monat_label}, {alerts_sent} Alerts gesendet")


if __name__ == "__main__":
    main()
