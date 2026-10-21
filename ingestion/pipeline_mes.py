import calendar
import io
import json
import os
from pathlib import Path
import urllib.request

import boto3
import httpx
import polars as pl
import psycopg
from botocore.client import Config
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential_jitter

MONTH = os.environ.get("MONTH", "2024-01")


def s3():
    return boto3.client(
        "s3",
        endpoint_url="http://minio:9000",
        aws_access_key_id=os.environ["MINIO_ROOT_USER"],
        aws_secret_access_key=os.environ["MINIO_ROOT_PASSWORD"],
        region_name="us-east-1",
        config=Config(signature_version="s3v4"),
    )


def periodo():
    ano, mes = map(int, MONTH.split("-"))
    ultimo = calendar.monthrange(ano, mes)[1]
    inicio = f"{MONTH}-01"
    fim_api = f"{MONTH}-{ultimo:02d}"
    fim = f"{ano + 1}-01-01" if mes == 12 else f"{ano}-{mes + 1:02d}-01"
    return inicio, fim_api, fim


def retryable(exc: BaseException) -> bool:
    return isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code in (429, 500, 502, 503)


@retry(
    retry=retry_if_exception(retryable),
    wait=wait_exponential_jitter(initial=1, max=30),
    stop=stop_after_attempt(5),
    reraise=True,
)
def buscar_clima(client: httpx.Client, inicio: str, fim: str) -> dict:
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
    inicio, fim_api, fim = periodo()
    cliente = s3()
    nome = f"yellow_tripdata_{MONTH}.parquet"
    bruto = Path("/tmp") / nome
    print(f"1/6 taxi {MONTH}")
    urllib.request.urlretrieve(
        f"https://d37ci6vzurychx.cloudfront.net/trip-data/{nome}",
        bruto,
    )
    cliente.upload_file(str(bruto), "landing", f"taxi/month={MONTH}/{nome}")

    print("2/6 normaliza taxi")
    taxi = pl.read_parquet(bruto).rename({c: c.lower() for c in pl.read_parquet(bruto).columns})
    taxi = pl.read_parquet(bruto)
    taxi = taxi.rename({c: c.lower() for c in taxi.columns}).with_columns(
        pl.col("passenger_count").cast(pl.Float64),
        pl.col("airport_fee").cast(pl.Float64),
    )
    taxi_out = Path("/tmp") / "taxi_norm.parquet"
    taxi.write_parquet(taxi_out)
    cliente.upload_file(str(taxi_out), "lake", f"taxi/month={MONTH}/{nome}")

    print("3/6 clima")
    with httpx.Client(base_url="https://archive-api.open-meteo.com", timeout=30) as http:
        dado = buscar_clima(http, inicio, fim_api)
    clima_json = Path("/tmp") / "clima.json"
    clima_json.write_text(json.dumps(dado), encoding="utf-8")
    cliente.upload_file(str(clima_json), "landing", f"clima/month={MONTH}/open_meteo.json")

    print("4/6 normaliza clima")
    horas = dado["hourly"]
    clima = pl.DataFrame(
        {
            "hora": horas["time"],
            "temperatura_c": horas["temperature_2m"],
            "precipitacao_mm": horas["precipitation"],
        }
    ).with_columns(pl.col("hora").str.to_datetime("%Y-%m-%dT%H:%M"))
    if clima.height != calendar.monthrange(*map(int, MONTH.split("-")))[1] * 24:
        raise SystemExit(f"clima incompleto: {clima.height}")
    clima_out = Path("/tmp") / "clima.parquet"
    clima.write_parquet(clima_out)
    cliente.upload_file(str(clima_out), "lake", f"clima/month={MONTH}/clima.parquet")

    print("5/6 resumo por hora")
    viagens = taxi.with_columns(
        pl.col("tpep_pickup_datetime").dt.truncate("1h").cast(pl.Datetime("us")).alias("hora")
    )
    clima = clima.with_columns(pl.col("hora").cast(pl.Datetime("us")))
    resumo = (
        viagens.group_by("hora")
        .agg(
            pl.len().alias("corridas"),
            (pl.col("fare_amount") < 0).sum().alias("tarifas_negativas"),
            pl.col("total_amount").filter(pl.col("total_amount") >= 0).sum().alias("receita"),
        )
        .join(clima, on="hora", how="inner")
        .sort("hora")
        .with_columns(
            pl.col("corridas").cast(pl.Int64),
            pl.col("tarifas_negativas").cast(pl.Int64),
            pl.col("receita").round(2),
        )
    )
    resumo_out = Path("/tmp") / "resumo.parquet"
    resumo.write_parquet(resumo_out)
    cliente.upload_file(str(resumo_out), "lake", f"resumo/month={MONTH}/por_hora.parquet")

    print("6/6 postgres")
    url = (
        f"postgresql://{os.environ['PG_USER']}:{os.environ['PG_PASSWORD']}"
        f"@postgres:5432/{os.environ['PG_DB']}"
    )
    buf = io.StringIO()
    resumo.select(
        "hora", "corridas", "tarifas_negativas", "receita", "temperatura_c", "precipitacao_mm"
    ).write_csv(buf, include_header=False)
    buf.seek(0)
    with psycopg.connect(url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM mart.resumo_horario WHERE hora >= %s AND hora < %s",
                (inicio, fim),
            )
            with cur.copy(
                "COPY mart.resumo_horario (hora, corridas, tarifas_negativas, receita, temperatura_c, precipitacao_mm) FROM STDIN WITH (FORMAT CSV)"
            ) as copy:
                copy.write(buf.read())
            cur.execute(
                "SELECT count(*) FROM mart.resumo_horario WHERE hora >= %s AND hora < %s",
                (inicio, fim),
            )
            total = cur.fetchone()[0]
        conn.commit()
    print(f"mes {MONTH}: {resumo.height} horas no lake, {total} linhas no postgres")


if __name__ == "__main__":
    main()
