import os
from pathlib import Path

import boto3
import polars as pl
from botocore.client import Config

MESES = ["2023-01", "2024-01"]
OBRIGATORIAS = (
    "vendorid",
    "tpep_pickup_datetime",
    "tpep_dropoff_datetime",
    "passenger_count",
    "trip_distance",
    "fare_amount",
    "total_amount",
    "airport_fee",
)


def cliente():
    return boto3.client(
        "s3",
        endpoint_url="http://minio:9000",
        aws_access_key_id=os.environ["MINIO_ROOT_USER"],
        aws_secret_access_key=os.environ["MINIO_ROOT_PASSWORD"],
        region_name="us-east-1",
        config=Config(signature_version="s3v4"),
    )


def main() -> None:
    s3 = cliente()
    for month in MESES:
        chave = f"taxi/month={month}/yellow_tripdata_{month}.parquet"
        local = Path("/tmp") / f"lake_{month}.parquet"
        s3.download_file("lake", chave, str(local))
        df = pl.read_parquet(local)
        faltando = [coluna for coluna in OBRIGATORIAS if coluna not in df.columns]
        if faltando:
            raise SystemExit(f"{month}: contrato quebrado, faltam {faltando}")
        if df.schema["airport_fee"] != pl.Float64 or df.schema["passenger_count"] != pl.Float64:
            raise SystemExit(f"{month}: tipo inesperado em airport_fee ou passenger_count")
        print(f"\n== {month} ==")
        print("contrato: ok")
        print("linhas:", df.height)
        print("distancia negativa:", df.filter(pl.col("trip_distance") < 0).height)
        print("tarifa negativa:", df.filter(pl.col("fare_amount") < 0).height)
        print("passageiros nulos:", df.get_column("passenger_count").null_count())


if __name__ == "__main__":
    main()
