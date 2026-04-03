#!/usr/bin/env python3
"""
LiteLLM Spend Report
Ruft Key-, Team- und Tag-Daten vom LiteLLM Proxy ab und gibt eine Tabelle aus.
"""

import argparse
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

try:
    import duckdb
    import pyarrow as pa
    import pyarrow.parquet as pq
    import requests
    from dotenv import load_dotenv
    from tabulate import tabulate
except ImportError:
    print("Bitte installieren: uv pip install requests tabulate python-dotenv duckdb pyarrow")
    sys.exit(1)

load_dotenv()


# ── Konfiguration ──────────────────────────────────────────────────────────────
PROXY_URL = os.environ.get("LITELLM_PROXY_URL", "http://localhost:4000")
MASTER_KEY = os.environ.get("LITELLM_MASTER_KEY", "")
TABLE_FMT = "rounded_outline"
DATA_DIR = Path(__file__).parent / "data" / "parquet"


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
def fetch_keys():
    """Holt Key-Daten und gibt normalisierte Dicts zurück."""
    data = get("/global/spend/keys")
    if not data:
        return []
    rows = []
    for item in data:
        info = key_info(item.get("api_key", ""))
        models = info.get("models") or []
        rows.append({
            "key_alias": item.get("key_alias") or item.get("api_key", "")[:12] + "...",
            "team_id": info.get("team_id", ""),
            "user_id": info.get("user_id", ""),
            "spend": float(item.get("total_spend", item.get("total_cost", 0)) or 0),
            "models": ", ".join(models) if models else "",
        })
    return rows


def report_keys():
    """Spend pro Virtual Key"""
    data = fetch_keys()
    rows = [[r["key_alias"], r["team_id"] or "—", r["user_id"] or "—",
             f"${r['spend']:.4f}", r["models"]] for r in data]
    rows.sort(key=lambda x: float(x[3].replace("$", "")), reverse=True)

    if TABLE_FMT == "github":
        print("\n## 📊 Spend pro Virtual Key\n")
    else:
        print("\n📊 Spend pro Virtual Key")
    print(tabulate(rows, headers=["Key / Alias", "Team", "User", "Kosten (USD)", "Modelle"], tablefmt=TABLE_FMT))


def fetch_tags(start_date, end_date):
    """Holt Tag-Daten und gibt normalisierte Dicts zurück."""
    data = get("/global/spend/tags", params={"start_date": start_date, "end_date": end_date})
    if not data:
        return []
    tag_list = data.get("spend_per_tag", []) if isinstance(data, dict) else data
    if not tag_list:
        return []
    rows = []
    for item in tag_list:
        rows.append({
            "tag_name": item.get("name", item.get("individual_request_tag", "")),
            "spend": float(item.get("spend", item.get("total_spend", 0)) or 0),
            "request_count": int(item.get("log_count", 0) or 0),
        })
    return rows


def report_tags(start_date, end_date):
    """Spend pro Tag / Projekt"""
    data = fetch_tags(start_date, end_date)
    if not data:
        print("\n⚠️  Keine Tag-Daten gefunden. Tags in Requests noch nicht gesetzt?")
        return

    rows = [[r["tag_name"], f"${r['spend']:.4f}", r["request_count"]] for r in data]
    rows.sort(key=lambda x: float(x[1].replace("$", "")), reverse=True)

    if TABLE_FMT == "github":
        print(f"\n## 🏷️  Spend pro Tag/Projekt ({start_date} → {end_date})\n")
    else:
        print(f"\n🏷️  Spend pro Tag/Projekt ({start_date} → {end_date})")
    print(tabulate(rows, headers=["Tag", "Kosten (USD)", "Requests"], tablefmt=TABLE_FMT))


def fetch_daily(start_date, end_date):
    """Holt tägliche Spend-Daten und gibt normalisierte Dicts zurück."""
    data = get("/global/spend/report", params={"start_date": start_date, "end_date": end_date})
    if not data:
        return []
    rows = []
    for item in data:
        rows.append({
            "day": item.get("group_by_day", item.get("date", "")),
            "spend": float(item.get("total_cost", 0) or 0),
            "tokens": int(item.get("total_tokens", 0) or 0),
        })
    return rows


