"""Land files into the warehouse raw layer, exactly as delivered.

    python load_raw.py                         # BigQuery (default): sample_data/exports -> dataset raw
    python load_raw.py --dir landing/          # whatever the custom PMS connectors dropped
    python load_raw.py --target pg             # Postgres instead (local testing)

Every column is stored as text (BigQuery STRING) with snake_case names, one
table per file: raw.<system>__<file>. dbt does the typing and translation.
In production, Fivetran and the BigQuery Data Transfer Service write Sage
Intacct, UKG and the ad platforms straight into the warehouse; this script
covers the custom PMS connectors' files.

BigQuery: GCP_PROJECT in the environment or .env; sign in once with
  gcloud auth application-default login
Postgres: PG_HOST, PG_USER, PG_PASSWORD, PG_DATABASE, PG_PORT, PG_SSLMODE.
"""
from __future__ import annotations

import csv
import io
import os
import pathlib
import sys

from ingestion.naming import raw_table, snake

ROOT = pathlib.Path(__file__).parent


def load_env():
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"'))


def files_and_columns(src: pathlib.Path):
    for f in sorted(src.glob("*/*.csv")):
        with f.open(newline="", encoding="utf-8-sig") as fh:
            header = next(csv.reader(fh))
        yield f, raw_table(f.parent.name, f.stem), [snake(c) for c in header]


def load_bigquery(src):
    from google.cloud import bigquery
    project = os.environ["GCP_PROJECT"]
    client = bigquery.Client(project=project)
    client.create_dataset(bigquery.Dataset(f"{project}.raw"), exists_ok=True)
    for f, table, cols in files_and_columns(src):
        job = client.load_table_from_file(
            f.open("rb"), f"{project}.raw.{table}",
            job_config=bigquery.LoadJobConfig(
                source_format=bigquery.SourceFormat.CSV, skip_leading_rows=1, allow_quoted_newlines=True,
                schema=[bigquery.SchemaField(c, "STRING") for c in cols],
                write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE))
        job.result()
        print(f"landed raw.{table:40s} {client.get_table(job.destination).num_rows:>9,} rows")


def load_postgres(src):
    import psycopg
    con = psycopg.connect(
        host=os.environ["PG_HOST"], user=os.environ["PG_USER"], password=os.environ.get("PG_PASSWORD", ""),
        dbname=os.environ.get("PG_DATABASE", "practice_pulse"), port=os.environ.get("PG_PORT", "5432"),
        sslmode=os.environ.get("PG_SSLMODE", "require"))
    with con, con.cursor() as cur:
        cur.execute("CREATE SCHEMA IF NOT EXISTS raw")
        for f, table, cols in files_and_columns(src):
            # CASCADE drops dbt's staging views over this table; the next dbt build recreates them
            cur.execute(f'DROP TABLE IF EXISTS raw."{table}" CASCADE')
            cur.execute(f'CREATE TABLE raw."{table}" ({", ".join(f"{c} text" for c in cols)})')
            with f.open(newline="", encoding="utf-8-sig") as fh, \
                    cur.copy(f'COPY raw."{table}" FROM STDIN WITH (FORMAT csv, HEADER true)') as cp:
                while chunk := fh.read(1 << 20):
                    cp.write(chunk)
            cur.execute(f'SELECT count(*) FROM raw."{table}"')
            print(f"landed raw.{table:40s} {cur.fetchone()[0]:>9,} rows")


def main():
    load_env()
    src = pathlib.Path(sys.argv[sys.argv.index("--dir") + 1]) if "--dir" in sys.argv else ROOT / "sample_data" / "exports"
    if not any(src.glob("*/*.csv")):
        sys.exit(f"no CSV files under {src}")
    target = sys.argv[sys.argv.index("--target") + 1] if "--target" in sys.argv else "bigquery"
    (load_postgres if target == "pg" else load_bigquery)(src)


if __name__ == "__main__":
    main()
