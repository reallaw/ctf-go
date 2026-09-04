# Уязвимый сервис SecureNotes для attack-defense CTF.
FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .

ENV PORT=8000 \
    SECURENOTES_DB=/tmp/securenotes.db
EXPOSE 8000

# gunicorn = штатный запуск (без Flask debug-консоли), но код всё равно уязвим.
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", "app:app"]
