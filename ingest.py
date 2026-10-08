"""Pull data from Northwind's systems into the landing folder.

    python ingest.py --list                     # show connectors and what each needs
    python ingest.py --check                    # which connectors have their env vars set
    python ingest.py --only sage,open_dental --since 2026-01-01
    python ingest.py --all --since 2025-04-01

Each connector writes one file per source table to LANDING_DIR (default
sample_data/exports). Then `python load_raw.py --dir <LANDING_DIR>` loads it into
BigQuery and `dbt build` (in dbt/) turns it into the marts. build.py --no-gen
gives the local DuckDB preview from the same files.

Do not point PMS connectors at live offices until Northwind has a signed BAA
and sign-off. For the demos, use the placeholder exports (build.py).
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys

from ingestion.connectors.base import ConfigError
from ingestion.connectors.business import (InventoryUsage, MarketingChannels, SageGLDetail,
                                           UKGTimecardsAPI, UKGTimecardsReport)
from ingestion.connectors.pms import (AscendPayments, AscendProcedures, AscendProviders, DolphinPayments,
                                      DolphinProcedures, DolphinProviders, OpenDentalPayments,
                                      OpenDentalProcedures, OpenDentalProviders, SenseiPayments,
                                      SenseiProcedures, SenseiProviders, TDOPayments, TDOProcedures,
                                      TDOProviders, DentrixPayments, DentrixProcedures, DentrixProviders,
                                      DOXPayments, DOXProcedures, DOXProviders)

GROUPS = {
    "open_dental": ([OpenDentalProcedures, OpenDentalPayments, OpenDentalProviders],
                    "OPEN_DENTAL_DEVELOPER_KEY, OPEN_DENTAL_CUSTOMER_KEYS"),
    "dentrix_ascend": ([AscendProcedures, AscendPayments, AscendProviders],
                       "ASCEND_API_BASE, ASCEND_TOKEN_URL, ASCEND_CLIENT_ID, ASCEND_CLIENT_SECRET (partner approval)"),
    "sensei": ([SenseiProcedures, SenseiPayments, SenseiProviders], "SENSEI_PROC_DROP, SENSEI_PAY_DROP, SENSEI_PROV_DROP"),
    "dolphin": ([DolphinProcedures, DolphinPayments, DolphinProviders], "DOLPHIN_ODBC + mapped queries/dolphin_*.sql"),
    "tdo": ([TDOProcedures, TDOPayments, TDOProviders], "TDO_PROC_DROP, TDO_PAY_DROP, TDO_PROV_DROP"),
    "dentrix": ([DentrixProcedures, DentrixPayments, DentrixProviders], "DENTRIX_ODBC (DDP read-only views) + mapped queries/dentrix_*.sql"),
    "dox": ([DOXProcedures, DOXPayments, DOXProviders], "DOX_PROC_DROP, DOX_PAY_DROP, DOX_PROV_DROP"),
    "sage": ([SageGLDetail], "INTACCT_SENDER_ID/PASSWORD, INTACCT_USER_ID/PASSWORD, INTACCT_COMPANY_ID"),
    "ukg": ([UKGTimecardsReport], "UKG_REPORT_DROP (or use ukg_api: UKG_VANITY_URL, UKG_APP_KEY, ...)"),
    "ukg_api": ([UKGTimecardsAPI], "UKG_VANITY_URL, UKG_APP_KEY, UKG_USERNAME/PASSWORD, UKG_CLIENT_ID/SECRET, UKG_TIMECARD_PATH"),
    "inventory": ([InventoryUsage], "INVENTORY_DROP"),
    "marketing": ([MarketingChannels], "GOOGLE_ADS_*, META_ACCESS_TOKEN, META_AD_ACCOUNT_ID, GA4_PROPERTIES"),
}
DEFAULT = [g for g in GROUPS if g != "ukg_api"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="comma-separated groups: " + ",".join(GROUPS))
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--since", default=(dt.date.today() - dt.timedelta(days=45)).isoformat())
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()

    if a.list:
        for g, (_, needs) in GROUPS.items():
            print(f"{g:15s} needs {needs}")
        return
    groups = DEFAULT if a.all or a.check else (a.only or "").split(",")
    if not groups or groups == [""]:
        ap.error("pick --only, --all, --list or --check")
    since = dt.date.fromisoformat(a.since)

    failed = 0
    for g in groups:
        if g not in GROUPS:
            ap.error(f"unknown group {g}")
        for cls in GROUPS[g][0]:
            name = f"{g}/{cls.file}"
            try:
                if a.check:
                    gen = cls().extract(since)
                    next(iter(gen), None)
                    print(f"ok      {name}")
                else:
                    n = cls().run(since)
                    print(f"landed  {name:28s} {n:>9,} rows")
            except ConfigError as e:
                failed += 1
                print(f"skip    {name:28s} {e}")
            except ModuleNotFoundError as e:
                failed += 1
                print(f"skip    {name:28s} install the {e.name} package (see requirements.txt)")
            except NotImplementedError as e:
                failed += 1
                print(f"todo    {name:28s} {e}")
            except Exception as e:      # noqa: BLE001 - report and continue with other systems
                failed += 1
                print(f"error   {name:28s} {type(e).__name__}: {e}")
    sys.exit(1 if failed and not a.check else 0)


if __name__ == "__main__":
    main()
