# NYC Mobility Platform
Local pipeline for New York City taxi trips enriched with hourly weather.
January 2023 and January 2024 land in MinIO and are published in three stages:
- landing: raw taxi Parquet and weather JSON
- lake: one schema (`airport_fee`), hourly weather, and an hourly summary
- `mart.resumo_horario` in Postgres: trips, revenue, and temperature by hour
Airflow runs the January 2024 pipeline from the `taxi_mensal` DAG.
## Run
With Docker Desktop open, from the project folder:
    docker compose up -d
- MinIO: http://127.0.0.1:9001
- Postgres: localhost:5432, database `mobility`, user `mobility`
- Airflow: http://127.0.0.1:8080 (user `admin`, password `admin`)
MinIO and Postgres passwords live in `.env`, which is not committed. The template is `.env.example`.
Scripts are in `ingestion/` and run on the Compose network. The DAG is `dags/taxi_mensal.py`.
