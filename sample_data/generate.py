"""Generate PLACEHOLDER exports for every Northwind source system.

Nothing here is real Northwind data. Each file is written in the shape that
system's connector lands it: its own field names, date formats, status
codes and code sets. The tables in seeds/ translate those codes into the
warehouse's shared categories.

Offices and the PMS each runs are Northwind's real list (38 offices). Everything
else per office (region where the name doesn't say, specialty where the name
doesn't say, operatories, open dates, every dollar) is PLACEHOLDER.

PMS systems:
  dentrix_ascend  rows shaped like flattened Ascend API JSON
  sensei          Sensei Cloud report export
  open_dental     Open Dental ShortQuery result
  dolphin         Dolphin Management SQL extract (orthodontics)
  tdo             TDO report export (endodontics)
  dentrix         Dentrix G-series read-only SQL extract
  dox             Dental Office Xpress report export
Field names for vendors without public docs are modeled, not confirmed.

Planted demo patterns (INVENTED, to show what the alerts catch): Gulf Breeze
overstaffed with heavy overtime and supply waste; Marina Park weak collections;
Meta ads costly per booking.
"""
from __future__ import annotations

import csv
import datetime as dt
import pathlib
import re

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "sample_data" / "exports"
SEEDS = ROOT / "seeds"
SEED = 42
START, END = dt.date(2025, 4, 1), dt.date(2026, 9, 30)

#   key name                             region            ops pms              specialty       opened        coll   labor
LOCATIONS = [
    (1, 'Harbor Point'                  , 'Central'         ,  8, 'dentrix_ascend', 'General'      , '2010-07-01', 0.974, 0.95),
    (2, 'Cedar Ridge Orthodontics'      , 'South'           ,  6, 'dolphin'       , 'Orthodontics' , '2009-06-01', 0.972, 1.05),
    (3, 'Bayview Orthodontics'          , 'South'           ,  4, 'dolphin'       , 'Orthodontics' , '2008-02-01', 0.970, 0.95),
    (4, 'Lakeshore Endodontics'         , 'North'           ,  4, 'tdo'           , 'Endodontics'  , '2016-07-01', 0.963, 1.01),
    (5, 'Southgate Oral Surgery'        , 'South'           ,  4, 'sensei'        , 'Oral Surgery' , '2018-11-01', 0.972, 0.95),
    (6, 'Pinecrest'                     , 'South'           ,  8, 'dentrix_ascend', 'General'      , '2008-04-01', 0.963, 1.04),
    (7, 'Riverbend'                     , 'South'           ,  7, 'dentrix_ascend', 'General'      , '2014-03-01', 0.972, 1.01),
    (8, 'Willow Creek'                  , 'North'           , 10, 'dentrix_ascend', 'General'      , '2021-11-01', 0.965, 1.01),
    (9, 'Maple Grove'                   , 'Central'         ,  7, 'dox'           , 'General'      , '2013-02-01', 0.972, 0.95),
    (10, 'Sunridge'                      , 'South'           ,  5, 'open_dental'   , 'General'      , '2017-04-01', 0.971, 1.00),
    (11, 'Oak Hollow'                    , 'West'            ,  8, 'sensei'        , 'General'      , '2015-10-01', 0.979, 0.98),
    (12, 'Fairhaven'                     , 'South'           ,  7, 'dentrix_ascend', 'General'      , '2020-03-01', 0.975, 0.97),
    (13, 'Gulf Breeze'                   , 'Central'         ,  7, 'dentrix_ascend', 'General'      , '2016-08-01', 0.978, 1.22),
    (14, 'Stonebridge'                   , 'South'           ,  7, 'dentrix_ascend', 'General'      , '2017-02-01', 0.964, 0.99),
    (15, 'Brookside'                     , 'West'            ,  8, 'dentrix_ascend', 'General'      , '2010-08-01', 0.970, 1.06),
    (16, 'Marina Park'                   , 'North'           ,  6, 'dentrix_ascend', 'General'      , '2020-09-01', 0.885, 1.05),
    (17, 'Clearwater Ridge'              , 'Central'         ,  8, 'dentrix_ascend', 'General'      , '2013-12-01', 0.968, 1.00),
    (18, 'Heron Bay'                     , 'Central'         ,  9, 'dentrix_ascend', 'General'      , '2009-02-01', 0.979, 1.00),
    (19, 'Palm Terrace'                  , 'West'            ,  6, 'dentrix_ascend', 'General'      , '2008-12-01', 0.975, 1.02),
    (20, 'Laurel Springs'                , 'North'           ,  9, 'dentrix_ascend', 'General'      , '2012-12-01', 0.969, 1.02),
    (21, 'Magnolia Park Park'                 , 'Central'         ,  5, 'dentrix_ascend', 'General'      , '2015-06-01', 0.965, 0.95),
    (22, 'Ashford'                       , 'South'           ,  5, 'dentrix_ascend', 'General'      , '2011-05-01', 0.964, 0.97),
    (23, 'Kingsley'                      , 'West'            ,  8, 'dentrix_ascend', 'General'      , '2022-08-01', 0.963, 0.99),
    (24, 'Bramble Lane'                  , 'North'           , 10, 'dentrix_ascend', 'General'      , '2012-03-01', 0.977, 1.04),
    (25, 'Seaview Implant Center'        , 'East'            ,  5, 'dentrix_ascend', 'Oral Surgery' , '2019-07-01', 0.980, 1.02),
    (26, 'Northfield Periodontics'       , 'South'           ,  5, 'open_dental'   , 'Periodontics' , '2011-03-01', 0.963, 0.96),
    (27, 'Eastlake - Sunrise'            , 'North'           ,  7, 'dentrix_ascend', 'General'      , '2008-08-01', 0.977, 0.96),
    (28, 'Eastlake - Wells'              , 'North'           ,  7, 'dentrix_ascend', 'General'      , '2008-03-01', 0.970, 0.98),
    (29, 'Eastlake - Dunmore'            , 'North'           ,  8, 'dentrix_ascend', 'General'      , '2010-12-01', 0.977, 1.05),
    (30, 'Westport - Bay'                , 'South'           ,  5, 'sensei'        , 'General'      , '2015-11-01', 0.976, 0.99),
    (31, 'Westport - Bayfront'        , 'South'           ,  8, 'sensei'        , 'General'      , '2014-02-01', 0.971, 0.99),
    (32, 'Westport Oral Surgery'         , 'South'           ,  4, 'sensei'        , 'Oral Surgery' , '2009-04-01', 0.970, 0.95),
    (33, 'Midland'                       , 'Central'         ,  5, 'dentrix_ascend', 'General'      , '2009-01-01', 0.972, 1.00),
    (34, 'Tall Pines'                    , 'South'           ,  8, 'dentrix_ascend', 'General'      , '2017-01-01', 0.963, 0.96),
    (35, 'Hillcrest'                     , 'West'            ,  8, 'dentrix'       , 'General'      , '2010-11-01', 0.967, 0.98),
    (36, 'Featherstone'                  , 'West'            ,  8, 'dentrix_ascend', 'General'      , '2015-02-01', 0.964, 1.00),
    (37, 'Rosewood Periodontics'         , 'Central'         ,  5, 'dentrix_ascend', 'Periodontics' , '2015-08-01', 0.968, 0.96),
    (38, 'Thornbury'                     , 'South'           ,  8, 'dentrix'       , 'General'      , '2019-05-01', 0.971, 1.02),
]
SLUG = {k: re.sub(r'[^a-z0-9]+', '-', n.lower()).strip('-') for k, n, *_ in LOCATIONS}
OVERSTAFFED = {k for k, *_, labor in LOCATIONS if labor > 1.1}
SEASON = {1: .97, 2: 1.0, 3: 1.04, 4: 1.0, 5: 1.01, 6: 1.03, 7: 1.05, 8: 1.04, 9: .98, 10: 1.0, 11: .95, 12: .86}


