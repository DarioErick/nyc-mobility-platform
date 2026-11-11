import os

from pyspark.sql import SparkSession
from pyspark.sql import functions as F

MONTH = os.environ.get("MONTH", "2024-01")
ORIGEM = f"s3a://landing/taxi/month={MONTH}/yellow_tripdata_{MONTH}.parquet"
DESTINO = f"s3a://lake/bronze/taxi/month={MONTH}/"

spark = (
    SparkSession.builder.appName("bronze-taxi")
    .master("local[2]")
    .config("spark.driver.memory", "2g")
    .config("spark.hadoop.fs.s3a.endpoint", "http://minio:9000")
    .config("spark.hadoop.fs.s3a.access.key", os.environ["MINIO_ROOT_USER"])
    .config("spark.hadoop.fs.s3a.secret.key", os.environ["MINIO_ROOT_PASSWORD"])
    .config("spark.hadoop.fs.s3a.path.style.access", "true")
    .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
    .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false")
    .getOrCreate()
)

bronze = (
    spark.read.parquet(ORIGEM)
    .withColumn("_arquivo_origem", F.lit(f"yellow_tripdata_{MONTH}.parquet"))
    .withColumn("_carregado_em", F.current_timestamp())
)
bronze.write.mode("overwrite").parquet(DESTINO)
print(f"bronze {MONTH}: {bronze.count()} linhas em {DESTINO}")
spark.stop()
