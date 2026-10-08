"""Column-name normalization shared by every loader (DuckDB preview, BigQuery, Postgres).

Raw tables keep every field a vendor sends, but names are normalized to
snake_case so the same SQL runs unchanged on DuckDB, BigQuery and Postgres
(spaces and "#" would otherwise force quoting).
  "ClinicNum" -> clinic_num     "Date of Service" -> date_of_service
  "Patient #" -> patient_no     "RECORDNO" -> recordno     "OrgLevel1" -> org_level1
"""
import re


def snake(name: str) -> str:
    s = name.strip().replace("#", " no")
    s = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", s)          # camelCase boundary
    s = re.sub(r"[^0-9A-Za-z]+", "_", s).strip("_").lower()
    s = re.sub(r"_+", "_", s)
    # words that are SQL types/keywords in some dialects get a suffix
    return f"{s}_col" if s in {"date", "time", "timestamp", "order", "group", "select", "table"} else s


def raw_table(system_folder: str, file_stem: str) -> str:
    """sample_data/exports/pms_open_dental/procedures.csv -> pms_open_dental__procedures"""
    return f"{snake(system_folder)}__{snake(file_stem)}"