def report_global(start_date, end_date):
    """Gesamtreport nach Datum"""
    data = fetch_daily(start_date, end_date)
    if not data:
        print("\n⚠️  Keine Daten für den Zeitraum gefunden.")
        return

    rows = [[r["day"], f"${r['spend']:.4f}", r["tokens"] or "—"] for r in data]
    total = sum(r["spend"] for r in data)

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


def fetch_teams():
    """Holt Team-Daten und gibt normalisierte Dicts zurück."""
    data = get("/global/spend/teams")
    if not data:
        return []
    team_list = data.get("total_spend_per_team", []) if isinstance(data, dict) else data
    if not team_list:
        return []
    rows = []
    for item in team_list:
        rows.append({
            "team_alias": item.get("team_alias") or "",
            "team_id": item.get("team_id", ""),
            "spend": float(item.get("total_spend", item.get("spend", 0)) or 0),
            "max_budget": float(item.get("max_budget", 0) or 0),
        })
    return rows


def store_data(start_date, end_date):
    """Holt alle Report-Daten und speichert sie als Parquet."""
    fetch_date = datetime.now().strftime("%Y-%m-%d")
    total_rows = 0

    # Keys
    print("   Lade Keys...", end="", flush=True)
    keys = fetch_keys()
    if keys:
        _write_parquet("keys", fetch_date, keys, {
            "fetch_date": pa.string(),
            "key_alias": pa.string(),
            "team_id": pa.string(),
            "user_id": pa.string(),
            "spend": pa.float64(),
            "models": pa.string(),
        })
        total_rows += len(keys)
        print(f" {len(keys)} Einträge")
    else:
        print(" keine Daten")

    # Teams
    print("   Lade Teams...", end="", flush=True)
    teams = fetch_teams()
    if teams:
        _write_parquet("teams", fetch_date, teams, {
            "fetch_date": pa.string(),
            "team_alias": pa.string(),
            "team_id": pa.string(),
            "spend": pa.float64(),
            "max_budget": pa.float64(),
        })
        total_rows += len(teams)
        print(f" {len(teams)} Einträge")
    else:
        print(" keine Daten")

    # Tags
    print("   Lade Tags...", end="", flush=True)
    tags = fetch_tags(start_date, end_date)
    if tags:
        _write_parquet("tags", fetch_date, tags, {
            "fetch_date": pa.string(),
            "tag_name": pa.string(),
            "spend": pa.float64(),
            "request_count": pa.int64(),
        })
        total_rows += len(tags)
        print(f" {len(tags)} Einträge")
    else:
        print(" keine Daten")

    # Daily
    print("   Lade Daily...", end="", flush=True)
    daily = fetch_daily(start_date, end_date)
    if daily:
        _write_parquet("daily", fetch_date, daily, {
            "fetch_date": pa.string(),
            "day": pa.string(),
            "spend": pa.float64(),
            "tokens": pa.int64(),
        })
        total_rows += len(daily)
        print(f" {len(daily)} Einträge")
    else:
        print(" keine Daten")

    print(f"\n✅ Gespeichert: {total_rows} Zeilen → {DATA_DIR}/")


def _write_parquet(report_type, fetch_date, rows, schema_fields):
    """Schreibt eine Liste von Dicts als Parquet-Datei."""
    out_dir = DATA_DIR / report_type
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{fetch_date}.parquet"

    for row in rows:
        row["fetch_date"] = fetch_date

    schema = pa.schema([(k, v) for k, v in schema_fields.items()])
    arrays = {col: pa.array([r.get(col) for r in rows], type=typ) for col, typ in schema_fields.items()}
    table = pa.table(arrays, schema=schema)
    pq.write_table(table, out_file)


QUERIES = {
    "trends": "Kosten pro Monat",
    "top-projects": "Top 10 Projekte nach Spend",
    "compare": "Monatsvergleich (benötigt 2 Monate: --query compare 2026-03 2026-02)",
    "users": "Spend pro User",
    "models": "Spend pro Credential/Modell",
}


