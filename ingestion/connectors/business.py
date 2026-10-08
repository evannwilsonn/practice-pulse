"""Connectors for Northwind's business systems: Sage Intacct, UKG, inventory, marketing."""
from __future__ import annotations

import datetime as dt
import re
import time
import uuid
import xml.etree.ElementTree as ET
from collections import defaultdict

import requests

from .base import Connector, FileDropConnector, env, env_map


# ======================================================================
# Sage Intacct - XML Web Services, readByQuery on GLDETAIL
# Needs a Web Services sender ID (licensed from Sage) plus a Web Services
# user in the company. Field names follow the GLDETAIL object; confirm
# against developer.intacct.com for your company's configuration.
# ======================================================================
INTACCT_URL = "https://api.intacct.com/ia/xml/xmlgw.phtml"


class SageGLDetail(Connector):
    folder, file = "sage_intacct", "gl_detail"
    columns = ["RECORDNO", "ENTRY_DATE", "BATCH_TITLE", "ACCOUNTNO", "ACCOUNTTITLE", "LOCATIONID",
               "DEPARTMENTID", "TR_TYPE", "AMOUNT"]

    def _call(self, function_xml: str) -> ET.Element:
        body = f"""<?xml version="1.0" encoding="UTF-8"?>
<request>
  <control>
    <senderid>{env('INTACCT_SENDER_ID')}</senderid>
    <password>{env('INTACCT_SENDER_PASSWORD')}</password>
    <controlid>{uuid.uuid4()}</controlid>
    <uniqueid>false</uniqueid>
    <dtdversion>3.0</dtdversion>
  </control>
  <operation>
    <authentication>
      <login>
        <userid>{env('INTACCT_USER_ID')}</userid>
        <companyid>{env('INTACCT_COMPANY_ID')}</companyid>
        <password>{env('INTACCT_USER_PASSWORD')}</password>
      </login>
    </authentication>
    <content><function controlid="f1">{function_xml}</function></content>
  </operation>
</request>"""
        r = requests.post(INTACCT_URL, data=body.encode(), headers={"Content-Type": "application/xml"}, timeout=120)
        r.raise_for_status()
        root = ET.fromstring(r.content)
        result = root.find(".//result")
        if result is None or result.findtext("status") != "success":
            err = root.findtext(".//errormessage/error/description2") or root.findtext(".//description2") or r.text[:500]
            raise RuntimeError(f"Sage Intacct error: {err}")
        return result.find("data")

    def extract(self, since):
        data = self._call(f"""<readByQuery><object>GLDETAIL</object><fields>{','.join(self.columns)}</fields>
            <query>ENTRY_DATE &gt;= '{since:%m/%d/%Y}'</query><pagesize>1000</pagesize></readByQuery>""")
        while data is not None:
            for rec in data:
                yield {c: rec.findtext(c) for c in self.columns}
            remaining, result_id = int(data.get("numremaining", "0")), data.get("resultId")
            if not remaining or not result_id:
                break
            data = self._call(f"<readMore><resultId>{result_id}</resultId></readMore>")


# ======================================================================
# UKG
#  * report mode (default): a UKG scheduled report (employee, org level,
#    job, date, earning code, hours, rate) delivered to SFTP. Works with
#    any UKG product and needs no API license.
#  * api mode: UKG Pro Workforce Management REST. Token request is
#    implemented; set UKG_TIMECARD_PATH to the timecard/aggregation
#    endpoint your tenant uses and adjust _rows() to its response.
# ======================================================================
class UKGTimecardsReport(FileDropConnector):
    folder, file, env_prefix = "ukg", "timecards", "UKG_REPORT"
    columns = ["EmployeeNumber", "OrgLevel1", "JobCode", "WorkDate", "EarningCode", "Hours", "HourlyRate"]


class UKGTimecardsAPI(Connector):
    folder, file = "ukg", "timecards"
    columns = UKGTimecardsReport.columns

    def _token(self, base: str) -> str:
        r = requests.post(f"{base}/api/authentication/access_token",
                          headers={"appkey": env("UKG_APP_KEY"), "Content-Type": "application/x-www-form-urlencoded"},
                          data={"username": env("UKG_USERNAME"), "password": env("UKG_PASSWORD"),
                                "client_id": env("UKG_CLIENT_ID"), "client_secret": env("UKG_CLIENT_SECRET"),
                                "grant_type": "password", "auth_chain": "OAuthLdapService"}, timeout=30)
        r.raise_for_status()
        return r.json()["access_token"]

    def _rows(self, body) -> list[dict]:
        # TODO: map your tenant's response to the landing columns
        raise NotImplementedError("Map the UKG timecard response to landing columns for your tenant")

    def extract(self, since):
        base = env("UKG_VANITY_URL").rstrip("/")
        token = self._token(base)
        r = requests.post(base + env("UKG_TIMECARD_PATH"),
                          headers={"Authorization": token, "appkey": env("UKG_APP_KEY")},
                          json={"where": {"dateRange": {"startDate": since.isoformat(),
                                                        "endDate": dt.date.today().isoformat()}}}, timeout=120)
        r.raise_for_status()
        yield from self._rows(r.json())


