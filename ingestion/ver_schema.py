import os
from pathlib import Path

import boto3
import pyarrow.parquet as pq
from botocore.client import Config

MONTH = "2024-01"
KEY = f"taxi/month={MONTH}/yellow_tripdata_{MONTH}.parquet"
dest = Path("/tmp") / "yellow.parquet"

s3 = boto3.client(
    "s3",
    endpoint_url="http://minio:9000",
    aws_access_key_id=os.environ["MINIO_ROOT_USER"],
    aws_secret_access_key=os.environ["MINIO_ROOT_PASSWORD"],
    region_name="us-east-1",
    config=Config(signature_version="s3v4"),
)
s3.download_file("landing", KEY, str(dest))

arquivo = pq.ParquetFile(dest)
print(f"linhas: {arquivo.metadata.num_rows}")
print("colunas:")
for campo in arquivo.schema_arrow:
    print(f"  {campo.name}: {campo.type}")