def query_data(query_name, query_args):
    """Führt eine vordefinierte Abfrage auf den Parquet-Daten aus."""
    if not DATA_DIR.exists():
        print("❌ Keine gespeicherten Daten gefunden. Zuerst --store ausführen.")
        sys.exit(1)

    db = duckdb.connect()

    if query_name == "trends":
        _query_trends(db)
    elif query_name == "top-projects":
        _query_top_projects(db)
    elif query_name == "compare":
        if len(query_args) < 2:
            print("❌ compare benötigt 2 Monate: --query compare 2026-03 2026-02")
            sys.exit(1)
        _query_compare(db, query_args[0], query_args[1])
    elif query_name == "users":
        _query_users(db)
    elif query_name == "models":
        _query_models(db)
    else:
        print(f"❌ Unbekannte Abfrage: {query_name}")
        print("\nVerfügbare Abfragen:")
        for name, desc in QUERIES.items():
            print(f"  {name:15s} {desc}")
        sys.exit(1)

    db.close()


def _query_trends(db):
    """Kosten pro Monat aus den Daily-Daten."""
    daily_dir = DATA_DIR / "daily"
    if not daily_dir.exists() or not list(daily_dir.glob("*.parquet")):
        print("\n⚠️  Keine Daily-Daten gefunden.")
        return
    parquet_path = str(daily_dir / "*.parquet")
    result = db.execute(f"""
        SELECT
            strftime(day::DATE, '%Y-%m') AS monat,
            SUM(spend) AS kosten,
            SUM(tokens) AS tokens
        FROM read_parquet('{parquet_path}')
        GROUP BY monat
        ORDER BY monat
    """).fetchall()

    if not result:
        print("\n⚠️  Keine Daily-Daten gefunden.")
        return

    rows = [[r[0], f"${r[1]:.4f}", f"{r[2]:,}"] for r in result]
    print("\n📈 Kosten-Trend pro Monat")
    print(tabulate(rows, headers=["Monat", "Kosten (USD)", "Tokens"], tablefmt=TABLE_FMT))


def _query_top_projects(db):
    """Top 10 Projekte nach Spend (letzter Snapshot)."""
    tags_dir = DATA_DIR / "tags"
    if not tags_dir.exists() or not list(tags_dir.glob("*.parquet")):
        print("\n⚠️  Keine Projekt-Tags gefunden.")
        return
    parquet_path = str(tags_dir / "*.parquet")
    result = db.execute(f"""
        WITH latest AS (
            SELECT MAX(fetch_date) AS fd FROM read_parquet('{parquet_path}')
        )
        SELECT tag_name, spend, request_count
        FROM read_parquet('{parquet_path}'), latest
        WHERE fetch_date = latest.fd
          AND tag_name LIKE 'project:%'
        ORDER BY spend DESC
        LIMIT 10
    """).fetchall()

    if not result:
        print("\n⚠️  Keine Projekt-Tags gefunden.")
        return

    rows = [[r[0], f"${r[1]:.4f}", r[2]] for r in result]
    print("\n🏆 Top 10 Projekte")
    print(tabulate(rows, headers=["Projekt", "Kosten (USD)", "Requests"], tablefmt=TABLE_FMT))


def _query_compare(db, month_a, month_b):
    """Vergleich zweier Monate bei Tags."""
    tags_dir = DATA_DIR / "tags"
    if not tags_dir.exists() or not list(tags_dir.glob("*.parquet")):
        print(f"\n⚠️  Keine Daten für {month_a} und/oder {month_b} gefunden.")
        return
    parquet_path = str(tags_dir / "*.parquet")
    result = db.execute(f"""
        WITH a AS (
            SELECT tag_name, spend
            FROM read_parquet('{parquet_path}')
            WHERE fetch_date LIKE '{month_a}%'
            AND tag_name LIKE 'project:%'
        ),
        b AS (
            SELECT tag_name, spend
            FROM read_parquet('{parquet_path}')
            WHERE fetch_date LIKE '{month_b}%'
            AND tag_name LIKE 'project:%'
        )
        SELECT
            COALESCE(a.tag_name, b.tag_name) AS projekt,
            COALESCE(a.spend, 0) AS kosten_a,
            COALESCE(b.spend, 0) AS kosten_b,
            COALESCE(a.spend, 0) - COALESCE(b.spend, 0) AS differenz
        FROM a FULL OUTER JOIN b ON a.tag_name = b.tag_name
        ORDER BY COALESCE(a.spend, 0) DESC
    """).fetchall()

    if not result:
        print(f"\n⚠️  Keine Daten für {month_a} und/oder {month_b} gefunden.")
        return

    rows = []
    for r in result:
        pct = (r[3] / r[2] * 100) if r[2] != 0 else 0
        rows.append([r[0], f"${r[1]:.4f}", f"${r[2]:.4f}", f"${r[3]:+.4f}", f"{pct:+.1f}%"])

    print(f"\n🔄 Vergleich {month_a} vs {month_b}")
    print(tabulate(rows, headers=["Projekt", month_a, month_b, "Differenz", "%"], tablefmt=TABLE_FMT))


