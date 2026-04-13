FROM python:3.11-slim AS builder
WORKDIR /app
RUN pip install --no-cache-dir --user requests python-dotenv

FROM python:3.11-slim
RUN apt-get update && apt-get install -y cron && rm -rf /var/lib/apt/lists/*
RUN useradd -m -u 1000 appuser
WORKDIR /app

COPY --from=builder /root/.local /root/.local
COPY --from=builder /root/.local /home/appuser/.local
RUN chown -R appuser:appuser /home/appuser/.local
COPY litellm_budget_alert.py .

ENV PATH=/root/.local/bin:/home/appuser/.local/bin:$PATH
ENV PYTHONUNBUFFERED=1

# Cron-Job: täglich um 8:00 Uhr Budget-Alerts prüfen
# Env-Vars werden zur Laufzeit aus /app/.env.cron injiziert
RUN echo '0 8 * * * root . /app/.env.cron && /home/appuser/.local/bin/python /app/litellm_budget_alert.py >> /var/log/budget-alert.log 2>&1' > /etc/cron.d/budget-alert \
    && chmod 0644 /etc/cron.d/budget-alert

COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

CMD ["/app/entrypoint.sh"]