def codes(k, pms):
    """Each system's own identifier for the same practice."""
    pms_code = {"open_dental": str(k), "dentrix_ascend": f"asc-loc-{k:04d}", "sensei": f"Practice {k}",
                "dolphin": f"DOL-{k:02d}", "tdo": f"Office {k}", "dentrix": f"C{k:03d}", "dox": f"DOX{k:02d}"}[pms]
    return {pms: pms_code, "sage_intacct": f"E{100 + k}", "ukg": f"UK{k:02d}",
            "inventory": f"S{k:02d}", "marketing": SLUG[k]}


# visit templates by specialty: (name, weight, hygiene?, [(cdt, probability), ...])
TEMPLATES = {
    "General": (3.4, [
        ("recall", .48, True, [("D0120", 1), ("D1110", 1), ("D0274", .5), ("D1206", .25)]),
        ("perio_maint", .07, True, [("D4910", 1), ("D0120", .6)]),
        ("new_patient", .08, True, [("D0150", 1), ("D0210", .9), ("D1110", .8), ("D0330", .3)]),
        ("srp", .03, True, [("D4341", 1), ("D4341", .9)]),
        ("restorative", .20, False, [("D2392", .7), ("D2391", .6), ("D2392", .3)]),
        ("crown", .06, False, [("D2950", .8), ("D2740", 1)]),
        ("endo", .03, False, [("D3330", 1), ("D2950", .5)]),
        ("extraction", .04, False, [("D0140", .7), ("D7140", .7), ("D7210", .3)]),
        ("implant", .01, False, [("D6010", 1)]),
    ]),
    "Orthodontics": (5.0, [
        ("adjustment", .78, False, [("D8670", 1)]),
        ("consult", .07, False, [("D8660", 1), ("D0330", .8)]),
        ("start_teen", .015, False, [("D8080", 1)]),
        ("start_adult", .006, False, [("D8090", 1)]),
        ("retention", .09, False, [("D8680", 1)]),
    ]),
    "Endodontics": (2.4, [
        ("consult", .30, False, [("D9310", 1), ("D0220", 1), ("D0367", .3)]),
        ("rct_molar", .30, False, [("D3330", 1), ("D0220", .8)]),
        ("rct_premolar", .17, False, [("D3320", 1), ("D0220", .8)]),
        ("rct_anterior", .10, False, [("D3310", 1), ("D0220", .8)]),
        ("retreat", .07, False, [("D3346", 1), ("D0220", 1)]),
        ("post_op", .06, False, [("D0140", 1)]),
    ]),
    "Oral Surgery": (2.6, [
        ("consult", .25, False, [("D9310", 1), ("D0330", .7), ("D0367", .3)]),
        ("extraction", .18, False, [("D7140", 1), ("D7140", .4)]),
        ("third_molars", .17, False, [("D7240", 1), ("D7240", .9), ("D9239", .9)]),
        ("surgical_ext", .15, False, [("D7210", 1), ("D7953", .4)]),
        ("implant", .15, False, [("D6010", 1), ("D7953", .3), ("D9239", .3)]),
        ("post_op", .10, False, [("D0140", 1)]),
    ]),
    "Periodontics": (3.0, [
        ("consult", .12, False, [("D9310", 1), ("D0210", .8)]),
        ("perio_maint", .40, True, [("D4910", 1), ("D0120", .5)]),
        ("srp", .18, True, [("D4341", 1), ("D4341", .9), ("D4342", .3)]),
        ("osseous", .10, False, [("D4260", 1)]),
        ("graft", .08, False, [("D4273", 1)]),
        ("implant", .07, False, [("D6010", 1), ("D7953", .3)]),
        ("post_op", .05, False, [("D0140", 1)]),
    ]),
}
LAB_CODES = {"D2740": .20, "D6010": .20, "D8080": .06, "D8090": .06}

