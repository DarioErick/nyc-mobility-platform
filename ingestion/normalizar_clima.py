import json
import os
from pathlib import Path

import boto3
import polars as pl
from botocore.client import Config

MESES = ["2023-01", "2024-01"]


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
        origem = f"clima/month={month}/open_meteo.json"
        local = Path("/tmp") / f"clima_{month}.json"
        s3.download_file("landing", origem, str(local))
        bruto = json.loads(local.read_text(encoding="utf-8"))
        horas = bruto["hourly"]
        df = pl.DataFrame(
            {
                "hora": horas["time"],
                "temperatura_c": horas["temperature_2m"],
                "precipitacao_mm": horas["precipitation"],
            }
        ).with_columns(pl.col("hora").str.to_datetime("%Y-%m-%dT%H:%M"))
        if df.height != 31 * 24:
            raise SystemExit(f"{month}: esperava 744 horas, veio {df.height}")
        if df.null_count().sum_horizontal()[0] != 0:
            raise SystemExit(f"{month}: hora sem medicao")
        saida = Path("/tmp") / f"clima_{month}.parquet"
        df.write_parquet(saida)
        destino = f"clima/month={month}/clima.parquet"
        s3.upload_file(str(saida), "lake", destino)
        print(
            f"{month}: {df.height} horas, "
            f"temperatura {df['temperatura_c'].min()} a {df['temperatura_c'].max()} C, "
            f"s3://lake/{destino}"
        )


if __name__ == "__main__":
    main()
