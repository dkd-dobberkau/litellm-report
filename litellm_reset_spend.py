#!/usr/bin/env python3
"""
LiteLLM Spend-Reset
Setzt den Spend aller Keys mit Budget am Monatsersten auf $0 zurück.

Cronjob (1. jeden Monats, 00:05 Uhr):
  5 0 1 * * cd /path/to/litellm-report && python litellm_reset_spend.py
"""

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


def headers():
    return {"Authorization": f"Bearer {MASTER_KEY}", "Content-Type": "application/json"}


def main():
    if not MASTER_KEY:
        print("Fehler: LITELLM_MASTER_KEY nicht gesetzt")
        sys.exit(1)

    now = datetime.now()
    print(f"🔄 Spend-Reset am {now.strftime('%d.%m.%Y %H:%M')}\n")

    r = requests.get(f"{PROXY_URL}/global/spend/keys", headers=headers(), timeout=10)
    r.raise_for_status()
    all_keys = r.json()

    erfolge = 0
    for item in all_keys:
        alias = item.get("key_alias") or ""
        api_key = item.get("api_key", "")
        spend = item.get("total_spend", 0) or 0

        # Key-Info für max_budget
        r2 = requests.get(
            f"{PROXY_URL}/key/info",
            headers=headers(),
            params={"key": api_key},
            timeout=10,
        )
        if not r2.ok:
            continue
        info = r2.json().get("info", {})
        max_budget = info.get("max_budget")
        if not max_budget or max_budget <= 0:
            continue

        # Spend zurücksetzen
        r3 = requests.post(
            f"{PROXY_URL}/key/update",
            headers=headers(),
            json={"key": api_key, "spend": 0.0},
            timeout=10,
        )
        if r3.ok:
            print(f"  ✓ {alias or api_key[:12]:35s} ${spend:>10,.2f} → $0.00")
            erfolge += 1
        else:
            print(f"  ✗ {alias or api_key[:12]:35s} Fehler: {r3.status_code}")

    print(f"\n   {erfolge} Keys zurückgesetzt")


if __name__ == "__main__":
    main()