STAFF_PLAN = {  # job code, base rate, headcount as a function of operatories
    "General": [("RDH01", 46, lambda o, m: round(o * .5)), ("DA01", 22, lambda o, m: round(o * .30 * m)),
                ("EFDA01", 27, lambda o, m: max(1, round(o * .15 * m))), ("FD01", 19, lambda o, m: 2),
                ("INS01", 21, lambda o, m: 1 if o >= 8 else 0), ("OM01", 30, lambda o, m: 1)],
    "Orthodontics": [("DA01", 21, lambda o, m: round(o * .8 * m)), ("FD01", 19, lambda o, m: 2),
                     ("INS01", 21, lambda o, m: 1), ("OM01", 30, lambda o, m: 1)],
    "Endodontics": [("DA01", 24, lambda o, m: round(o * 1.0 * m)), ("FD01", 19, lambda o, m: 2),
                    ("OM01", 30, lambda o, m: 1)],
    "Oral Surgery": [("DA01", 24, lambda o, m: round(o * 1.2 * m)), ("FD01", 19, lambda o, m: 2),
                     ("INS01", 21, lambda o, m: 1), ("OM01", 30, lambda o, m: 1)],
    "Periodontics": [("RDH01", 46, lambda o, m: round(o * .5)), ("DA01", 23, lambda o, m: round(o * .6 * m)),
                     ("FD01", 19, lambda o, m: 2), ("OM01", 30, lambda o, m: 1)],
}
CLINICAL_JOBS = {"RDH01", "DA01", "EFDA01"}

INVENTORY_ITEMS = [
    ("100-2241", "Nitrile exam gloves, medium", "GLOVES/MASKS", "BX", 0.26, 9.80),
    ("100-3310", "Level 3 procedure masks", "GLOVES/MASKS", "BX", 0.11, 14.50),
    ("110-0182", "Surface disinfectant wipes", "INFECTION CONTROL", "CN", 0.07, 11.25),
    ("220-4410", "Composite resin syringe A2", "RESTORATIVE MATERIALS", "EA", 0.18, 42.00),
    ("230-1120", "VPS impression cartridge", "IMPRESSION MATERIALS", "EA", 0.07, 28.00),
    ("310-0770", "Prophy paste cups, medium grit", "HYGIENE/PREVENTIVE", "BX", 0.04, 36.00),
    ("320-1001", "Fluoride varnish unit dose", "HYGIENE/PREVENTIVE", "BX", 0.018, 89.00),
    ("400-5520", "Patient bibs", "DISPOSABLES", "CS", 0.004, 48.00),
    ("410-2205", "Lidocaine 2% w/ epi, 50 carp", "ANESTHETICS", "BX", 0.013, 61.00),
    ("500-9001", "Implant healing abutment", "IMPLANT COMPONENTS", "EA", 0.007, 185.00),
]

