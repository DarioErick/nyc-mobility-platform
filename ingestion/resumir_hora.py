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
        taxi_local = Path("/tmp") / f"taxi_{month}.parquet"
        clima_local = Path("/tmp") / f"clima_{month}.parquet"
        s3.download_file("lake", f"taxi/month={month}/yellow_tripdata_{month}.parquet", str(taxi_local))
        s3.download_file("lake", f"clima/month={month}/clima.parquet", str(clima_local))

        viagens = pl.read_parquet(taxi_local).with_columns(
            pl.col("tpep_pickup_datetime").dt.truncate("1h").cast(pl.Datetime("us")).alias("hora")
        )
        clima = pl.read_parquet(clima_local).with_columns(pl.col("hora").cast(pl.Datetime("us")))
        com_clima = viagens.join(clima.select("hora"), on="hora", how="left")
        casadas = com_clima.filter(pl.col("hora").is_in(clima["hora"])).height

        resumo = (
            viagens.group_by("hora")
            .agg(
                pl.len().alias("corridas"),
                (pl.col("fare_amount") < 0).sum().alias("tarifas_negativas"),
                pl.col("total_amount").filter(pl.col("total_amount") >= 0).sum().alias("receita"),
            )
            .join(clima, on="hora", how="inner")
            .sort("hora")
        )
        saida = Path("/tmp") / f"resumo_{month}.parquet"
        resumo.write_parquet(saida)
        destino = f"resumo/month={month}/por_hora.parquet"
        s3.upload_file(str(saida), "lake", destino)
        print(
            f"{month}: corridas {viagens.height}, com clima {casadas}, "
            f"horas no resumo {resumo.height}, receita {round(resumo['receita'].sum(), 2)}, "
            f"s3://lake/{destino}"
        )


if __name__ == "__main__":
    main()
