#!/usr/bin/env python3
"""
LiteLLM Budget-Konfiguration
Setzt ein Gesamtbudget und modellspezifische Limits über die LiteLLM Proxy API.
"""

import os
import sys

try:
    import requests
    from dotenv import load_dotenv
except ImportError:
    print("Bitte installieren: uv pip install requests python-dotenv")
    sys.exit(1)

load_dotenv()

PROXY_URL = os.environ.get("LITELLM_PROXY_URL", "http://localhost:4000")
MASTER_KEY = os.environ.get("LITELLM_MASTER_KEY", "")

# ── Budget-Einstellungen ─────────────────────────────────────────────────────
GESAMT_BUDGET = 5000.0          # USD
BUDGET_DAUER = "30d"            # Reset-Intervall
MODELL_BUDGETS = {
    "claude-opus-4-6": GESAMT_BUDGET * 0.50,   # 2500 USD (50%)
}


def headers():
    return {"Authorization": f"Bearer {MASTER_KEY}", "Content-Type": "application/json"}


def budget_info_anzeigen():
    """Zeigt die aktuelle Budget-Konfiguration an."""
    print("=" * 60)
    print("LiteLLM Budget-Konfiguration")
    print("=" * 60)
    print(f"  Proxy:           {PROXY_URL}")
    print(f"  Gesamtbudget:    ${GESAMT_BUDGET:,.2f}")
    print(f"  Budget-Dauer:    {BUDGET_DAUER}")
    print(f"  Modell-Limits:")
    for modell, limit in MODELL_BUDGETS.items():
        anteil = limit / GESAMT_BUDGET * 100
        print(f"    {modell}: ${limit:,.2f} ({anteil:.0f}%)")
    print("=" * 60)


def key_erstellen():
    """Erstellt einen neuen API-Key mit Budget-Limits."""
    payload = {
        "max_budget": GESAMT_BUDGET,
        "budget_duration": BUDGET_DAUER,
        "model_max_budget": MODELL_BUDGETS,
    }

    resp = requests.post(f"{PROXY_URL}/key/generate", headers=headers(), json=payload)
    resp.raise_for_status()
    data = resp.json()

    print("\nNeuer Key erstellt:")
    print(f"  Key:        {data.get('key', 'n/a')}")
    print(f"  Budget:     ${GESAMT_BUDGET:,.2f}")
    print(f"  Dauer:      {BUDGET_DAUER}")
    print(f"  Modell-Limits: {MODELL_BUDGETS}")
    return data


def key_aktualisieren(key_id: str):
    """Aktualisiert einen bestehenden Key mit neuen Budget-Limits."""
    payload = {
        "key": key_id,
        "max_budget": GESAMT_BUDGET,
        "budget_duration": BUDGET_DAUER,
        "model_max_budget": MODELL_BUDGETS,
    }

    resp = requests.post(f"{PROXY_URL}/key/update", headers=headers(), json=payload)
    resp.raise_for_status()
    data = resp.json()

    print(f"\nKey aktualisiert: {key_id}")
    print(f"  Budget:     ${GESAMT_BUDGET:,.2f}")
    print(f"  Dauer:      {BUDGET_DAUER}")
    print(f"  Modell-Limits: {MODELL_BUDGETS}")
    return data


def team_erstellen(team_name: str):
    """Erstellt ein neues Team mit Budget-Limits."""
    payload = {
        "team_alias": team_name,
        "max_budget": GESAMT_BUDGET,
        "budget_duration": BUDGET_DAUER,
        "model_max_budget": MODELL_BUDGETS,
    }

    resp = requests.post(f"{PROXY_URL}/team/new", headers=headers(), json=payload)
    resp.raise_for_status()
    data = resp.json()

    print(f"\nTeam erstellt: {team_name}")
    print(f"  Team-ID:    {data.get('team_id', 'n/a')}")
    print(f"  Budget:     ${GESAMT_BUDGET:,.2f}")
    print(f"  Modell-Limits: {MODELL_BUDGETS}")
    return data


def main():
    import argparse

    parser = argparse.ArgumentParser(description="LiteLLM Budget-Konfiguration")
    sub = parser.add_subparsers(dest="aktion", help="Verfügbare Aktionen")

    sub.add_parser("info", help="Budget-Konfiguration anzeigen")
    sub.add_parser("key-neu", help="Neuen API-Key mit Budget erstellen")

    p_update = sub.add_parser("key-update", help="Bestehenden Key aktualisieren")
    p_update.add_argument("key", help="Der zu aktualisierende Key (sk-...)")

    p_team = sub.add_parser("team-neu", help="Neues Team mit Budget erstellen")
    p_team.add_argument("name", help="Team-Name")

    args = parser.parse_args()

    if not MASTER_KEY:
        print("Fehler: LITELLM_MASTER_KEY nicht gesetzt (.env oder Umgebungsvariable)")
        sys.exit(1)

    if args.aktion == "info" or args.aktion is None:
        budget_info_anzeigen()
    elif args.aktion == "key-neu":
        key_erstellen()
    elif args.aktion == "key-update":
        key_aktualisieren(args.key)
    elif args.aktion == "team-neu":
        team_erstellen(args.name)


if __name__ == "__main__":
    main()