MARKETING_ROWS = [  # utm_source, utm_medium, campaign, base monthly spend, cost per lead, lead->booked
    ("google", "cpc", "brand+local_search", 1700, 55, .55),
    ("bing", "cpc", "local_search", 500, 50, .55),
    ("facebook", "paid_social", "new_patient_special", 1000, 70, .28),
    ("instagram", "paid_social", "new_patient_special", 500, 75, .26),
    ("google", "organic", "(not set)", 600, 30, .50),
    ("bing", "organic", "(not set)", 0, 0, .50),
    ("referral", "referral", "(not set)", 0, 0, .70),
    ("(direct)", "(none)", "(not set)", 0, 0, .45),
]


# ---------------- per-vendor row writers ----------------
def pms_row(pms, loc, appt, pat, d, prov, code, fee, wo, status):
    if pms == "open_dental":     # AptStatus: 2 Complete, 5 Broken, 3 UnschedList
        st = {"completed": 2, "no_show": 5, "cancelled": 3}[status]
        return (loc, appt, pat, d.isoformat(), prov, code, fee, wo, st)
    if pms == "dentrix_ascend":
        st = {"completed": "COMPLETE", "no_show": "BROKEN", "cancelled": "CANCELLED"}[status]
        return (loc, f"apt-{appt}", f"pat-{pat}", f"{d.isoformat()}T00:00:00Z", f"prv-{prov}", code, fee, wo, st)
    if pms == "sensei":
        st = {"completed": "Completed", "no_show": "No Show", "cancelled": "Canceled"}[status]
        return (loc, d.strftime("%d-%b-%Y"), code, fee, wo, prov, st, pat, appt)
    if pms == "dolphin":
        st = {"completed": "C", "no_show": "NS", "cancelled": "X"}[status]
        return (loc, f"V{appt}", f"PT-{pat}", d.strftime("%m/%d/%Y"), prov, code, fee, wo, st)
    if pms == "dentrix":         # Dentrix G-series SQL extract (SQL Server datetimes)
        st = {"completed": "C", "no_show": "B", "cancelled": "D"}[status]
        return (loc, appt, f"G{pat}", f"{d.isoformat()} 00:00:00.000", prov, code, fee, wo, st)
    if pms == "dox":             # Dental Office Xpress report export
        st = {"completed": "Done", "no_show": "Missed", "cancelled": "Canc"}[status]
        return (loc, d.strftime("%m-%d-%Y"), code, fee, wo, prov, st, pat, appt)
    st = {"completed": "Seen", "no_show": "No-Show", "cancelled": "Cancelled"}[status]   # tdo
    return (loc, d.strftime("%Y%m%d"), code, fee, wo, prov, st, pat, appt)


def pay_row(pms, loc, d, is_ins, amt):
    if pms == "open_dental":
        return (loc, d.isoformat(), "Insurance" if is_ins else "Patient", amt)
    if pms == "dentrix_ascend":
        return (loc, f"{d.isoformat()}T00:00:00Z", "INSURANCE_PAYMENT" if is_ins else "PATIENT_PAYMENT", amt)
    if pms == "sensei":
        return (loc, d.strftime("%d-%b-%Y"), "Insurance Payment" if is_ins else "Patient Payment", amt)
    if pms == "dolphin":
        return (loc, d.strftime("%m/%d/%Y"), "INS" if is_ins else "PAT", amt)
    if pms == "dentrix":
        return (loc, f"{d.isoformat()} 00:00:00.000", "InsPayment" if is_ins else "PatPayment", amt)
    if pms == "dox":
        return (loc, d.strftime("%m-%d-%Y"), "Insurance" if is_ins else "Patient", amt)
    return (loc, d.strftime("%Y%m%d"), "Ins" if is_ins else "Pt", amt)


def prov_row(pms, loc, prov, is_dentist, specialty):
    if pms == "open_dental":     # provider.IsSecondary = 1 marks a hygienist
        return (prov, loc, 0 if is_dentist else 1)
    if pms == "dentrix_ascend":
        return (f"prv-{prov}", loc, "DENTIST" if is_dentist else "HYGIENIST")
    if pms == "sensei":
        return (loc, prov, "Doctor" if is_dentist else "Hygienist")
    if pms == "dolphin":
        return (prov, loc, "DDS, MS Orthodontics")
    if pms == "dentrix":
        return (prov, loc, "Dentist" if is_dentist else "Hygienist")
    if pms == "dox":
        return (loc, prov, "DDS" if is_dentist else "RDH")
    return (loc, prov, "Endodontist")


