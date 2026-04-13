#!/bin/sh
# Env-Vars für Cron verfügbar machen (Cron hat keine Umgebung)
env | grep -E '^(LITELLM_|AZURE_|MAIL_)' | sed 's/^\(.*\)$/export \1/' > /app/.env.cron

echo "$(date) Budget-Alert Container gestartet"
echo "  Cron: täglich um 08:00 Uhr"
echo "  Proxy: ${LITELLM_PROXY_URL}"
echo "  Mail-From: ${MAIL_FROM}"

# Einmaliger Lauf beim Start
echo "$(date) Initialer Lauf..."
python /app/litellm_budget_alert.py --dry-run

# Cron im Vordergrund starten
echo "$(date) Cron gestartet, warte auf 08:00..."
cron -f
