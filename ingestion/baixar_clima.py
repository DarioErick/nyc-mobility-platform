import os
from pathlib import Path

import boto3
import httpx
from botocore.client import Config
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential_jitter

MESES = ["2023-01", "2024-01"]


def retryable(exc: BaseException) -> bool:
    return isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code in (429, 500, 502, 503)


@retry(
    retry=retry_if_exception(retryable),
    wait=wait_exponential_jitter(initial=1, max=30),
    stop=stop_after_attempt(5),
    reraise=True,
)
def buscar(client: httpx.Client, inicio: str, fim: str) -> dict:
    resposta = client.get(
        "/v1/archive",
        params={
            "latitude": 40.71,
            "longitude": -74.0,
            "start_date": inicio,
            "end_date": fim,
            "hourly": "temperature_2m,precipitation",
            "timezone": "America/New_York",
        },
    )
    resposta.raise_for_status()
    return resposta.json()


def main() -> None:
    s3 = boto3.client(
        "s3",
        endpoint_url="http://minio:9000",
        aws_access_key_id=os.environ["MINIO_ROOT_USER"],
        aws_secret_access_key=os.environ["MINIO_ROOT_PASSWORD"],
        region_name="us-east-1",
        config=Config(signature_version="s3v4"),
    )
    with httpx.Client(base_url="https://archive-api.open-meteo.com", timeout=30) as client:
        for month in MESES:
            inicio = f"{month}-01"
            fim = f"{month}-31"
            dado = buscar(client, inicio, fim)
            horas = len(dado["hourly"]["time"])
            local = Path("/tmp") / f"clima_{month}.json"
            local.write_text(__import__("json").dumps(dado), encoding="utf-8")
            chave = f"clima/month={month}/open_meteo.json"
            s3.upload_file(str(local), "landing", chave)
            print(f"{month}: {horas} horas gravadas em s3://landing/{chave}")


if __name__ == "__main__":
    main()
