"""Practice management connectors for Northwind's seven PMS systems (38 offices).

  Open Dental     public REST API (developer key + per-office customer key).
                  Fully implemented through the ShortQuery endpoint, so we
                  control exactly which tables and columns are pulled.
  Dentrix Ascend  Henry Schein One API Exchange. Access requires partner
                  approval (security review, SOC 2 Type II, OAuth 2.0).
                  OAuth + paging are implemented; endpoint paths and field
                  names get filled in from the docs H1 provides on approval.
  Sensei Cloud    no self-serve API (gated developer program). Default is a
                  scheduled report export dropped to a folder / SFTP.
  Dolphin         Dolphin Management on-prem SQL Server: read-only query.
                  Dolphin Cloud offices: report export instead.
  TDO             TDO Cloud: report export. On-prem TDO: read-only query.
  Dentrix         Dentrix G-series (on-prem, 2 offices): read-only database
                  views through the Dentrix Developer Program (DDP@Dentrix.com),
                  queried over ODBC from a machine in the office.
  Dental Office   DOX (1 office): scheduled report export to a folder / SFTP.
  Xpress (DOX)    Column names modeled until the office exports a sample.

Office count by PMS: Dentrix Ascend 24, Sensei 5, Open Dental 2, Dolphin 2,
Dentrix 2, TDO 1, DOX 1. Ascend is the critical path: 24 of 38 offices
depend on Henry Schein One API Exchange approval.

PMS data is PHI. Do not run these against real offices until Northwind has a
signed BAA with whoever stores the data and company sign-off is in place.
"""
from __future__ import annotations

import datetime as dt
import time

import requests

from .base import Connector, FileDropConnector, SqlServerConnector, env, env_map

# ======================================================================
# Open Dental
# ======================================================================
OD_BASE = "https://api.opendental.com/api/v1"   # confirm against the current API spec

OD_PROCEDURES_SQL = """
SELECT pl.ProcNum, pl.AptNum, pl.PatNum, pl.ProcDate, pl.ProvNum, pc.ProcCode,
       pl.ProcFee * GREATEST(pl.UnitQty, 1) AS ProcFee,
       COALESCE(SUM(cp.WriteOff), 0) AS WriteOff,
       COALESCE(a.AptStatus, 2) AS AptStatus
FROM procedurelog pl
JOIN procedurecode pc ON pc.CodeNum = pl.CodeNum
LEFT JOIN appointment a ON a.AptNum = pl.AptNum
LEFT JOIN claimproc cp ON cp.ProcNum = pl.ProcNum
WHERE pl.ProcStatus = 2 AND pl.ProcDate >= '{since}'
GROUP BY pl.ProcNum
UNION ALL
SELECT 0, a.AptNum, a.PatNum, DATE(a.AptDateTime), a.ProvNum, '', 0, 0, a.AptStatus
FROM appointment a
WHERE a.AptStatus IN (3, 5) AND a.AptDateTime >= '{since}'
"""
OD_PAYMENTS_SQL = """
SELECT PayDate, 'Patient' AS PayType, PayAmt FROM payment WHERE PayDate >= '{since}'
UNION ALL
SELECT CheckDate, 'Insurance', CheckAmt FROM claimpayment WHERE CheckDate >= '{since}'
"""
OD_PROVIDERS_SQL = "SELECT ProvNum, IsSecondary FROM provider WHERE IsHidden = 0"


class _OpenDentalBase(Connector):
    """One Open Dental database per office: OPEN_DENTAL_CUSTOMER_KEYS maps the
    office code used in seeds/location_crosswalk.csv to that office's customer
    key, e.g. '1:abc123,2:def456'. ClinicNum is written as that office code."""
    folder = "pms_open_dental"
    sql = ""
    page = 100   # ShortQuery returns results in pages; Offset steps through them

    def _query(self, customer_key: str, sql: str):
        headers = {"Authorization": f"ODFHIR {env('OPEN_DENTAL_DEVELOPER_KEY')}/{customer_key}",
                   "Content-Type": "application/json"}
        offset = 0
        while True:
            r = requests.put(f"{OD_BASE}/queries/ShortQuery", params={"Offset": offset},
                             json={"SqlCommand": sql}, headers=headers, timeout=60)
            if r.status_code == 429:
                time.sleep(5)
                continue
            r.raise_for_status()
            rows = r.json()
            yield from rows
            if len(rows) < self.page:
                break
            offset += len(rows)

    def extract(self, since):
        for office, key in env_map("OPEN_DENTAL_CUSTOMER_KEYS").items():
            for row in self._query(key, self.sql.format(since=since.isoformat())):
                row["ClinicNum"] = office
                yield row