def _query_users(db):
    """Spend pro User über alle Snapshots."""
    keys_dir = DATA_DIR / "keys"
    if not keys_dir.exists() or not list(keys_dir.glob("*.parquet")):
        print("\n⚠️  Keine User-Daten gefunden.")
        return
    parquet_path = str(keys_dir / "*.parquet")
    result = db.execute(f"""
        WITH latest AS (
            SELECT MAX(fetch_date) AS fd FROM read_parquet('{parquet_path}')
        )
        SELECT
            user_id,
            SUM(spend) AS kosten,
            COUNT(*) AS keys
        FROM read_parquet('{parquet_path}'), latest
        WHERE fetch_date = latest.fd
          AND user_id != ''
        GROUP BY user_id
        ORDER BY kosten DESC
    """).fetchall()

    if not result:
        print("\n⚠️  Keine User-Daten gefunden.")
        return

    rows = [[r[0] or "—", f"${r[1]:.4f}", r[2]] for r in result]
    print("\n👤 Spend pro User")
    print(tabulate(rows, headers=["User", "Kosten (USD)", "Keys"], tablefmt=TABLE_FMT))


def _query_models(db):
    """Spend pro Credential/Modell."""
    tags_dir = DATA_DIR / "tags"
    if not tags_dir.exists() or not list(tags_dir.glob("*.parquet")):
        print("\n⚠️  Keine Credential-Tags gefunden.")
        return
    parquet_path = str(tags_dir / "*.parquet")
    result = db.execute(f"""
        WITH latest AS (
            SELECT MAX(fetch_date) AS fd FROM read_parquet('{parquet_path}')
        )
        SELECT tag_name, spend, request_count
        FROM read_parquet('{parquet_path}'), latest
        WHERE fetch_date = latest.fd
          AND tag_name LIKE 'Credential:%'
        ORDER BY spend DESC
    """).fetchall()

    if not result:
        print("\n⚠️  Keine Credential-Tags gefunden.")
        return

    rows = [[r[0], f"${r[1]:.4f}", r[2]] for r in result]
    print("\n🤖 Spend pro Modell/Credential")
    print(tabulate(rows, headers=["Credential", "Kosten (USD)", "Requests"], tablefmt=TABLE_FMT))


def report_teams():
    """Spend pro Team"""
    data = fetch_teams()
    if not data:
        print("\n⚠️  Keine Team-Daten gefunden. Teams noch nicht angelegt?")
        return

    rows = []
    for r in data:
        rows.append([
            r["team_alias"] or r["team_id"] or "—",
            f"${r['spend']:.4f}",
            f"${r['max_budget']:.2f}" if r["max_budget"] else "—",
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

Speichern & Abfragen:
  python litellm_report.py --store
  python litellm_report.py --query trends
  python litellm_report.py --query top-projects
  python litellm_report.py --query compare 2026-03 2026-02
  python litellm_report.py --query users
  python litellm_report.py --query models
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
    parser.add_argument("--store", action="store_true", help="Daten als Parquet speichern")
    parser.add_argument("--query", nargs="+", metavar="ABFRAGE",
                        help="Gespeicherte Daten abfragen (trends|top-projects|compare|users|models)")
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

    if args.query:
        query_data(args.query[0], args.query[1:])
        if args.output:
            sys.stdout.close()
        return

    if args.store:
        store_data(args.start, args.end)
        if args.output:
            sys.stdout.close()
        return

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