HEADERS = {
    "open_dental": (["ClinicNum", "AptNum", "PatNum", "ProcDate", "ProvNum", "ProcCode", "ProcFee", "WriteOff", "AptStatus"],
                    ["ClinicNum", "PayDate", "PayType", "PayAmt"], ["ProvNum", "ClinicNum", "IsSecondary"]),
    "dentrix_ascend": (["locationId", "appointmentId", "patientId", "procedureDate", "providerId", "adaCode", "fee",
                        "adjustmentTotal", "appointmentStatus"],
                       ["locationId", "transactionDate", "transactionType", "amount"],
                       ["providerId", "locationId", "providerType"]),
    "sensei": (["Practice", "Date of Service", "Procedure", "Charge", "Adj", "Provider", "Appt Status", "Patient #",
                "Appointment #"], ["Practice", "Date", "Transaction Type", "Amount"],
               ["Practice", "Provider", "Provider Type"]),
    "dolphin": (["office_code", "visit_id", "patient_ref", "service_date", "provider_code", "ada_code", "fee_usd",
                 "contractual_adj", "status"], ["office_code", "posted", "source", "amount"],
                ["provider_code", "office_code", "credential"]),
    "tdo": (["Office", "Visit Date", "CDT", "Gross", "Adjustment", "Doctor", "Status", "Chart #", "Visit ID"],
            ["Office", "Posted Date", "Payer Type", "Amount"], ["Office", "Doctor", "Role"]),
    "dentrix": (["ClinicID", "ApptID", "PatGUID", "ProcDate", "ProvID", "ADACode", "Amt", "AdjAmt", "ApptStatus"],
                ["ClinicID", "TransDate", "TransType", "Amount"], ["ProvID", "ClinicID", "ProvType"]),
    "dox": (["Office", "Svc Date", "Code", "Fee", "Discount", "Provider", "Appt Result", "Acct #", "Appt #"],
            ["Office", "Pmt Date", "Pmt Source", "Amount"], ["Office", "Provider", "Type"]),
}


GL_TITLES = {r["account_no"]: r["account_title"]
             for r in csv.DictReader(open(SEEDS / "gl_account_map.csv"))} if (SEEDS / "gl_account_map.csv").exists() else {}
PMS_MONTHLY_FEE = {"open_dental": 210, "dentrix_ascend": 640, "sensei": 520, "dolphin": 480, "tdo": 450,
                   "dentrix": 430, "dox": 300}
HOT = {6: 1.3, 7: 1.4, 8: 1.4, 9: 1.25, 5: 1.1, 10: 1.05}       # summer A/C months


