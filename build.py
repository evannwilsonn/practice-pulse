"""Run the whole platform end to end on placeholder data.

    python build.py            # regenerate placeholder exports, then build
    python build.py --no-gen   # build from whatever files are in sample_data/exports

1. creates the warehouse (warehouse/practice_pulse.duckdb)
2. loads mapping tables from seeds/ into ref.*
3. lands every export file into raw.<system>__<file>, exactly as delivered
   (in production the connectors drop real files / API pulls here instead)
4. builds staging views (code translation) and mart tables
5. exports marts to dashboard/data.json and bakes dashboard/index.html
"""
from __future__ import annotations

import json
import pathlib
import sys

import duckdb

from ingestion.naming import raw_table, snake

ROOT = pathlib.Path(__file__).parent
DB = ROOT / "warehouse" / "practice_pulse.duckdb"
EXPORTS = ROOT / "sample_data" / "exports"
SEEDS = ROOT / "seeds"

SEED_TYPES = {
    "dim_location": {"location_key": "INTEGER", "open_date": "DATE", "operatories": "INTEGER"},
    "cdt_procedure_map": {"is_new_patient_code": "BOOLEAN", "typical_fee": "DOUBLE"},
    "location_crosswalk": {"source_location": "VARCHAR", "location_key": "INTEGER"},
    "gl_account_map": {"account_no": "VARCHAR", "is_opex": "BOOLEAN"},
}


def main():
    if "--no-gen" not in sys.argv:
        from sample_data.generate import main as generate
        generate()

    DB.unlink(missing_ok=True)
    con = duckdb.connect(str(DB))
    con.execute((ROOT / "warehouse" / "schema.sql").read_text())

    for f in sorted(SEEDS.glob("*.csv")):
        types = SEED_TYPES.get(f.stem, {})
        opt = f", types={types!r}" if types else ""
        con.execute(f"CREATE TABLE ref.{f.stem} AS SELECT * FROM read_csv('{f}', header=true{opt})")
    print(f"loaded {len(list(SEEDS.glob('*.csv')))} mapping tables into ref.*")

    for f in sorted(EXPORTS.glob("*/*.csv")):
        table = f"raw.{raw_table(f.parent.name, f.stem)}"
        cols = con.execute(f"DESCRIBE SELECT * FROM read_csv('{f}', header=true, all_varchar=true)").fetchall()
        select = ", ".join(f'"{c[0]}" AS {snake(c[0])}' for c in cols)
        con.execute(f"CREATE TABLE {table} AS SELECT {select} FROM read_csv('{f}', header=true, all_varchar=true)")
        n = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"landed {table:40s} {n:>9,} rows")

    con.execute((ROOT / "models" / "staging" / "stg_models.sql").read_text())
    con.execute((ROOT / "models" / "marts" / "mart_models.sql").read_text())

    dq = con.execute("SELECT kind, value, row_count FROM staging.dq_unmapped").fetchall()
    print("unmapped codes:", dq or "none")
    rec = con.execute("""SELECT category, round(SUM(variance) / SUM(ops_amount) * 100, 2)
                         FROM marts.mart_reconciliation GROUP BY 1 ORDER BY 1""").fetchall()
    print("GL vs operational variance %:", rec)

    def rows(sql):
        cur = con.execute(sql)
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]

    data = {
        "locations": rows("SELECT location_key, location_name, region, specialty, pms_system, operatories "
                          "FROM ref.dim_location ORDER BY location_key"),
        "monthly": rows("SELECT * EXCLUDE (location_name, region, specialty, pms_system), "
                        "strftime(month, '%Y-%m') AS month FROM marts.mart_location_monthly "
                        "ORDER BY month, location_key"),
        "channels": rows("SELECT location_key, strftime(month, '%Y-%m') AS month, channel, "
                         "spend, leads, booked FROM marts.mart_marketing_channel_monthly"),
        "mix": rows("SELECT location_key, strftime(month, '%Y-%m') AS month, procedure_category AS cat, "
                    "gross_production AS prod FROM marts.mart_procedure_mix"),
        # compact form: account list once, then [location, month, account index, amount] rows
        "opex_accounts": [list(r) for r in con.execute(
            "SELECT DISTINCT account_no, account_title, category, source FROM marts.mart_opex_monthly ORDER BY 1, 4").fetchall()],
        "opex": None,
        "recon": rows("SELECT location_key, strftime(month, '%Y-%m') AS month, category, ops_source, "
                      "ops_amount, gl_amount FROM marts.mart_reconciliation"),
        "sources": rows("""
            SELECT 'Practice management' AS source, '7 PMS systems · CDT codes' AS detail,
                   (SELECT COUNT(*) FROM raw.pms_open_dental__procedures) + (SELECT COUNT(*) FROM raw.pms_dentrix_ascend__procedures)
                   + (SELECT COUNT(*) FROM raw.pms_sensei__procedures) + (SELECT COUNT(*) FROM raw.pms_dolphin__procedures)
                   + (SELECT COUNT(*) FROM raw.pms_tdo__procedures) + (SELECT COUNT(*) FROM raw.pms_dentrix__procedures)
                   + (SELECT COUNT(*) FROM raw.pms_dox__procedures) AS n
            UNION ALL SELECT 'Sage Intacct', 'GL detail · 12 accounts', COUNT(*) FROM raw.sage_intacct__gl_detail
            UNION ALL SELECT 'UKG', 'Timecards · job + earning codes', COUNT(*) FROM raw.ukg__timecards
            UNION ALL SELECT 'Inventory', 'Usage · vendor categories', COUNT(*) FROM raw.inventory__usage
            UNION ALL SELECT 'Marketing / websites', 'UTM source + medium', COUNT(*) FROM raw.marketing__channel_performance
        """),
        "unmapped": len(dq),
    }

    idx = {(a[0], a[3]): i for i, a in enumerate(data["opex_accounts"])}
    data["opex"] = [[r[0], r[1], idx[(r[2], r[3])], round(r[4], 2)] for r in con.execute(
        "SELECT location_key, strftime(month, '%Y-%m'), account_no, source, amount FROM marts.mart_opex_monthly").fetchall()]

    def tidy(v):
        if isinstance(v, float):
            return round(v, 2)
        if isinstance(v, list):
            return [tidy(x) for x in v]
        if isinstance(v, dict):
            return {k: tidy(x) for k, x in v.items()}
        return v

    out = ROOT / "dashboard" / "data.json"
    out.write_text(json.dumps(tidy(data), default=str, separators=(",", ":")))
    tpl = (ROOT / "dashboard" / "template.html").read_text()
    (ROOT / "dashboard" / "index.html").write_text(tpl.replace("/*__DATA__*/", out.read_text()))
    print(f"wrote dashboard/data.json ({out.stat().st_size / 1024:.0f} KB) and dashboard/index.html")


if __name__ == "__main__":
    main()
