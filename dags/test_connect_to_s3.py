from datetime import timedelta
from typing import Optional

import logging
import os
from pathlib import Path

import pendulum
import requests
from airflow.sdk import DAG, task, task_group

# Reuse configuration from assignment.py to keep behavior consistent
from assignment import (
    CSV_URL,
    CSV_NAME,
    HTTP_TIMEOUT,
    CHUNK_SIZE,
    TMP_DIR,
    DBT_PROFILES_DIR,
    DBT_PROJECT_DIR,
    _run,
)

try:
    import boto3
    from botocore.exceptions import ClientError
    from botocore.config import Config as BotoConfig
except Exception as e:  # pragma: no cover - surfaced at runtime if missing
    raise RuntimeError(
        "boto3 is required for S3 connectivity. Add it to requirements and rebuild image."
    ) from e


logger = logging.getLogger(__name__)

# ---------------- S3 / MinIO config ----------------
# Defaults align with docker-compose MinIO + warehouse bucket created by mc
S3_ENDPOINT_URL = os.getenv("S3_ENDPOINT_URL", "http://minio:9000")
S3_ACCESS_KEY_ID = os.getenv("S3_ACCESS_KEY_ID", os.getenv("AWS_ACCESS_KEY_ID", "admin"))
S3_SECRET_ACCESS_KEY = os.getenv(
    "S3_SECRET_ACCESS_KEY", os.getenv("AWS_SECRET_ACCESS_KEY", "password")
)
S3_REGION = os.getenv("S3_REGION", os.getenv("AWS_REGION", "us-east-1"))
S3_BUCKET = os.getenv("S3_BUCKET", "warehouse")
S3_RAW_PREFIX = os.getenv("S3_RAW_PREFIX", "raw/")
S3_MARTS_PREFIX = os.getenv("S3_MARTS_PREFIX", "marts/")

# DuckDB path where dbt writes models (from dbt profile)
DUCKDB_PATH = os.getenv("DUCKDB_PATH", "/opt/airflow/dbt/warehouse.duckdb")

# Default marts tables to export; can override via env MARTS_TABLES as CSV
MARTS_TABLES = [
    t.strip() for t in os.getenv(
        "MARTS_TABLES",
        "analytics_analytics.agg_norm_location,analytics_analytics.agg_norm_question",
    ).split(",") if t.strip()
]


def _duckdb_s3_env() -> dict:
    """Environment overrides for DuckDB httpfs S3 to use MinIO with path-style URLs."""
    # Strip scheme for DUCKDB_S3_ENDPOINT if present
    endpoint = S3_ENDPOINT_URL.replace("http://", "").replace("https://", "")
    return {
        # DuckDB-specific envs
        "DUCKDB_S3_ACCESS_KEY_ID": S3_ACCESS_KEY_ID,
        "DUCKDB_S3_SECRET_ACCESS_KEY": S3_SECRET_ACCESS_KEY,
        "DUCKDB_S3_REGION": S3_REGION,
        "DUCKDB_S3_ENDPOINT": endpoint,
        "DUCKDB_S3_USE_SSL": "false" if S3_ENDPOINT_URL.startswith("http://") else "true",
        "DUCKDB_S3_URL_STYLE": os.getenv("S3_ADDRESSING_STYLE", "path"),
        # Also provide standard AWS envs for libraries that may read them
        "AWS_ACCESS_KEY_ID": S3_ACCESS_KEY_ID,
        "AWS_SECRET_ACCESS_KEY": S3_SECRET_ACCESS_KEY,
        "AWS_REGION": S3_REGION,
    }


def _dbt_cmd_local(*subcommand: str, vars_yaml: Optional[str] = None) -> list[str]:
    cmd = [
        "dbt",
        *subcommand,
        "--profiles-dir",
        DBT_PROFILES_DIR,
        "--project-dir",
        DBT_PROJECT_DIR,
    ]
    if vars_yaml:
        cmd.extend(["--vars", vars_yaml])
    return cmd


def _s3_client():
    return boto3.client(
        "s3",
        endpoint_url=S3_ENDPOINT_URL,
        aws_access_key_id=S3_ACCESS_KEY_ID,
        aws_secret_access_key=S3_SECRET_ACCESS_KEY,
        region_name=S3_REGION,
        config=BotoConfig(s3={"addressing_style": os.getenv("S3_ADDRESSING_STYLE", "path")}),
    )


def _ensure_tmp_dir() -> None:
    Path(TMP_DIR).mkdir(parents=True, exist_ok=True)


def _s3_key() -> str:
    prefix = S3_RAW_PREFIX
    if not prefix.endswith("/"):
        prefix += "/"
    return f"{prefix}{CSV_NAME}"


