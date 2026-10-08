"""Shared plumbing for every connector.

A connector pulls records from one system and lands them, untouched, as a
CSV in the landing folder (sample_data/exports/<folder>/<file>.csv by
default, or LANDING_DIR). build.py and load_raw.py (BigQuery) pick
the files up from there; all code translation happens later in staging.

Three connector styles cover Northwind's systems:
  * API connectors       - Open Dental, Sage Intacct, marketing APIs, UKG, Ascend
  * FileDropConnector    - vendor report exports dropped in a folder or SFTP
                           (Sensei, TDO Cloud, inventory, UKG scheduled reports)
  * SqlServerConnector   - read-only queries against an on-prem database
                           (Dolphin Management, TDO on-prem)
Credentials come from environment variables (see .env.example), never code.
"""
from __future__ import annotations

import csv
import datetime as dt
import fnmatch
import io
import os
import pathlib
from abc import ABC, abstractmethod
from typing import Iterable

ROOT = pathlib.Path(__file__).resolve().parents[2]
LANDING = pathlib.Path(os.environ.get("LANDING_DIR", ROOT / "sample_data" / "exports"))


class ConfigError(RuntimeError):
    pass


def env(name: str, default: str | None = None, required: bool = True) -> str:
    val = os.environ.get(name, default)
    if required and not val:
        raise ConfigError(f"Missing environment variable {name} (see .env.example)")
    return val or ""


def env_map(name: str, required: bool = True) -> dict[str, str]:
    """'clearwater:123,brandon:456' -> {'clearwater': '123', 'brandon': '456'}"""
    raw = env(name, required=required)
    return dict(pair.split(":", 1) for pair in raw.split(",") if pair.strip())


class Connector(ABC):
    folder: str = ""          # landing folder, e.g. "ukg"
    file: str = ""            # file name, e.g. "timecards"
    columns: list[str] = []   # vendor field names, in landing order

    @abstractmethod
    def extract(self, since: dt.date) -> Iterable[dict]:
        """Yield records changed on or after `since`, keyed by the names in `columns`."""

    def run(self, since: dt.date) -> int:
        out = LANDING / self.folder / f"{self.file}.csv"
        out.parent.mkdir(parents=True, exist_ok=True)
        tmp = out.with_suffix(".partial")
        n = 0
        with open(tmp, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=self.columns, extrasaction="ignore")
            w.writeheader()
            for rec in self.extract(since):
                w.writerow(rec)
                n += 1
        tmp.replace(out)          # only swap in a complete file
        return n


class FileDropConnector(Connector):
    """Picks up the newest report export matching a pattern from a local
    folder or an SFTP drop, checks its header, and lands it unchanged.

    Env: <PREFIX>_DROP = local folder path or sftp://user@host/path
         <PREFIX>_PATTERN = filename glob (default '*.csv')
         SFTP password or key: <PREFIX>_SFTP_PASSWORD / <PREFIX>_SFTP_KEY
    """
    env_prefix: str = ""

    def _newest(self) -> tuple[str, bytes]:
        drop = env(f"{self.env_prefix}_DROP")
        pattern = env(f"{self.env_prefix}_PATTERN", "*.csv")
        if drop.startswith("sftp://"):
            import paramiko  # pip install paramiko
            rest = drop[len("sftp://"):]
            userhost, _, path = rest.partition("/")
            user, _, host = userhost.rpartition("@")
            t = paramiko.Transport((host, 22))
            key = os.environ.get(f"{self.env_prefix}_SFTP_KEY")
            t.connect(username=user, password=os.environ.get(f"{self.env_prefix}_SFTP_PASSWORD"),
                      pkey=paramiko.RSAKey.from_private_key_file(key) if key else None)
            sftp = paramiko.SFTPClient.from_transport(t)
            files = [a for a in sftp.listdir_attr("/" + path) if fnmatch.fnmatch(a.filename, pattern)]
            if not files:
                raise FileNotFoundError(f"No {pattern} in {drop}")
            newest = max(files, key=lambda a: a.st_mtime)
            with sftp.open(f"/{path}/{newest.filename}") as fh:
                data = fh.read()
            t.close()
            return newest.filename, data
        files = sorted(pathlib.Path(drop).glob(pattern), key=lambda p: p.stat().st_mtime)
        if not files:
            raise FileNotFoundError(f"No {pattern} in {drop}")
        return files[-1].name, files[-1].read_bytes()

    def extract(self, since):
        name, data = self._newest()
        reader = csv.DictReader(io.StringIO(data.decode("utf-8-sig")))
        missing = [c for c in self.columns if c not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"{name}: export is missing columns {missing}. Check the report layout.")
        yield from reader


class SqlServerConnector(Connector):
    """Read-only query against an on-prem SQL Server database through ODBC.
    Use a dedicated read-only login. The query file returns columns named
    exactly as `columns`; it receives one parameter, the `since` date.

    Env: <PREFIX>_ODBC = full ODBC connection string
    """
    env_prefix: str = ""
    query_file: str = ""

    def extract(self, since):
        import pyodbc  # pip install pyodbc (+ Microsoft ODBC Driver 18 for SQL Server)
        sql = (pathlib.Path(__file__).parent / "queries" / self.query_file).read_text()
        with pyodbc.connect(env(f"{self.env_prefix}_ODBC"), readonly=True, timeout=30) as conn:
            cur = conn.cursor()
            cur.execute(sql, since)
            names = [d[0] for d in cur.description]
            for row in cur:
                yield dict(zip(names, row))
