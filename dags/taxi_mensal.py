from datetime import datetime

from airflow import DAG
from airflow.operators.bash import BashOperator

with DAG(
    dag_id="taxi_mensal",
    schedule=None,
    start_date=datetime(2024, 1, 1),
    catchup=False,
    default_args={"retries": 1},
    tags=["taxi"],
) as dag:
    BashOperator(
        task_id="pipeline",
        bash_command="python /opt/airflow/ingestion/pipeline_mes.py",
        env={"MONTH": "2024-01"},
        append_env=True,
    )
