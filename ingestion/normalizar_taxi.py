import os
from pathlib import Path

import boto3
import pyarrow as pa
import pyarrow.parquet as pq
from botocore.client import Config

MONTH = "2024-01"
ORIGEM = f"taxi/month={MONTH}/yellow_tripdata_{MONTH}.parquet"
DESTINO = ORIGEM

s3 = boto3.client(
    "s3",
    endpoint_url="http://minio:9000",
    aws_access_key_id=os.environ["MINIO_ROOT_USER"],
    aws_secret_access_key=os.environ["MINIO_ROOT_PASSWORD"],
    region_name="us-east-1",
    config=Config(signature_version="s3v4"),
)
local = Path("/tmp") / "yellow.parquet"
s3.download_file("landing", ORIGEM, str(local))

tabela = pq.read_table(local)
print("antes:", [nome for nome in tabela.column_names if "fee" in nome.lower()])

tabela = tabela.rename_columns([nome.lower() for nome in tabela.column_names])
for coluna in ("passenger_count", "airport_fee"):
    indice = tabela.schema.get_field_index(coluna)
    tabela = tabela.set_column(indice, coluna, tabela.column(coluna).cast(pa.float64()))

saida = Path("/tmp") / "yellow_normalizado.parquet"
pq.write_table(tabela, saida)
s3.upload_file(str(saida), "lake", DESTINO)
print("depois:", [nome for nome in tabela.column_names if "fee" in nome.lower()])
print(f"gravado em s3://lake/{DESTINO}")
