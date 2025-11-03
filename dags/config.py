import os
from dataclasses import dataclass
from pathlib import Path
from typing import Tuple


@dataclass(frozen=True)
class Settings:
    # Local data dirs
    airflow_data_dir: str = os.getenv("AIRFLOW_DATA_DIR", "/opt/airflow/data")
    tmp_dir: Path = Path(os.getenv("TMP_DIR", f"{os.getenv('AIRFLOW_DATA_DIR', '/opt/airflow/data')}/tmp"))
    raw_dir: Path = Path(os.getenv("RAW_DIR", f"{os.getenv('AIRFLOW_DATA_DIR', '/opt/airflow/data')}/raw"))

    # CSV ingest
    csv_name: str = os.getenv("CSV_NAME", "cdc_data.csv")
    csv_url: str = os.getenv(
        "CSV_URL",
        "https://data.cdc.gov/api/views/hksd-2xuw/rows.csv?accessType=DOWNLOAD",
    )

    # dbt settings
    dbt_profiles_dir: str = os.getenv("DBT_PROFILES_DIR", "/opt/airflow/dbt/profiles")
    dbt_project_dir: str = os.getenv("DBT_PROJECT_DIR", "/opt/airflow/dbt")
    dbt_docs_port: str = os.getenv("DBT_DOCS_PORT", "8082")

    # HTTP download settings
    http_timeout_connect: int = int(os.getenv("HTTP_TIMEOUT_CONNECT", "5"))
    http_timeout_read: int = int(os.getenv("HTTP_TIMEOUT_READ", "30"))
    http_chunk_size: int = int(os.getenv("HTTP_CHUNK_SIZE", str(1 << 14)))  # 16KB

    @property
    def http_timeout(self) -> Tuple[int, int]:
        return (self.http_timeout_connect, self.http_timeout_read)


settings = Settings()