class OpenDentalProcedures(_OpenDentalBase):
    file = "procedures"
    sql = OD_PROCEDURES_SQL
    columns = ["ClinicNum", "AptNum", "PatNum", "ProcDate", "ProvNum", "ProcCode", "ProcFee", "WriteOff", "AptStatus"]


class OpenDentalPayments(_OpenDentalBase):
    file = "payments"
    sql = OD_PAYMENTS_SQL
    columns = ["ClinicNum", "PayDate", "PayType", "PayAmt"]


class OpenDentalProviders(_OpenDentalBase):
    file = "providers"
    sql = OD_PROVIDERS_SQL
    columns = ["ProvNum", "ClinicNum", "IsSecondary"]


# ======================================================================
# Dentrix Ascend (Henry Schein One API Exchange - partner access required)
# ======================================================================
class _AscendBase(Connector):
    """OAuth 2.0 client credentials + cursor paging. Once H1 approves API
    access, set the paths below and the FIELD_MAP for each endpoint from
    their documentation. Each Ascend location's ID goes in the crosswalk."""
    folder = "pms_dentrix_ascend"
    path = ""                    # TODO from H1 docs, e.g. "/procedures"
    field_map: dict[str, str] = {}   # landing column -> JSON field (dot paths allowed)
    _token: tuple[str, float] | None = None

    def _auth(self) -> str:
        if self._token and self._token[1] > time.time() + 60:
            return self._token[0]
        r = requests.post(env("ASCEND_TOKEN_URL"), data={"grant_type": "client_credentials"},
                          auth=(env("ASCEND_CLIENT_ID"), env("ASCEND_CLIENT_SECRET")), timeout=30)
        r.raise_for_status()
        body = r.json()
        _AscendBase._token = (body["access_token"], time.time() + body.get("expires_in", 3600))
        return body["access_token"]

    @staticmethod
    def _get(obj, dotted):
        for part in dotted.split("."):
            obj = obj.get(part) if isinstance(obj, dict) else None
        return obj

    def extract(self, since):
        if not self.path or not self.field_map:
            raise NotImplementedError("Fill in path and field_map from the Dentrix Ascend API docs after partner approval")
        url = env("ASCEND_API_BASE").rstrip("/") + self.path
        params = {"modifiedSince": since.isoformat()}     # TODO: confirm filter name
        while url:
            r = requests.get(url, params=params, headers={"Authorization": f"Bearer {self._auth()}"}, timeout=60)
            r.raise_for_status()
            body = r.json()
            for item in body.get("data", body if isinstance(body, list) else []):
                yield {col: self._get(item, src) for col, src in self.field_map.items()}
            url, params = (body.get("next") if isinstance(body, dict) else None), None   # TODO: confirm paging


class AscendProcedures(_AscendBase):
    file = "procedures"
    columns = ["locationId", "appointmentId", "patientId", "procedureDate", "providerId", "adaCode", "fee",
               "adjustmentTotal", "appointmentStatus"]


class AscendPayments(_AscendBase):
    file = "payments"
    columns = ["locationId", "transactionDate", "transactionType", "amount"]


class AscendProviders(_AscendBase):
    file = "providers"
    columns = ["providerId", "locationId", "providerType"]


# ======================================================================
# Sensei Cloud - scheduled report exports (env prefix SENSEI_PROC / SENSEI_PAY / SENSEI_PROV)
# ======================================================================
class SenseiProcedures(FileDropConnector):
    folder, file, env_prefix = "pms_sensei", "procedures", "SENSEI_PROC"
    columns = ["Practice", "Date of Service", "Procedure", "Charge", "Adj", "Provider", "Appt Status",
               "Patient #", "Appointment #"]


class SenseiPayments(FileDropConnector):
    folder, file, env_prefix = "pms_sensei", "payments", "SENSEI_PAY"
    columns = ["Practice", "Date", "Transaction Type", "Amount"]


