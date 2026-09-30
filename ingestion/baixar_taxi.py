import os
import urllib.request
from pathlib import Path

import boto3
from botocore.client import Config

MONTH = "2024-01"
URL = f"https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_{MONTH}.parquet"
KEY = f"taxi/month={MONTH}/yellow_tripdata_{MONTH}.parquet"


def main() -> None:
    dest = Path("/tmp") / f"yellow_tripdata_{MONTH}.parquet"
    print(f"baixando {URL}")
    urllib.request.urlretrieve(URL, dest)
    print(f"baixado: {dest.stat().st_size} bytes")

    s3 = boto3.client(
        "s3",
        endpoint_url="http://minio:9000",
        aws_access_key_id=os.environ["MINIO_ROOT_USER"],
        aws_secret_access_key=os.environ["MINIO_ROOT_PASSWORD"],
        region_name="us-east-1",
        config=Config(signature_version="s3v4"),
    )
    s3.upload_file(str(dest), "landing", KEY)
    print(f"gravado em s3://landing/{KEY}")


if __name__ == "__main__":
    main()
