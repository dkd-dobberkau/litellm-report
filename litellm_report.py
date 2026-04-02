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
TABLE_FMT = "rounded_outline"


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
        info = key_info(item.get("api_key", ""))
        rows.append([
            item.get("key_alias") or item.get("api_key", "")[:12] + "...",
            info.get("team_id", "—"),
            info.get("user_id", "—"),
            f"${item.get('total_spend', item.get('total_cost', 0)):.4f}",
            info.get("models", []),
        ])

    rows.sort(key=lambda x: float(x[3].replace("$", "")), reverse=True)

    if TABLE_FMT == "github":
        print("\n## 📊 Spend pro Virtual Key\n")
    else:
        print("\n📊 Spend pro Virtual Key")
    print(tabulate(rows, headers=["Key / Alias", "Team", "User", "Kosten (USD)", "Modelle"], tablefmt=TABLE_FMT))


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

    if TABLE_FMT == "github":
        print(f"\n## 🏷️  Spend pro Tag/Projekt ({start_date} → {end_date})\n")
    else:
        print(f"\n🏷️  Spend pro Tag/Projekt ({start_date} → {end_date})")
    print(tabulate(rows, headers=["Tag", "Kosten (USD)", "Requests"], tablefmt=TABLE_FMT))


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

    if TABLE_FMT == "github":
        print(f"\n## 📅 Täglicher Spend ({start_date} → {end_date})\n")
    else:
        print(f"\n📅 Täglicher Spend ({start_date} → {end_date})")
    print(tabulate(rows, headers=["Datum", "Kosten (USD)", "Tokens"], tablefmt=TABLE_FMT))
    print(f"\n   Gesamt: ${total:.4f} USD")


def key_info(api_key_hash):
    """Holt Details zu einem Key über /key/info."""
    url = f"{PROXY_URL}/key/info"
    try:
        r = requests.get(url, headers=headers(), params={"key": api_key_hash}, timeout=10)
        r.raise_for_status()
        data = r.json()
        return data.get("info", data)
    except Exception:
        return {}


def report_users():
    """Heavy-User-Analyse: Spend pro User aggregiert über alle Keys"""
    data = get("/global/spend/keys")

    if not data:
        print("\n⚠️  Keine Key-Daten gefunden.")
        return

    # Key-Details laden um user_id zu erhalten
    print("\n   Lade Key-Details...", end="", flush=True)
    users = {}
    for item in data:
        spend = item.get("total_spend", 0) or 0
        info = key_info(item.get("api_key", ""))
        uid = info.get("user_id") or "—"
        models = info.get("models") or []
        if uid not in users:
            users[uid] = {"spend": 0.0, "keys": 0, "models": set()}
        users[uid]["spend"] += spend
        users[uid]["keys"] += 1
        for m in models:
            users[uid]["models"].add(m)
    print(" fertig.")

    gesamt = sum(u["spend"] for u in users.values()) or 1.0

    rows = []
    for uid, info in users.items():
        anteil = info["spend"] / gesamt * 100
        rows.append([
            uid,
            f"${info['spend']:.4f}",
            f"{anteil:.1f}%",
            info["keys"],
            ", ".join(sorted(info["models"])) or "—",
        ])

    rows.sort(key=lambda x: float(x[1].replace("$", "")), reverse=True)

    if TABLE_FMT == "github":
        print("\n## 👤 Spend pro User (Heavy-User-Analyse)\n")
    else:
        print("\n👤 Spend pro User (Heavy-User-Analyse)")
    print(tabulate(rows, headers=["User", "Kosten (USD)", "Anteil", "Keys", "Modelle"], tablefmt=TABLE_FMT))
    print(f"\n   Gesamt: ${gesamt:.4f} USD  |  {len(users)} User  |  {len(data)} Keys")


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

    if TABLE_FMT == "github":
        print("\n## 👥 Spend pro Team\n")
    else:
        print("\n👥 Spend pro Team")
    print(tabulate(rows, headers=["Team", "Kosten (USD)", "Budget (USD)"], tablefmt=TABLE_FMT))


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
    parser.add_argument("--users",  action="store_true", help="Heavy-User-Analyse")
    parser.add_argument("--teams",  action="store_true", help="Spend pro Team")
    parser.add_argument("--tags",   action="store_true", help="Spend pro Tag/Projekt")
    parser.add_argument("--daily",  action="store_true", help="Täglicher Spend")
    parser.add_argument("--all",    action="store_true", help="Alle Reports")
    parser.add_argument("--markdown", action="store_true", help="Ausgabe als Markdown")
    parser.add_argument("--output", "-o", metavar="DATEI", help="Ausgabe in Datei schreiben")
    parser.add_argument("--start",  default=(datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d"),
                        help="Startdatum (default: -30 Tage)")
    parser.add_argument("--end",    default=datetime.now().strftime("%Y-%m-%d"),
                        help="Enddatum (default: heute)")

    args = parser.parse_args()

    global TABLE_FMT
    if args.markdown or (args.output and args.output.endswith(".md")):
        TABLE_FMT = "github"

    if args.output:
        sys.stdout = open(args.output, "w", encoding="utf-8")

    if not MASTER_KEY:
        print("❌ LITELLM_MASTER_KEY nicht gesetzt.")
        print("   export LITELLM_MASTER_KEY=sk-...")
        sys.exit(1)

    if TABLE_FMT == "github":
        print(f"# LiteLLM Spend Report\n")
        print(f"- **Proxy:** {PROXY_URL}")
        print(f"- **Zeitraum:** {args.start} → {args.end}")
    else:
        print(f"🔌 Proxy: {PROXY_URL}")
        print(f"📆 Zeitraum: {args.start} → {args.end}")

    if args.all or args.keys:
        report_keys()
    if args.all or args.users:
        report_users()
    if args.all or args.teams:
        report_teams()
    if args.all or args.tags:
        report_tags(args.start, args.end)
    if args.all or args.daily:
        report_global(args.start, args.end)

    if not any([args.keys, args.users, args.teams, args.tags, args.daily, args.all]):
        parser.print_help()


if __name__ == "__main__":
    main()
