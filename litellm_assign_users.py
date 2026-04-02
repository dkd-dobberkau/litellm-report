#!/usr/bin/env python3
"""
LiteLLM User-Zuordnung
Weist bestehenden Virtual Keys eine user_id zu, basierend auf dem Key-Alias.

Ablauf:
  1. --preview  zeigt die geplante Zuordnung (Default)
  2. --apply    führt die Zuordnung durch
"""

import os
import sys

try:
    import requests
    from dotenv import load_dotenv
    from tabulate import tabulate
except ImportError:
    print("Bitte installieren: uv pip install requests python-dotenv tabulate")
    sys.exit(1)

load_dotenv()

PROXY_URL = os.environ.get("LITELLM_PROXY_URL", "http://localhost:4000")
MASTER_KEY = os.environ.get("LITELLM_MASTER_KEY", "")

# ── Zuordnung: key_alias → user_id ──────────────────────────────────────────
# Persönliche Keys (Muster: dkd{nachname} → nachname@dkd.de)
# Service-Keys bleiben unverändert oder bekommen eine Service-ID.
USER_MAP = {
    # Persönliche Keys
    "dkdrkaehm":            "rafael.kaehm@dkd.de",
    "dkdjammann":           "julian.ammann@dkd.de",
    "dkdndehl":             "nils.dehl@dkd.de",
    "dkdnreuschling":       "nicolai.reuschling@dkd.de",
    "dkdehenrich":          "eike.henrich@dkd.de",
    "dkdakolos":            "andrej.kolos@dkd.de",
    "dkdjheymann":          "johannes.heymann@dkd.de",
    "dkdczabanski":         "chris.zabanski@dkd.de",
    "dkdiprokhorov":        "igor.prokhorov@dkd.de",
    "dkdmlubenka":          "mario.lubenka@dkd.de",
    "dkdtjanke":            "thomas.janke@dkd.de",
    "dkdmfriedrich":        "markus.friedrich@dkd.de",
    "dkdoseiffermann":      "oliver.seiffermann@dkd.de",
    "dkdtwebler":           "timo.webler@dkd.de",
    "dkdahildebrand":       "andrea.hildebrand@dkd.de",
    "dkdgduman":            "goekay.duman@dkd.de",
    "dkdtmichael":          "timo.michael@dkd.de",
    "dkddebert":            "dimitri.ebert@dkd.de",
    "dkdohauser":           "oliver.hauser@dkd.de",
    "dkdltode":             "lars.tode@dkd.de",
    "dkdigolman":           "ivan.golman@dkd.de",
    "dkdkmueller":          "kevin.mueller@dkd.de",
    "dkdfrosnerlehnebach":  "florian.lehnebach@dkd.de",
    "dkdikartolo":          "ivan.kartolo@dkd.de",
    "dkdmgoldbach":         "markus.goldbach@dkd.de",
    "dkdcsahner":           "clemens.sahner@dkd.de",
    # Service-Keys
    "qodo":                          "service:qodo",
    "hosted-solr-node-14":           "service:hosted-solr",
    "Demo Instance User Key":        "service:demo",
    "chat.dkd.de Developer Accounts": "service:chat-dev",
    "chat.dkd.de Management":         "service:chat-mgmt",
}


def headers():
    return {"Authorization": f"Bearer {MASTER_KEY}", "Content-Type": "application/json"}


def keys_laden():
    """Alle Keys vom Proxy laden."""
    r = requests.get(f"{PROXY_URL}/global/spend/keys", headers=headers(), timeout=10)
    r.raise_for_status()
    return r.json()


def preview(keys):
    """Zeigt die geplante Zuordnung ohne Änderungen."""
    rows = []
    zugeordnet = 0
    for item in sorted(keys, key=lambda x: x.get("total_spend", 0) or 0, reverse=True):
        alias = item.get("key_alias") or ""
        spend = item.get("total_spend", 0) or 0
        if spend == 0 and alias not in USER_MAP:
            continue

        aktuell = item.get("user_id") or "—"
        neu = USER_MAP.get(alias, "")
        status = ""
        if neu and aktuell in ("", "—", None):
            status = "→ zuweisen"
            zugeordnet += 1
        elif neu and aktuell == neu:
            status = "bereits gesetzt"
        elif neu and aktuell not in ("", "—", None):
            status = "→ überschreiben"
            zugeordnet += 1
        elif not neu:
            status = "kein Mapping"

        rows.append([
            alias or item.get("api_key", "")[:12] + "...",
            f"${spend:.2f}",
            aktuell,
            neu or "—",
            status,
        ])

    print("\n👤 Geplante User-Zuordnung (Preview)")
    print(tabulate(rows, headers=["Key-Alias", "Spend", "Aktuell", "Neu", "Status"], tablefmt="rounded_outline"))
    print(f"\n   {zugeordnet} Keys werden aktualisiert")
    return zugeordnet


def apply(keys):
    """Führt die Zuordnung durch."""
    erfolge = 0
    fehler = 0

    for item in keys:
        alias = item.get("key_alias") or ""
        token = item.get("api_key", "")
        if alias not in USER_MAP or not token:
            continue

        aktuell = item.get("user_id") or ""
        neu = USER_MAP[alias]
        if aktuell == neu:
            continue

        try:
            r = requests.post(
                f"{PROXY_URL}/key/update",
                headers=headers(),
                json={"key": token, "user_id": neu},
                timeout=10,
            )
            r.raise_for_status()
            print(f"  ✓ {alias:35s} → {neu}")
            erfolge += 1
        except requests.exceptions.HTTPError as e:
            print(f"  ✗ {alias:35s} → Fehler: {e}")
            fehler += 1

    print(f"\n   {erfolge} aktualisiert, {fehler} Fehler")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="LiteLLM User-Zuordnung für Virtual Keys")
    parser.add_argument("--apply", action="store_true", help="Zuordnung durchführen (ohne: nur Preview)")
    args = parser.parse_args()

    if not MASTER_KEY:
        print("Fehler: LITELLM_MASTER_KEY nicht gesetzt (.env oder Umgebungsvariable)")
        sys.exit(1)

    keys = keys_laden()

    if args.apply:
        print("🔧 User-Zuordnung wird durchgeführt...\n")
        apply(keys)
    else:
        preview(keys)
        print("\n   → Mit --apply die Zuordnung durchführen")


if __name__ == "__main__":
    main()