def gl_lines(rng, m, k, pms, specialty, ops, n_doctors, headcount, agg, supply_total, spend_total, coll_rate, ramp):
    """One month of Sage Intacct GL activity for one practice: (account, dept, TR_TYPE, amount).
    Amounts are placeholders sized like a multi-location dental group."""
    u = lambda lo, hi: rng.uniform(lo, hi)
    chance = lambda p: rng.random() < p
    wages = agg.get("wage_clin", 0) + agg.get("wage_admin", 0) + agg.get("pto", 0)
    quarter_end = m.month in (3, 6, 9, 12)
    bonus = wages * .045 * u(.8, 1.2) if quarter_end else 0
    if m.month == 12:
        bonus += headcount * 250                               # year-end bonus
    workstations = round(ops * 1.5) + 4
    lines = [
        ("4000", "CLIN", -1, agg["collections"] * u(.995, 1.005)),
        ("4900", "CLIN", 1, agg["collections"] * u(.002, .006)),              # refunds (debit to revenue)
        # doctors
        ("5100", "CLIN", 1, agg["dentist_net"] * coll_rate * .30),
        ("5110", "CLIN", 1, 1150 * n_doctors),
        # clinical supplies & lab
        ("5200", "CLIN", 1, agg["lab"]),
        ("5300", "CLIN", 1, supply_total * u(.97, 1.03)),
        ("5310", "CLIN", 1, 30 * ops * u(.6, 1.6)),
        # staff payroll & benefits (wages themselves come from UKG and are booked here to reconcile)
        ("6000", "CLIN", 1, agg.get("wage_clin", 0) * u(.985, 1.015)),
        ("6010", "ADMIN", 1, agg.get("wage_admin", 0) * u(.985, 1.015)),
        ("6030", "ADMIN", 1, agg.get("pto", 0) * u(.99, 1.01)),
        ("6040", "ADMIN", 1, bonus),
        ("6050", "ADMIN", 1, (wages + bonus) * (.0765 + (.02 if m.month <= 3 else .004))),   # FUTA/SUTA front-loaded
        ("6060", "ADMIN", 1, headcount * .5 * 520 * u(.97, 1.03)),
        ("6070", "ADMIN", 1, wages * .03 * .65),
        ("6080", "ADMIN", 1, wages * .006),
        # occupancy
        ("6100", "ADMIN", 1, 1750 * ops),
        ("6110", "ADMIN", 1, 165 * ops),
        # utilities
        ("6150", "ADMIN", 1, 230 * ops * HOT.get(m.month, 1.0) * u(.92, 1.08)),
        ("6155", "ADMIN", 1, 48 * ops * u(.9, 1.1)),
        ("6160", "ADMIN", 1, 185),
        ("6165", "ADMIN", 1, 265),
        ("6170", "ADMIN", 1, 26 * (ops + 4)),
        ("6175", "ADMIN", 1, 110),
        # facilities & maintenance (lumpy repairs)
        ("6200", "ADMIN", 1, 250 * u(.5, 1.5) + (u(900, 6500) if chance(.14) else 0)),
        ("6210", "ADMIN", 1, (325 if m.month in (1, 4, 7, 10) else 0) + (u(600, 4800) if chance(.05 + .12 * (m.month in HOT)) else 0)),
        ("6220", "ADMIN", 1, 850 + 95 * ops),
        ("6225", "ADMIN", 1, 425 * u(.9, 1.2) if m.month in (2, 5, 8, 11) else 0),
        ("6230", "ADMIN", 1, 95),
        ("6240", "ADMIN", 1, 45 + ((180 + 22 * ops) if m.month == (k % 12) + 1 else 0)),   # annual inspection + recharge
        ("6250", "ADMIN", 1, 59),
        # dental equipment
        ("6300", "CLIN", 1, 280 * u(.5, 1.5) + (u(700, 5200) if chance(.2) else 0)),
        ("6310", "CLIN", 1, 140 + (u(450, 900) if m.month == ((k + 5) % 12) + 1 else 0)),
        ("6320", "CLIN", 1, 1450 if specialty != "General" else 900),                     # CBCT / chair leases
        # technology & software
        ("6330", "ADMIN", 1, 85 * workstations),
        ("6340", "ADMIN", 1, PMS_MONTHLY_FEE[pms] + 18 * n_doctors * 4),
        ("6345", "CLIN", 1, 240 + (180 if specialty != "General" else 0)),
        ("6350", "ADMIN", 1, 34 * headcount + 180),
        ("6380", "ADMIN", 1, u(1100, 3200) if chance(.12) else 0),
        # office & administrative
        ("6400", "ADMIN", 1, 260 + 45 * ops * u(.8, 1.2)),
        ("6410", "ADMIN", 1, 115 * u(.8, 1.2)),
        ("6420", "ADMIN", 1, 95 * u(.7, 1.3)),
        ("6440", "ADMIN", 1, 120 * u(.5, 1.5)),
        # marketing
        ("6600", "ADMIN", 1, spend_total),
        ("6630", "ADMIN", 1, 140 * u(.6, 1.4) * (1.5 if ramp < 1 else 1)),
        # staff development & HR
        ("6700", "ADMIN", 1, 32 * headcount * u(.7, 1.3)),
        ("6710", "ADMIN", 1, (n_doctors * 180 + headcount * 35) * u(.4, 1.8)),
        ("6720", "ADMIN", 1, 40 + (n_doctors * 650 + headcount * 95 if m.month == 1 else 0)),   # annual renewals
        ("6730", "ADMIN", 1, u(400, 2200) if chance(.3) else 0),
        ("6740", "ADMIN", 1, 14 * headcount + (headcount * 60 if m.month == 12 else 0)),
        # insurance & professional fees
        ("6800", "ADMIN", 1, 360 * n_doctors),
        ("6810", "ADMIN", 1, 290 + 18 * ops),
        ("6820", "ADMIN", 1, 92),
        ("6830", "ADMIN", 1, 620 + (1400 if m.month in (2, 3) else 0)),                   # tax season
        ("6850", "ADMIN", 1, agg.get("patient_coll", 0) * .026),
        ("6860", "ADMIN", 1, agg["collections"] * .003 * (2.5 if coll_rate < .93 else 1)),
        # compliance & safety
        ("6900", "CLIN", 1, 155 + 6 * ops),
        ("6910", "ADMIN", 1, 129),
        ("6920", "CLIN", 1, 85 + (240 if m.month in (3, 9) else 0)),
    ]
    return lines


def read_seed(name):
    with open(SEEDS / name) as f:
        return list(csv.DictReader(f))