with DAG(
    dag_id="s3_ingest_test",
    start_date=pendulum.datetime(2023, 1, 1, tz="UTC"),
    schedule=None,
    catchup=False,
    tags=["assignment", "s3", "minio"],
    params={
        "csv_url": CSV_URL,
        "force_download": False,
    },
) as dag:

    @task(
        task_id="ingest_file_s3",
        retries=3,
        retry_delay=timedelta(seconds=10),
        execution_timeout=timedelta(minutes=3),
    )
    def ingest_file_s3(force: Optional[bool] = None, csv_url: Optional[str] = None) -> str:
        _ensure_tmp_dir()

        force_flag = bool(force) if force is not None else bool(
            dag.params.get("force_download", False)
        )
        url = csv_url or str(dag.params.get("csv_url") or CSV_URL)

        s3 = _s3_client()
        key = _s3_key()
        s3_uri = f"s3://{S3_BUCKET}/{key}"

        # If exists and not forcing, return existing S3 path
        try:
            if not force_flag:
                s3.head_object(Bucket=S3_BUCKET, Key=key)
                logger.info("[ingest_file_s3] S3 object already exists: %s", s3_uri)
                return s3_uri
        except ClientError as e:
            code = e.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
            if code and int(code) == 404:
                pass  # not found -> proceed to download
            else:
                # Some other error (e.g. auth); surface it
                raise

        tmp_path = Path(TMP_DIR) / (CSV_NAME + ".part")
        headers = {"User-Agent": "apache-airflow/3.1.0"}
        with requests.Session() as session:
            with session.get(url, headers=headers, stream=True, timeout=HTTP_TIMEOUT) as r:
                r.raise_for_status()
                with tmp_path.open("wb") as f:
                    for chunk in r.iter_content(chunk_size=CHUNK_SIZE):
                        if chunk:
                            f.write(chunk)

        size = tmp_path.stat().st_size
        if size == 0:
            tmp_path.unlink(missing_ok=True)
            raise ValueError(f"[ingest_file_s3] downloaded empty file from {url}")

        # Upload to S3 raw zone and cleanup temp
        s3.upload_file(str(tmp_path), S3_BUCKET, key)
        tmp_path.unlink(missing_ok=True)
        logger.info("[ingest_file_s3] uploaded to %s (%d bytes)", s3_uri, size)
        return s3_uri

    @task_group(group_id="transform_dbt", tooltip="ETL subtasks")
    def transform_dbt(file_uri: Optional[str] = None):
        @task(
            task_id="dbt_debug_deps",
            retries=2,
            retry_delay=timedelta(seconds=10),
            execution_timeout=timedelta(minutes=10),
        )
        def dbt_debug_deps():
            env = _duckdb_s3_env()
            _run(["dbt", "--version"], extra_env=env)
            _run(_dbt_cmd_local("debug"), extra_env=env)
            _run(_dbt_cmd_local("deps"), extra_env=env)

        @task(
            task_id="dbt_run_test",
            retries=2,
            retry_delay=timedelta(seconds=10),
            execution_timeout=timedelta(minutes=10),
        )
        def dbt_run_test(csv_uri: Optional[str] = None):
            env = _duckdb_s3_env()
            vars_yaml = f"csv_uri: '{str(csv_uri).replace("'", "''")}'" if csv_uri else None
            _run(_dbt_cmd_local("run", vars_yaml=vars_yaml), extra_env=env)
            _run(_dbt_cmd_local("test", vars_yaml=vars_yaml), extra_env=env)

        @task(
            task_id="dbt_docs_generate",
            retries=2,
            retry_delay=timedelta(seconds=10),
            execution_timeout=timedelta(minutes=10),
        )
        def dbt_docs_generate(csv_uri: Optional[str] = None):
            env = _duckdb_s3_env()
            vars_yaml = f"csv_uri: '{str(csv_uri).replace("'", "''")}'" if csv_uri else None
            _run(_dbt_cmd_local("docs", "generate", vars_yaml=vars_yaml), extra_env=env)

        dbg = dbt_debug_deps()
        run_test = dbt_run_test(csv_uri=file_uri)
        docs = dbt_docs_generate(csv_uri=file_uri)
        dbg >> run_test >> docs

    @task(
        task_id="export_marts_to_s3",
        retries=2,
        retry_delay=timedelta(seconds=10),
        execution_timeout=timedelta(minutes=10),
    )
    def export_marts_to_s3() -> list[str]:
        import duckdb

        Path(TMP_DIR).mkdir(parents=True, exist_ok=True)
        s3 = _s3_client()
        exported = []

        # Ensure prefix ends with '/'
        prefix = S3_MARTS_PREFIX if S3_MARTS_PREFIX.endswith("/") else S3_MARTS_PREFIX + "/"

        con = duckdb.connect(DUCKDB_PATH, read_only=True)
        try:
            # Pick an existing schema as default for two-part identifiers
            schemas = [r[0] for r in con.execute(
                "SELECT schema_name FROM information_schema.schemata"
            ).fetchall()]
            target_schema = "analytics" if "analytics" in schemas else "main"
            con.execute(f"SET schema '{target_schema}'")

            for tbl in MARTS_TABLES:
                local_parquet = Path(TMP_DIR) / f"{tbl}.parquet"
                # Export using DuckDB COPY to Parquet from the selected schema
                con.execute(f"COPY {tbl} TO '{local_parquet}' (FORMAT PARQUET);")

                key = f"{prefix}{tbl}.parquet"
                s3.upload_file(str(local_parquet), S3_BUCKET, key)
                exported.append(f"s3://{S3_BUCKET}/{key}")
                try:
                    local_parquet.unlink(missing_ok=True)
                except Exception:
                    pass
        finally:
            con.close()

        logger.info("[export_marts_to_s3] Exported: %s", exported)
        return exported

    s3_path = ingest_file_s3()
    tg = transform_dbt(file_uri=s3_path)
    done = export_marts_to_s3()
    s3_path >> tg >> done
