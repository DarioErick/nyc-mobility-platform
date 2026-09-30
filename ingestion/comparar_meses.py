import os
from pathlib import Path
import urllib.request

import boto3
import pyarrow as pa
import pyarrow.parquet as pq
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
        url = f"https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_{month}.parquet"
        bruto = Path("/tmp") / f"bruto_{month}.parquet"
        chave = f"taxi/month={month}/yellow_tripdata_{month}.parquet"
        print(f"\n== {month} ==")
        urllib.request.urlretrieve(url, bruto)
        s3.upload_file(str(bruto), "landing", chave)

        tabela = pq.read_table(bruto)
        antes = [n for n in tabela.column_names if "fee" in n.lower()]
        print("landing:", antes)

        tabela = tabela.rename_columns([n.lower() for n in tabela.column_names])
        for coluna in ("passenger_count", "airport_fee"):
            indice = tabela.schema.get_field_index(coluna)
            tabela = tabela.set_column(indice, coluna, tabela.column(coluna).cast(pa.float64()))

        saida = Path("/tmp") / f"norm_{month}.parquet"
        pq.write_table(tabela, saida)
        s3.upload_file(str(saida), "lake", chave)
        print("lake:", [n for n in tabela.column_names if "fee" in n.lower()])
        print("linhas:", tabela.num_rows)


if __name__ == "__main__":
    main()
