import io
import os
from pathlib import Path

import boto3
import polars as pl
import psycopg
from botocore.client import Config

MESES = ["2023-01", "2024-01"]


def cliente_s3():
    return boto3.client(
        "s3",
        endpoint_url="http://minio:9000",
        aws_access_key_id=os.environ["MINIO_ROOT_USER"],
        aws_secret_access_key=os.environ["MINIO_ROOT_PASSWORD"],
        region_name="us-east-1",
        config=Config(signature_version="s3v4"),
    )


def main() -> None:
    s3 = cliente_s3()
    url = (
        f"postgresql://{os.environ['PG_USER']}:{os.environ['PG_PASSWORD']}"
        f"@postgres:5432/{os.environ['PG_DB']}"
    )
    with psycopg.connect(url) as conn:
        with conn.cursor() as cur:
            cur.execute("CREATE SCHEMA IF NOT EXISTS mart")
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS mart.resumo_horario (
                    hora timestamp PRIMARY KEY,
                    corridas bigint NOT NULL,
                    tarifas_negativas bigint NOT NULL,
                    receita numeric(14,2) NOT NULL,
                    temperatura_c double precision,
                    precipitacao_mm double precision
                )
                """
            )
            for month in MESES:
                inicio = f"{month}-01"
                ano, mes = map(int, month.split("-"))
                fim = f"{ano + 1}-01-01" if mes == 12 else f"{ano}-{mes + 1:02d}-01"
                local = Path("/tmp") / f"resumo_{month}.parquet"
                s3.download_file("lake", f"resumo/month={month}/por_hora.parquet", str(local))
                df = pl.read_parquet(local).select(
                    "hora",
                    "corridas",
                    "tarifas_negativas",
                    "receita",
                    "temperatura_c",
                    "precipitacao_mm",
                ).with_columns(
                    pl.col("corridas").cast(pl.Int64),
                    pl.col("tarifas_negativas").cast(pl.Int64),
                    pl.col("receita").round(2),
                )
                buf = io.StringIO()
                df.write_csv(buf, include_header=False)
                buf.seek(0)
                cur.execute(
                    "DELETE FROM mart.resumo_horario WHERE hora >= %s AND hora < %s",
                    (inicio, fim),
                )
                with cur.copy(
                    "COPY mart.resumo_horario (hora, corridas, tarifas_negativas, receita, temperatura_c, precipitacao_mm) FROM STDIN WITH (FORMAT CSV)"
                ) as copy:
                    copy.write(buf.read())
                print(f"{month}: {df.height} horas gravadas em mart.resumo_horario")
        conn.commit()


if __name__ == "__main__":
    main()
