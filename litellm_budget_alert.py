#!/usr/bin/env python3
"""
LiteLLM Budget-Alert (Monatsbasis)
Prüft Budget-Auslastung pro Kalendermonat und sendet E-Mail-Warnungen.

Verwendung:
  python litellm_budget_alert.py              # Aktueller Monat, Alerts senden
  python litellm_budget_alert.py --dry-run    # Nur anzeigen, keine E-Mails
  python litellm_budget_alert.py --month 2026-03  # Bestimmten Monat prüfen
  python litellm_budget_alert.py --threshold 90   # Nur ab 90% anzeigen

Umgebungsvariablen (.env):
  LITELLM_PROXY_URL    URL des Proxys
  LITELLM_MASTER_KEY   Master Key
  SMTP_HOST            SMTP-Server (z.B. smtp.dkd.de)
  SMTP_PORT            SMTP-Port (default: 587)
  SMTP_USER            SMTP-Benutzername
  SMTP_PASSWORD        SMTP-Passwort
  SMTP_FROM            Absender-Adresse (z.B. litellm@dkd.de)
"""

import argparse
import calendar
import os
import smtplib
import sys
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

try:
    import requests
    from dotenv import load_dotenv
except ImportError:
    print("Bitte installieren: uv pip install requests python-dotenv")
    sys.exit(1)

load_dotenv()

PROXY_URL = os.environ.get("LITELLM_PROXY_URL", "http://localhost:4000")
MASTER_KEY = os.environ.get("LITELLM_MASTER_KEY", "")

SMTP_HOST = os.environ.get("SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
SMTP_FROM = os.environ.get("SMTP_FROM", "litellm@dkd.de")

# Schwellenwerte in Prozent — bei jedem wird eine E-Mail gesendet
ALERT_THRESHOLDS = [80, 90, 100]

# Monats-Budget pro Key (USD) — Keys ohne Eintrag werden ignoriert
MONTHLY_BUDGETS = {
    # Power-User ($500)
    "dkdrkaehm":            500.0,
    "dkdjammann":           500.0,
    "dkdndehl":             500.0,
    # Regular ($200)
    "dkdnreuschling":       200.0,
    "dkdehenrich":          200.0,
    "dkdakolos":            200.0,
    "dkdjheymann":          200.0,
    "dkdczabanski":         200.0,
    "dkdmlubenka":          200.0,
    "dkdtjanke":            200.0,
    "dkdmfriedrich":        200.0,
    "dkdoseiffermann":      200.0,
    # Light ($50)
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
    "chat.dkd.de Developer Accounts": 300.0,
    "chat.dkd.de Management":         300.0,
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


def get_keys_with_monthly_budget(year, month):
    """Lädt alle Keys mit Monatsbudget und berechnet den Monats-Spend."""
    start_date, end_date = month_range(year, month)

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

        results.append({
            "alias": alias,
            "user_id": user_id or "",
            "spend": spend,
            "max_budget": budget,
            "percent": spend / budget * 100 if budget > 0 else 0,
        })

    return results


def build_email(key_info, monat_label):
    """Erstellt die Alert-E-Mail."""
    alias = key_info["alias"]
    user = key_info["user_id"]
    spend = key_info["spend"]
    budget = key_info["max_budget"]
    percent = key_info["percent"]

    subject = f"LiteLLM Budget-Warnung {monat_label}: {alias} bei {percent:.0f}%"

    name = user.split("@")[0].replace(".", " ").title() if user and "@" in user else alias

    body = f"""Hallo {name},

dein LiteLLM API-Key "{alias}" hat im {monat_label} {percent:.0f}% des Monatsbudgets erreicht.

  Verbrauch {monat_label}:  ${spend:,.2f} USD
  Monatsbudget:             ${budget:,.2f} USD
  Auslastung:               {percent:.1f}%

{"⚠️  Das Monatsbudget ist aufgebraucht! Weitere Requests werden bis zum Monatswechsel abgelehnt." if percent >= 100 else "Bitte achte auf deinen Verbrauch, um eine Unterbrechung zu vermeiden."}

---
Diese Nachricht wurde automatisch vom LiteLLM Budget-Alert gesendet.
Proxy: {PROXY_URL}
"""
    return subject, body


def send_email(to_addr, subject, body, dry_run=False):
    """Sendet eine E-Mail über SMTP."""
    if dry_run:
        print(f"    [DRY-RUN] E-Mail an {to_addr}: {subject}")
        return True

    if not all([SMTP_HOST, SMTP_FROM]):
        print(f"    ⚠️  SMTP nicht konfiguriert — E-Mail an {to_addr} übersprungen")
        return False

    msg = MIMEMultipart()
    msg["From"] = SMTP_FROM
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
            server.starttls()
            if SMTP_USER and SMTP_PASSWORD:
                server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
        print(f"    ✓ E-Mail an {to_addr} gesendet")
        return True
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
    for key in sorted(keys, key=lambda k: k["percent"], reverse=True):
        percent = key["percent"]
        alias = key["alias"] or "unbekannt"
        user = key["user_id"]

        if percent < args.threshold:
            continue

        # Status-Anzeige
        if percent >= 100:
            status = "🔴"
        elif percent >= 90:
            status = "🟠"
        elif percent >= 80:
            status = "🟡"
        else:
            status = "🟢"

        print(f"  {status} {alias:30s} ${key['spend']:>10,.2f} / ${key['max_budget']:>10,.2f}  ({percent:.1f}%)")

        # E-Mail senden wenn Schwellenwert erreicht
        for threshold in sorted(ALERT_THRESHOLDS, reverse=True):
            if percent >= threshold:
                to_addr = user if user and "@" in user else ""
                if not to_addr:
                    break
                subject, body = build_email(key, monat_label)
                if send_email(to_addr, subject, body, dry_run=args.dry_run):
                    alerts_sent += 1
                break

    print(f"\n   {len(keys)} Keys geprüft für {monat_label}, {alerts_sent} Alerts gesendet")


if __name__ == "__main__":
    main()