class SenseiProviders(FileDropConnector):
    folder, file, env_prefix = "pms_sensei", "providers", "SENSEI_PROV"
    columns = ["Practice", "Provider", "Provider Type"]


# ======================================================================
# Dolphin Management - read-only SQL (DOLPHIN_ODBC); queries/dolphin_*.sql
# ======================================================================
class DolphinProcedures(SqlServerConnector):
    folder, file, env_prefix, query_file = "pms_dolphin", "procedures", "DOLPHIN", "dolphin_procedures.sql"
    columns = ["office_code", "visit_id", "patient_ref", "service_date", "provider_code", "ada_code", "fee_usd",
               "contractual_adj", "status"]


class DolphinPayments(SqlServerConnector):
    folder, file, env_prefix, query_file = "pms_dolphin", "payments", "DOLPHIN", "dolphin_payments.sql"
    columns = ["office_code", "posted", "source", "amount"]


class DolphinProviders(SqlServerConnector):
    folder, file, env_prefix, query_file = "pms_dolphin", "providers", "DOLPHIN", "dolphin_providers.sql"
    columns = ["provider_code", "office_code", "credential"]


# ======================================================================
# TDO - TDO Cloud report exports (env prefix TDO_PROC / TDO_PAY / TDO_PROV)
# ======================================================================
class TDOProcedures(FileDropConnector):
    folder, file, env_prefix = "pms_tdo", "procedures", "TDO_PROC"
    columns = ["Office", "Visit Date", "CDT", "Gross", "Adjustment", "Doctor", "Status", "Chart #", "Visit ID"]


class TDOPayments(FileDropConnector):
    folder, file, env_prefix = "pms_tdo", "payments", "TDO_PAY"
    columns = ["Office", "Posted Date", "Payer Type", "Amount"]


class TDOProviders(FileDropConnector):
    folder, file, env_prefix = "pms_tdo", "providers", "TDO_PROV"
    columns = ["Office", "Doctor", "Role"]


# ======================================================================
# Dentrix G-series - read-only views via the Dentrix Developer Program (DENTRIX_ODBC)
# ======================================================================
class DentrixProcedures(SqlServerConnector):
    folder, file, env_prefix, query_file = "pms_dentrix", "procedures", "DENTRIX", "dentrix_procedures.sql"
    columns = ["ClinicID", "ApptID", "PatGUID", "ProcDate", "ProvID", "ADACode", "Amt", "AdjAmt", "ApptStatus"]


class DentrixPayments(SqlServerConnector):
    folder, file, env_prefix, query_file = "pms_dentrix", "payments", "DENTRIX", "dentrix_payments.sql"
    columns = ["ClinicID", "TransDate", "TransType", "Amount"]


class DentrixProviders(SqlServerConnector):
    folder, file, env_prefix, query_file = "pms_dentrix", "providers", "DENTRIX", "dentrix_providers.sql"
    columns = ["ProvID", "ClinicID", "ProvType"]


# ======================================================================
# Dental Office Xpress - report exports (env prefix DOX_PROC / DOX_PAY / DOX_PROV)
# ======================================================================
class DOXProcedures(FileDropConnector):
    folder, file, env_prefix = "pms_dox", "procedures", "DOX_PROC"
    columns = ["Office", "Svc Date", "Code", "Fee", "Discount", "Provider", "Appt Result", "Acct #", "Appt #"]


class DOXPayments(FileDropConnector):
    folder, file, env_prefix = "pms_dox", "payments", "DOX_PAY"
    columns = ["Office", "Pmt Date", "Pmt Source", "Amount"]


class DOXProviders(FileDropConnector):
    folder, file, env_prefix = "pms_dox", "providers", "DOX_PROV"
    columns = ["Office", "Provider", "Type"]


PMS_CONNECTORS = [OpenDentalProcedures, OpenDentalPayments, OpenDentalProviders,
                  AscendProcedures, AscendPayments, AscendProviders,
                  SenseiProcedures, SenseiPayments, SenseiProviders,
                  DolphinProcedures, DolphinPayments, DolphinProviders,
                  TDOProcedures, TDOPayments, TDOProviders,
                  DentrixProcedures, DentrixPayments, DentrixProviders,
                  DOXProcedures, DOXPayments, DOXProviders]
