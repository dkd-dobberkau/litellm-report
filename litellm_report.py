#!/usr/bin/env python3
"""
LiteLLM Spend Report
Ruft Key-, Team- und Tag-Daten vom LiteLLM Proxy ab und gibt eine Tabelle aus.
"""

import argparse
import os
import sys
from datetime import datetime, timedelta

try:
    import requests
    from tabulate import tabulate
except ImportError:
    print("Bitte installieren: pip install requests tabulate")
    sys.exit(1)


# ── Konfiguration ──────────────────────────────────────────────────────────────
PROXY_URL = os.environ.get("LITELLM_PROXY_URL", "http://localhost:4000")
MASTER_KEY = os.environ.get("LITELLM_MASTER_KEY", "")


def headers():
    return {"Authorization": f"Bearer {MASTER_KEY}", "Content-Type": "application/json"}


def get(path, params=None):
    url = f"{PROXY_URL}{path}"
    try:
        r = requests.get(url, headers=headers(), params=params, timeout=10)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        print(f"❌ Keine Verbindung zu {PROXY_URL}")
        sys.exit(1)
    except requests.exceptions.HTTPError as e:
        try:
            detail = r.json().get("detail", {})
            error_msg = detail.get("error", "") if isinstance(detail, dict) else str(detail)
        except Exception:
            error_msg = r.text
        if "Enterprise" in error_msg or "LITELLM_LICENSE" in error_msg:
            print(f"⚠️  {path} erfordert LiteLLM Enterprise — übersprungen.")
            return None
        print(f"❌ HTTP Fehler {r.status_code}: {error_msg}")
        sys.exit(1)


# ── Report-Funktionen ──────────────────────────────────────────────────────────
def report_keys():
    """Spend pro Virtual Key"""
    data = get("/global/spend/keys")

    rows = []
    for item in data:
        rows.append([
            item.get("key_alias") or item.get("api_key", "")[:12] + "...",
            item.get("team_id", "—"),
            item.get("user_id", "—"),
            f"${item.get('total_spend', item.get('total_cost', 0)):.4f}",
            item.get("models", []),
        ])

    rows.sort(key=lambda x: float(x[3].replace("$", "")), reverse=True)

    print("\n📊 Spend pro Virtual Key")
    print(tabulate(rows, headers=["Key / Alias", "Team", "User", "Kosten (USD)", "Modelle"], tablefmt="rounded_outline"))


def report_tags(start_date, end_date):
    """Spend pro Tag / Projekt"""
    data = get("/global/spend/tags", params={"start_date": start_date, "end_date": end_date})

    if not data:
        print("\n⚠️  Keine Tag-Daten gefunden. Tags in Requests noch nicht gesetzt?")
        return

    # API returns a dict with "spend_per_tag" list
    tag_list = data.get("spend_per_tag", []) if isinstance(data, dict) else data

    if not tag_list:
        print("\n⚠️  Keine Tag-Daten gefunden. Tags in Requests noch nicht gesetzt?")
        return

    rows = []
    for item in tag_list:
        rows.append([
            item.get("name", item.get("individual_request_tag", "—")),
            f"${item.get('spend', item.get('total_spend', 0)):.4f}",
            item.get("log_count", "—"),
        ])

    rows.sort(key=lambda x: float(x[1].replace("$", "")), reverse=True)

    print(f"\n🏷️  Spend pro Tag/Projekt ({start_date} → {end_date})")
    print(tabulate(rows, headers=["Tag", "Kosten (USD)", "Requests"], tablefmt="rounded_outline"))


def report_global(start_date, end_date):
    """Gesamtreport nach Datum"""
    data = get("/global/spend/report", params={"start_date": start_date, "end_date": end_date})

    if data is None:
        return
    if not data:
        print("\n⚠️  Keine Daten für den Zeitraum gefunden.")
        return

    rows = []
    total = 0.0
    for item in data:
        cost = item.get("total_cost", 0)
        total += cost
        rows.append([
            item.get("group_by_day", item.get("date", "—")),
            f"${cost:.4f}",
            item.get("total_tokens", "—"),
        ])

    print(f"\n📅 Täglicher Spend ({start_date} → {end_date})")
    print(tabulate(rows, headers=["Datum", "Kosten (USD)", "Tokens"], tablefmt="rounded_outline"))
    print(f"\n   Gesamt: ${total:.4f} USD")


def report_teams():
    """Spend pro Team"""
    data = get("/global/spend/teams")

    if not data:
        print("\n⚠️  Keine Team-Daten gefunden. Teams noch nicht angelegt?")
        return

    # API returns a dict with "total_spend_per_team" list
    team_list = data.get("total_spend_per_team", []) if isinstance(data, dict) else data

    if not team_list:
        print("\n⚠️  Keine Team-Daten gefunden. Teams noch nicht angelegt?")
        return

    rows = []
    for item in team_list:
        rows.append([
            item.get("team_alias") or item.get("team_id", "—"),
            f"${item.get('total_spend', item.get('spend', 0)):.4f}",
            f"${item.get('max_budget', 0) or 0:.2f}" if item.get("max_budget") else "—",
        ])

    rows.sort(key=lambda x: float(x[1].replace("$", "")), reverse=True)

    print("\n👥 Spend pro Team")
    print(tabulate(rows, headers=["Team", "Kosten (USD)", "Budget (USD)"], tablefmt="rounded_outline"))


# ── CLI ────────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="LiteLLM Spend Report",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Umgebungsvariablen:
  LITELLM_PROXY_URL   URL des Proxys (default: http://localhost:4000)
  LITELLM_MASTER_KEY  Master Key für die API

Beispiele:
  python litellm_report.py --all
  python litellm_report.py --keys --teams
  python litellm_report.py --tags --start 2026-03-01 --end 2026-03-20
        """
    )
    parser.add_argument("--keys",   action="store_true", help="Spend pro Virtual Key")
    parser.add_argument("--teams",  action="store_true", help="Spend pro Team")
    parser.add_argument("--tags",   action="store_true", help="Spend pro Tag/Projekt")
    parser.add_argument("--daily",  action="store_true", help="Täglicher Spend")
    parser.add_argument("--all",    action="store_true", help="Alle Reports")
    parser.add_argument("--start",  default=(datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d"),
                        help="Startdatum (default: -30 Tage)")
    parser.add_argument("--end",    default=datetime.now().strftime("%Y-%m-%d"),
                        help="Enddatum (default: heute)")

    args = parser.parse_args()

    if not MASTER_KEY:
        print("❌ LITELLM_MASTER_KEY nicht gesetzt.")
        print("   export LITELLM_MASTER_KEY=sk-...")
        sys.exit(1)

    print(f"🔌 Proxy: {PROXY_URL}")
    print(f"📆 Zeitraum: {args.start} → {args.end}")

    if args.all or args.keys:
        report_keys()
    if args.all or args.teams:
        report_teams()
    if args.all or args.tags:
        report_tags(args.start, args.end)
    if args.all or args.daily:
        report_global(args.start, args.end)

    if not any([args.keys, args.teams, args.tags, args.daily, args.all]):
        parser.print_help()


if __name__ == "__main__":
    main()
