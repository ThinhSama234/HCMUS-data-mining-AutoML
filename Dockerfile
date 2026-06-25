# Console image — Streamlit + the storage layer (Postgres/MinIO drivers).
FROM python:3.11-slim
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY analysis/ ./analysis/
COPY storage/ ./storage/
COPY console/ ./console/
COPY results/ ./results/

EXPOSE 8501
# `migrate` (schema + ingest) is run as a one-off: docker-compose run --rm console python -m storage.migrate
CMD ["streamlit", "run", "console/app.py", "--server.address=0.0.0.0", "--server.port=8501"]