# ======================================================================
# Inventory - export from the inventory system dropped to a folder / SFTP
# ======================================================================
class InventoryUsage(FileDropConnector):
    folder, file, env_prefix = "inventory", "usage", "INVENTORY"
    columns = ["SiteCode", "Period", "ItemNumber", "Description", "VendorCategory", "UOM", "QtyIssued",
               "UnitCost", "QtyOnHand"]


# ======================================================================
# Marketing - Google Ads + Meta Ads spend, GA4 traffic and conversions,
# combined into one row per site / month / utm_source / utm_medium.
#   Campaigns are matched to a site by a [site-slug] tag in the campaign
#   name, e.g. "[clearwater] Local Search". GA4: one property per site.
# ======================================================================
SITE_TAG = re.compile(r"\[([a-z0-9-]+)\]")


class MarketingChannels(Connector):
    folder, file = "marketing", "channel_performance"
    columns = ["site_slug", "month", "utm_source", "utm_medium", "utm_campaign", "cost", "sessions",
               "form_submits", "appts_booked"]

    def __init__(self):
        self.rows = defaultdict(lambda: {"cost": 0.0, "sessions": 0, "form_submits": 0, "appts_booked": 0,
                                         "utm_campaign": "(not set)"})

    def _add(self, site, month, source, medium, **vals):
        row = self.rows[(site, month, source, medium)]
        for k, v in vals.items():
            row[k] = row[k] + v if isinstance(v, (int, float)) else v

    def _google_ads(self, since):
        from google.ads.googleads.client import GoogleAdsClient   # pip install google-ads
        client = GoogleAdsClient.load_from_env()                  # GOOGLE_ADS_* env vars
        svc = client.get_service("GoogleAdsService")
        query = f"""SELECT campaign.name, segments.month, metrics.cost_micros
                    FROM campaign WHERE segments.date >= '{since.isoformat()}'"""
        for batch in svc.search_stream(customer_id=env("GOOGLE_ADS_CUSTOMER_ID"), query=query):
            for r in batch.results:
                m = SITE_TAG.search(r.campaign.name)
                if m:
                    self._add(m.group(1), r.segments.month, "google", "cpc", cost=r.metrics.cost_micros / 1e6)

    def _meta(self, since):
        url = f"https://graph.facebook.com/{env('META_API_VERSION', 'v21.0')}/act_{env('META_AD_ACCOUNT_ID')}/insights"
        params = {"access_token": env("META_ACCESS_TOKEN"), "level": "campaign", "time_increment": "monthly",
                  "fields": "campaign_name,spend,date_start", "limit": 500,
                  "time_range": f'{{"since":"{since.isoformat()}","until":"{dt.date.today().isoformat()}"}}'}
        while url:
            r = requests.get(url, params=params, timeout=60)
            r.raise_for_status()
            body = r.json()
            for row in body.get("data", []):
                m = SITE_TAG.search(row.get("campaign_name", ""))
                if m:
                    self._add(m.group(1), row["date_start"][:7] + "-01", "facebook", "paid_social",
                              cost=float(row.get("spend", 0)))
            url, params = body.get("paging", {}).get("next"), None

    def _ga4(self, since):
        from google.analytics.data_v1beta import BetaAnalyticsDataClient   # pip install google-analytics-data
        from google.analytics.data_v1beta.types import DateRange, Dimension, Metric, RunReportRequest
        client = BetaAnalyticsDataClient()     # GOOGLE_APPLICATION_CREDENTIALS
        form_event = env("GA4_FORM_EVENT", "generate_lead")
        booked_event = env("GA4_BOOKED_EVENT", "appointment_booked")
        for site, prop in env_map("GA4_PROPERTIES").items():
            resp = client.run_report(RunReportRequest(
                property=f"properties/{prop}",
                dimensions=[Dimension(name="yearMonth"), Dimension(name="sessionSource"),
                            Dimension(name="sessionMedium"), Dimension(name="eventName")],
                metrics=[Metric(name="sessions"), Metric(name="eventCount")],
                date_ranges=[DateRange(start_date=since.isoformat(), end_date="today")], limit=100000))
            for r in resp.rows:
                ym, src, med, event = (v.value for v in r.dimension_values)
                sessions, count = int(r.metric_values[0].value), int(r.metric_values[1].value)
                month = f"{ym[:4]}-{ym[4:]}-01"
                vals = {"sessions": sessions if event == "session_start" else 0,
                        "form_submits": count if event == form_event else 0,
                        "appts_booked": count if event == booked_event else 0}
                self._add(site, month, src, med, **vals)

    def extract(self, since):
        self._google_ads(since)
        self._meta(since)
        self._ga4(since)
        seo = float(env("SEO_MONTHLY_RETAINER_PER_SITE", "0", required=False) or 0)
        for (site, month, src, med), vals in sorted(self.rows.items()):
            if src == "google" and med == "organic" and seo:
                vals["cost"] += seo
            yield {"site_slug": site, "month": month, "utm_source": src, "utm_medium": med, **vals}


BUSINESS_CONNECTORS = [SageGLDetail, UKGTimecardsReport, InventoryUsage, MarketingChannels]