def write(path: pathlib.Path, header, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def month_starts():
    d = START
    while d <= END:
        yield d
        d = (d.replace(day=28) + dt.timedelta(days=4)).replace(day=1)


def main():
    rng = np.random.default_rng(SEED)
    fees = {r["cdt_code"]: float(r["typical_fee"]) * 1.15 for r in read_seed("cdt_procedure_map.csv")}   # regional fee levels

    write(SEEDS / "dim_location.csv",
          ["location_key", "location_name", "region", "specialty", "open_date", "operatories", "pms_system"],
          [(k, n, r, sp, o, ops, p) for k, n, r, ops, p, sp, o, _, _ in LOCATIONS])
    xw = []
    for k, _n, _r, _ops, pms, *_ in LOCATIONS:
        xw += [(s, c, k) for s, c in codes(k, pms).items()]
    write(SEEDS / "location_crosswalk.csv", ["source_system", "source_location", "location_key"], xw)

    procs = {p: [] for p in HEADERS}
    pays = {p: [] for p in HEADERS}
    provs = {p: [] for p in HEADERS}
    ukg, gl, inv, mkt = [], [], [], []
    monthly = {}
    rec = 100000
    days = [START + dt.timedelta(d) for d in range((END - START).days + 1)]

    for k, name, region, ops, pms, specialty, opened, coll_rate, labor_mult in LOCATIONS:
        c = codes(k, pms)
        loc = c[pms]
        open_d = dt.date.fromisoformat(opened)
        visits_per_op, templates = TEMPLATES[specialty]
        tnames = [t[0] for t in templates]
        tprob = np.array([t[1] for t in templates]); tprob /= tprob.sum()
        tinfo = {t[0]: t for t in templates}

        def ramp_of(d):
            return 1.0 if open_d <= START else min(1.0, 0.35 + 0.11 * (d - open_d).days / 30)

        n_dds = max(1, round(ops / 3)) if specialty == "General" else 2
        n_rdh = max(1, round(ops * .5)) if specialty in ("General", "Periodontics") else 0
        dds = [f"{k}D{i}" for i in range(n_dds)]
        rdh = [f"{k}H{i}" for i in range(n_rdh)]
        for p in dds + rdh:
            provs[pms].append(prov_row(pms, loc, p, p in dds, specialty))

        # ---------------- visits, procedures, payments ----------------
        appt_no = 0
        for d in days:
            if d < open_d or d.weekday() >= 5:
                continue
            ramp, trend = ramp_of(d), 1 + 0.06 * (d - START).days / 365
            n = rng.poisson(ops * visits_per_op * SEASON[d.month] * ramp * trend)
            agg = monthly.setdefault((k, d.replace(day=1)), {"collections": 0.0, "lab": 0.0, "dentist_net": 0.0})
            day_net = 0.0
            for _ in range(n):
                appt_no += 1
                appt = f"{k}{appt_no:07d}"
                pat = f"{k}{rng.integers(1, 9000):05d}"
                t = tnames[rng.choice(len(tnames), p=tprob)]
                if ramp < 1 and specialty == "General" and rng.random() < .08:
                    t = "new_patient"
                _, _, is_hyg, lines = tinfo[t]
                status = rng.choice(["completed", "no_show", "cancelled"], p=[.86, .07, .07])
                pool = rdh if is_hyg else dds
                prov = pool[rng.integers(0, len(pool))]
                if status == "completed":
                    todo = [cd for cd, p in lines if rng.random() < p] or [lines[0][0]]
                else:
                    todo = [""]
                for code in todo:
                    fee = round(fees[code] * rng.uniform(.95, 1.08), 2) if code else 0.0
                    wo = round(fee * rng.uniform(.12, .22), 2)
                    day_net += fee - wo
                    agg["lab"] += fee * LAB_CODES.get(code, 0)
                    if prov in dds:
                        agg["dentist_net"] += fee - wo
                    procs[pms].append(pms_row(pms, loc, appt, pat, d, prov, code, fee, wo, status))
            collected = day_net * min(1.0, rng.normal(coll_rate, .015))
            agg["collections"] += collected
            agg["patient_coll"] = agg.get("patient_coll", 0) + collected * .38
            for is_ins, share in ((True, .62), (False, .38)):
                pays[pms].append(pay_row(pms, loc, d, is_ins, round(collected * share, 2)))

        # ---------------- UKG timecards ----------------
        staff = []
        for job, rate, count in STAFF_PLAN[specialty]:
            for _ in range(count(ops, labor_mult)):
                staff.append((f"1{k:02d}{len(staff):03d}", job, round(rate * rng.uniform(.92, 1.1), 2)))
        heavy = labor_mult > 1.1
        for d in days:
            if d < open_d or d.weekday() >= 5:
                continue
            agg = monthly[(k, d.replace(day=1))]
            for emp, job, rate in staff:
                wkey = "wage_clin" if job in CLINICAL_JOBS else "wage_admin"
                r = rng.random()
                if r < .04:
                    ukg.append((emp, c["ukg"], job, d.isoformat(), "PTO", 8.0, rate))
                    agg["pto"] = agg.get("pto", 0) + 8 * rate
                    continue
                if r < .06:
                    continue
                reg = round(min(8.0, rng.normal(7.8, .4)), 2)
                ot = round(max(0.0, rng.normal(.25 * labor_mult ** 6 if heavy else .1, .4 if heavy else .3)), 2)
                ukg.append((emp, c["ukg"], job, d.isoformat(), "REG", reg, rate))
                if ot > .05:
                    ukg.append((emp, c["ukg"], job, d.isoformat(), "OT", ot, rate))
                agg[wkey] = agg.get(wkey, 0) + reg * rate + ot * rate * 1.5

        # ---------------- monthly: inventory, marketing, GL ----------------
        for m in month_starts():
            if (k, m) not in monthly:
                continue
            ramp = ramp_of(m)
            vol = ops * 3.4 * 21 * SEASON[m.month] * ramp
            agg = monthly[(k, m)]

            supply_total = 0.0
            for item, desc, vcat, uom, per_visit, cost in INVENTORY_ITEMS:
                if specialty not in ("General", "Periodontics") and vcat == "HYGIENE/PREVENTIVE":
                    continue
                if specialty not in ("General", "Periodontics", "Oral Surgery") and vcat == "IMPLANT COMPONENTS":
                    continue
                qty = round(vol * per_visit * (1.18 if k in OVERSTAFFED else 1.0) * rng.uniform(.9, 1.1), 1)
                uc = round(cost * rng.uniform(.97, 1.05), 2)
                supply_total += qty * uc
                inv.append((c["inventory"], m.strftime("%Y%m"), item, desc, vcat, uom, qty, uc,
                            round(qty * rng.uniform(.4, 1.3), 1)))

            spend_total = 0.0
            for src, med, camp, base, cpl, conv in MARKETING_ROWS:
                spend = round(base * (1.6 if ramp < 1 else 1.0) * rng.uniform(.85, 1.15) * ops / 8, 2) if base else 0.0
                leads = int(spend / cpl) if cpl else max(0, int(rng.normal(6, 2) * ops / 8))
                spend_total += spend
                mkt.append((SLUG[k], m.isoformat(), src, med, camp, spend, int(leads * rng.uniform(18, 30)),
                            leads, int(leads * conv * rng.uniform(.85, 1.1))))

            last_day = (m.replace(day=28) + dt.timedelta(days=4)).replace(day=1) - dt.timedelta(days=1)
            for acct, dept, tr, amt in gl_lines(rng, m, k, pms, specialty, ops, len(dds), len(staff), agg,
                                                supply_total, spend_total, coll_rate, ramp):
                if amt <= 0:
                    continue
                rec += 1
                gl.append((rec, last_day.isoformat(), f"{m:%b %Y} month-end close", acct, GL_TITLES[acct],
                           c["sage_intacct"], dept, tr, round(amt, 2)))

    # ---------------- write ----------------
    import shutil
    if OUT.exists():
        shutil.rmtree(OUT)
    for pms, (h_proc, h_pay, h_prov) in HEADERS.items():
        write(OUT / f"pms_{pms}" / "procedures.csv", h_proc, procs[pms])
        write(OUT / f"pms_{pms}" / "payments.csv", h_pay, pays[pms])
        write(OUT / f"pms_{pms}" / "providers.csv", h_prov, provs[pms])
    write(OUT / "sage_intacct" / "gl_detail.csv",
          ["RECORDNO", "ENTRY_DATE", "BATCH_TITLE", "ACCOUNTNO", "ACCOUNTTITLE", "LOCATIONID", "DEPARTMENTID",
           "TR_TYPE", "AMOUNT"], gl)
    write(OUT / "ukg" / "timecards.csv",
          ["EmployeeNumber", "OrgLevel1", "JobCode", "WorkDate", "EarningCode", "Hours", "HourlyRate"], ukg)
    write(OUT / "inventory" / "usage.csv",
          ["SiteCode", "Period", "ItemNumber", "Description", "VendorCategory", "UOM", "QtyIssued", "UnitCost",
           "QtyOnHand"], inv)
    write(OUT / "marketing" / "channel_performance.csv",
          ["site_slug", "month", "utm_source", "utm_medium", "utm_campaign", "cost", "sessions", "form_submits",
           "appts_booked"], mkt)

    for p in sorted(OUT.rglob("*.csv")):
        print(f"{str(p.relative_to(ROOT)):52s} {sum(1 for _ in open(p)) - 1:>9,} rows")


if __name__ == "__main__":
    main()
