from __future__ import annotations

import logging
import os
import subprocess
from datetime import timedelta
from pathlib import Path
from typing import Optional
import json

import pendulum
import requests
from airflow.sdk import DAG, task, task_group  # Airflow 3 public API
# from airflow.exceptions import AirflowSkipException
# from airflow.providers.standard.operators.bash import BashOperator
# from airflow.providers.standard.operators.empty import EmptyOperator


# ---------------- Local (เฉพาะ temp) ----------------
AIRFLOW_DATA_DIR = os.getenv("AIRFLOW_DATA_DIR", "/opt/airflow/data")
TMP_DIR = Path(os.getenv("TMP_DIR", f"{AIRFLOW_DATA_DIR}/tmp"))
RAW_DIR = Path(os.getenv("RAW_DIR", f"{AIRFLOW_DATA_DIR}/raw"))
CSV_NAME = os.getenv("CSV_NAME", "cdc_data.csv")
CSV_URL = os.getenv(
    "CSV_URL", "https://data.cdc.gov/api/views/hksd-2xuw/rows.csv?accessType=DOWNLOAD")

# ---------------- dbt config ----------------
DBT_PROFILES_DIR = os.getenv("DBT_PROFILES_DIR", "/opt/airflow/dbt/profiles")
DBT_PROJECT_DIR = os.getenv("DBT_PROJECT_DIR", "/opt/airflow/dbt")
DBT_DOCS_PORT = os.getenv("DBT_DOCS_PORT", "8082")

# ---------------- HTTP config ----------------
HTTP_TIMEOUT_CONNECT = int(os.getenv("HTTP_TIMEOUT_CONNECT", "5"))
HTTP_TIMEOUT_READ = int(os.getenv("HTTP_TIMEOUT_READ", "30"))
HTTP_TIMEOUT = (HTTP_TIMEOUT_CONNECT, HTTP_TIMEOUT_READ)
CHUNK_SIZE = int(os.getenv("HTTP_CHUNK_SIZE", str(1 << 14)))  # 16KB

logger = logging.getLogger(__name__)


def _run(cmd: list[str], extra_env: Optional[dict] = None, cwd: Optional[str] = None) -> None:
    """Run a shell command; always log stdout/stderr; raise on non-zero."""
    env = {**os.environ}
    if extra_env:
        env.update(extra_env)
    if cwd is None:
        cwd = DBT_PROJECT_DIR

    logger.info("[cmd] %s", " ".join(cmd))
    p = subprocess.run(
        cmd,
        cwd=cwd,
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )
    if p.stdout:
        logger.info("--- STDOUT ---\n%s", p.stdout)
    if p.returncode != 0:
        if p.stderr:
            logger.error("--- STDERR ---\n%s", p.stderr)
        raise subprocess.CalledProcessError(
            p.returncode, cmd, p.stdout, p.stderr)


def _dbt_cmd(*subcommand: str, vars_yaml: Optional[str] = None) -> list[str]:
    """Build a dbt CLI command that shares the standard project/profile flags."""
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


def _dbt_vars(csv_uri: Optional[str]) -> Optional[str]:
    """Return the YAML payload for dbt ``--vars`` when a CSV path is provided."""
    if not csv_uri:
        return None
    safe = csv_uri.replace("'", "''")  # YAML single quotes; escape internal ones
    return f"csv_uri: '{safe}'"


def _run_dbt(*subcommand: str, csv_uri: Optional[str] = None) -> None:
    """Execute a dbt CLI command with optional ``csv_uri`` propagated via ``--vars``."""
    _run(_dbt_cmd(*subcommand, vars_yaml=_dbt_vars(csv_uri)))


def _ensure_dirs() -> None:
    """Ensure temporary and raw directories exist."""
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)


# ===== DAG =====
with DAG(
    dag_id="dbt_duckdb_test",
    start_date=pendulum.datetime(2023, 1, 1, tz="UTC"),
    schedule=None,
    catchup=False,
    tags=["assignment"],
    params={
        "csv_url": CSV_URL,
        "force_download": False,
    },
) as dag:

    @task(task_id="ingest_file",
          retries=3,
          retry_delay=timedelta(seconds=10),
          execution_timeout=timedelta(minutes=3)
          )
    def ingest_file(force: Optional[bool] = None, csv_url: Optional[str] = None) -> str:
        _ensure_dirs()
        force_flag = bool(force) if force is not None else bool(
            dag.params.get("force_download", False))
        url = csv_url or str(dag.params.get("csv_url") or CSV_URL)

        final_path = RAW_DIR / CSV_NAME
        if final_path.exists() and not force_flag:
            logger.info("[ingest_file] file already exists: %s", final_path)
            return str(final_path)  # ✅ no skip, downstream will run

        tmp_path = TMP_DIR / (CSV_NAME + ".part")
        headers = {"User-Agent": "apache-airflow/3.1.0"}
        with requests.Session() as session:
            with session.get(url, headers=headers, stream=True, timeout=HTTP_TIMEOUT) as r:
                r.raise_for_status()
                with tmp_path.open("wb") as f:
                    for chunk in r.iter_content(chunk_size=CHUNK_SIZE):
                        if chunk:
                            f.write(chunk)

        os.replace(tmp_path, final_path)
        size = final_path.stat().st_size
        if size == 0:
            raise ValueError(
                f"[ingest_file] downloaded empty file: {final_path}")
        logger.info(
            "[ingest_file] downloaded and moved to %s (%d bytes)", final_path, size)
        return str(final_path)

    @task_group(group_id="transform_dbt", tooltip="ETL subtasks")
    def transform_dbt(file_uri: Optional[str] = None):
        # === Debug & Deps ===
        @task(task_id="dbt_debug_deps",
              retries=2,
              retry_delay=timedelta(seconds=10),
              execution_timeout=timedelta(minutes=10)
              )
        def dbt_debug_deps():
            # Debug/Deps
            _run(["dbt", "--version"])
            _run(_dbt_cmd("debug"))
            _run(_dbt_cmd("deps"))


        # === Run & Test ===
        @task(task_id="dbt_run_test",
              retries=2,
              retry_delay=timedelta(seconds=10),
              execution_timeout=timedelta(minutes=10))
        def dbt_run_test(csv_uri: Optional[str] = None):
            # dbt run
            _run_dbt("run", csv_uri=csv_uri)

            # dbt test
            _run_dbt("test", csv_uri=csv_uri)
            

        # === Generate Docs ===
        @task(task_id="dbt_docs_generate",
              retries=2,
              retry_delay=timedelta(seconds=10),
              execution_timeout=timedelta(minutes=10))
        def dbt_docs_generate(csv_uri: Optional[str] = None):
            _run_dbt("docs", "generate", csv_uri=csv_uri)

        # flow control
        dbg = dbt_debug_deps()
        run_test = dbt_run_test(csv_uri=file_uri)
        docs = dbt_docs_generate(csv_uri=file_uri)
        dbg >> run_test >> docs

    # === DAG flow ===
    path_file = ingest_file()
    tg = transform_dbt(file_uri=path_file)   # ✅ pass XComArg into group param
    # # explicit dependency (optional but clear)
    path_file >> tg
