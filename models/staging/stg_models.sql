-- =====================================================================
-- Staging: translate each system's native codes into shared categories
-- and tie every row to a master location_key.
-- Written in portable SQL; snowflake/build_sql.py transpiles this file
-- for Snowflake, so avoid DuckDB-only syntax here.
-- =====================================================================

-- ---------------------------------------------------------------------
-- PMS: five vendors, five formats, one shape
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW staging.stg_pms_procedures AS
WITH unioned AS (
    -- Open Dental (ShortQuery result). AptStatus 2 = Complete, 5 = Broken, 3 = Unscheduled list
    SELECT 'open_dental' AS source_system, p.clinic_num AS source_location,
           'OD-' || p.apt_num AS appointment_id, 'OD-' || p.pat_num AS patient_id,
           CAST(p.proc_date AS DATE) AS service_date, p.prov_num AS provider_id,
           NULLIF(p.proc_code, '') AS cdt_code, CAST(p.proc_fee AS DOUBLE) AS fee, CAST(p.write_off AS DOUBLE) AS writeoff,
           CASE p.apt_status WHEN '2' THEN 'completed' WHEN '5' THEN 'no_show' WHEN '3' THEN 'cancelled' END AS status,
           CASE pr.is_secondary WHEN '1' THEN 'Hygienist' ELSE 'Dentist' END AS provider_type
    FROM raw.pms_open_dental__procedures p
    LEFT JOIN raw.pms_open_dental__providers pr ON pr.prov_num = p.prov_num AND pr.clinic_num = p.clinic_num
    UNION ALL
    -- Dentrix Ascend (flattened API JSON)
    SELECT 'dentrix_ascend', p.location_id, p.appointment_id, p.patient_id,
           CAST(SUBSTR(p.procedure_date, 1, 10) AS DATE), p.provider_id,
           NULLIF(p.ada_code, ''), CAST(p.fee AS DOUBLE), CAST(p.adjustment_total AS DOUBLE),
           CASE p.appointment_status WHEN 'COMPLETE' THEN 'completed' WHEN 'BROKEN' THEN 'no_show' WHEN 'CANCELLED' THEN 'cancelled' END,
           CASE pr.provider_type WHEN 'HYGIENIST' THEN 'Hygienist' ELSE 'Dentist' END
    FROM raw.pms_dentrix_ascend__procedures p
    LEFT JOIN raw.pms_dentrix_ascend__providers pr ON pr.provider_id = p.provider_id
    UNION ALL
    -- Sensei Cloud (report export)
    SELECT 'sensei', p.practice, 'SN-' || p.appointment_no, 'SN-' || p.patient_no,
           CAST(strptime(p.date_of_service, '%d-%b-%Y') AS DATE), p.provider,
           NULLIF(p.procedure, ''), CAST(p.charge AS DOUBLE), CAST(p.adj AS DOUBLE),
           CASE p.appt_status WHEN 'Completed' THEN 'completed' WHEN 'No Show' THEN 'no_show' WHEN 'Canceled' THEN 'cancelled' END,
           CASE pr.provider_type WHEN 'Hygienist' THEN 'Hygienist' ELSE 'Dentist' END
    FROM raw.pms_sensei__procedures p
    LEFT JOIN raw.pms_sensei__providers pr ON pr.practice = p.practice AND pr.provider = p.provider
    UNION ALL
    -- Dolphin Management (SQL extract) - orthodontics
    SELECT 'dolphin', p.office_code, p.visit_id, p.patient_ref,
           CAST(strptime(p.service_date, '%m/%d/%Y') AS DATE), p.provider_code,
           NULLIF(p.ada_code, ''), CAST(p.fee_usd AS DOUBLE), CAST(p.contractual_adj AS DOUBLE),
           CASE p.status WHEN 'C' THEN 'completed' WHEN 'NS' THEN 'no_show' WHEN 'X' THEN 'cancelled' END,
           'Dentist'
    FROM raw.pms_dolphin__procedures p
    UNION ALL
    -- TDO (report export) - endodontics
    SELECT 'tdo', p.office, 'TDO-' || p.visit_id, 'TDO-' || p.chart_no,
           CAST(strptime(p.visit_date, '%Y%m%d') AS DATE), p.doctor,
           NULLIF(p.cdt, ''), CAST(p.gross AS DOUBLE), CAST(p.adjustment AS DOUBLE),
           CASE p.status WHEN 'Seen' THEN 'completed' WHEN 'No-Show' THEN 'no_show' WHEN 'Cancelled' THEN 'cancelled' END,
           'Dentist'
    FROM raw.pms_tdo__procedures p
    UNION ALL
    -- Dentrix G-series (read-only SQL extract; SQL Server datetimes)
    SELECT 'dentrix', p.clinic_id, 'DX-' || p.appt_id, 'DX-' || p.pat_guid,
           CAST(SUBSTR(p.proc_date, 1, 10) AS DATE), p.prov_id,
           NULLIF(p.adacode, ''), CAST(p.amt AS DOUBLE), CAST(p.adj_amt AS DOUBLE),
           CASE p.appt_status WHEN 'C' THEN 'completed' WHEN 'B' THEN 'no_show' WHEN 'D' THEN 'cancelled' END,
           CASE pr.prov_type WHEN 'Hygienist' THEN 'Hygienist' ELSE 'Dentist' END
    FROM raw.pms_dentrix__procedures p
    LEFT JOIN raw.pms_dentrix__providers pr ON pr.prov_id = p.prov_id AND pr.clinic_id = p.clinic_id
    UNION ALL
    -- Dental Office Xpress (report export)
    SELECT 'dox', p.office, 'DOX-' || p.appt_no, 'DOX-' || p.acct_no,
           CAST(strptime(p.svc_date, '%m-%d-%Y') AS DATE), p.provider,
           NULLIF(p.code, ''), CAST(p.fee AS DOUBLE), CAST(p.discount AS DOUBLE),
           CASE p.appt_result WHEN 'Done' THEN 'completed' WHEN 'Missed' THEN 'no_show' WHEN 'Canc' THEN 'cancelled' END,
           CASE pr.type WHEN 'RDH' THEN 'Hygienist' ELSE 'Dentist' END
    FROM raw.pms_dox__procedures p
    LEFT JOIN raw.pms_dox__providers pr ON pr.office = p.office AND pr.provider = p.provider
)
SELECT x.location_key, u.source_system AS pms_system, u.appointment_id,
       -- patient IDs are hashed so no raw patient identifier reaches the marts
       md5(u.source_system || u.patient_id) AS patient_key,
       u.service_date, date_trunc('month', u.service_date) AS month,
       u.provider_type, u.status, u.cdt_code,
       CASE WHEN u.cdt_code IS NULL THEN NULL ELSE COALESCE(c.category, 'Unmapped code') END AS procedure_category,
       COALESCE(c.is_new_patient_code, FALSE) AS is_new_patient_code,
       u.fee AS gross_production, u.writeoff AS adjustments, u.fee - u.writeoff AS net_production
FROM unioned u
JOIN ref.location_crosswalk x ON x.source_system = u.source_system AND x.source_location = u.source_location
LEFT JOIN ref.cdt_procedure_map c ON c.cdt_code = u.cdt_code;

-- one row per appointment; new patient = a completed new-patient code (D0150, D8660, D9310)
CREATE OR REPLACE VIEW staging.stg_pms_appointments AS
SELECT location_key, pms_system, appointment_id, patient_key, service_date, month,
       MAX(provider_type) AS provider_type, MAX(status) AS status,
       MAX(CASE WHEN is_new_patient_code THEN 1 ELSE 0 END) = 1 AS is_new_patient,
       SUM(gross_production) AS gross_production, SUM(adjustments) AS adjustments,
       SUM(net_production) AS net_production
FROM staging.stg_pms_procedures
GROUP BY location_key, pms_system, appointment_id, patient_key, service_date, month;

CREATE OR REPLACE VIEW staging.stg_pms_payments AS
WITH unioned AS (
    SELECT 'open_dental' AS source_system, clinic_num AS source_location, CAST(pay_date AS DATE) AS paid_date,
           CASE pay_type WHEN 'Insurance' THEN 'Insurance' ELSE 'Patient' END AS payer, CAST(pay_amt AS DOUBLE) AS amount
    FROM raw.pms_open_dental__payments
    UNION ALL
    SELECT 'dentrix_ascend', location_id, CAST(SUBSTR(transaction_date, 1, 10) AS DATE),
           CASE transaction_type WHEN 'INSURANCE_PAYMENT' THEN 'Insurance' ELSE 'Patient' END, CAST(amount AS DOUBLE)
    FROM raw.pms_dentrix_ascend__payments
    UNION ALL
    SELECT 'sensei', practice, CAST(strptime(date_col, '%d-%b-%Y') AS DATE),
           CASE transaction_type WHEN 'Insurance Payment' THEN 'Insurance' ELSE 'Patient' END, CAST(amount AS DOUBLE)
    FROM raw.pms_sensei__payments
    UNION ALL
    SELECT 'dolphin', office_code, CAST(strptime(posted, '%m/%d/%Y') AS DATE),
           CASE source WHEN 'INS' THEN 'Insurance' ELSE 'Patient' END, CAST(amount AS DOUBLE)
    FROM raw.pms_dolphin__payments
    UNION ALL
    SELECT 'tdo', office, CAST(strptime(posted_date, '%Y%m%d') AS DATE),
           CASE payer_type WHEN 'Ins' THEN 'Insurance' ELSE 'Patient' END, CAST(amount AS DOUBLE)
    FROM raw.pms_tdo__payments
    UNION ALL
    SELECT 'dentrix', clinic_id, CAST(SUBSTR(trans_date, 1, 10) AS DATE),
           CASE trans_type WHEN 'InsPayment' THEN 'Insurance' ELSE 'Patient' END, CAST(amount AS DOUBLE)
    FROM raw.pms_dentrix__payments
    UNION ALL
    SELECT 'dox', office, CAST(strptime(pmt_date, '%m-%d-%Y') AS DATE),
           CASE pmt_source WHEN 'Insurance' THEN 'Insurance' ELSE 'Patient' END, CAST(amount AS DOUBLE)
    FROM raw.pms_dox__payments
)
SELECT x.location_key, u.paid_date, date_trunc('month', u.paid_date) AS month, u.payer, u.amount
FROM unioned u
JOIN ref.location_crosswalk x ON x.source_system = u.source_system AND x.source_location = u.source_location;

-- ---------------------------------------------------------------------
-- UKG: job codes -> roles, earning codes -> pay multiplier / overtime
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW staging.stg_ukg_labor AS
SELECT x.location_key, t.employee_number AS employee_id, t.job_code,
       COALESCE(j.role, 'Unmapped job') AS role, j.is_clinical,
       CAST(t.work_date AS DATE) AS work_date, date_trunc('month', CAST(t.work_date AS DATE)) AS month,
       t.earning_code, e.is_productive, e.is_overtime,
       -- the GL account these hours post to (ties UKG to Sage Intacct)
       CASE WHEN NOT e.is_productive THEN '6030' WHEN j.is_clinical THEN '6000' ELSE '6010' END AS gl_account_no,
       CAST(t.hours AS DOUBLE) AS hours,
       CAST(t.hours AS DOUBLE) * CAST(t.hourly_rate AS DOUBLE) * e.pay_multiplier AS labor_cost
FROM raw.ukg__timecards t
JOIN ref.location_crosswalk x ON x.source_system = 'ukg' AND x.source_location = t.org_level1
LEFT JOIN ref.ukg_job_map j ON j.job_code = t.job_code
LEFT JOIN ref.ukg_earning_map e ON e.earning_code = t.earning_code;

-- ---------------------------------------------------------------------
-- Sage Intacct: account numbers -> categories; TR_TYPE sign applied
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW staging.stg_sage_gl AS
SELECT x.location_key,
       -- Intacct returns MM/DD/YYYY over the API; ISO dates are accepted too
       date_trunc('month', CASE WHEN g.entry_date LIKE '__/__/____' THEN CAST(strptime(g.entry_date, '%m/%d/%Y') AS DATE)
                                ELSE CAST(g.entry_date AS DATE) END) AS month,
       g.accountno AS account_no, g.accounttitle AS account_title, g.departmentid AS department,
       COALESCE(a.category, 'Unmapped account') AS category, a.is_opex, a.mart_source,
       -- debits positive for expenses; revenue (credits) flipped positive
       CAST(g.amount AS DOUBLE) * CAST(g.tr_type AS INTEGER) * CASE WHEN a.category = 'Revenue' THEN -1 ELSE 1 END AS amount
FROM raw.sage_intacct__gl_detail g
JOIN ref.location_crosswalk x ON x.source_system = 'sage_intacct' AND x.source_location = g.locationid
LEFT JOIN ref.gl_account_map a ON a.account_no = g.accountno;

-- ---------------------------------------------------------------------
-- Inventory: vendor categories -> shared supply categories
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW staging.stg_inventory AS
SELECT x.location_key, CAST(strptime(i.period || '01', '%Y%m%d') AS DATE) AS month, i.item_number,
       i.description, COALESCE(m.category, 'Unmapped category') AS category,
       CAST(i.qty_issued AS DOUBLE) * CAST(i.unit_cost AS DOUBLE) AS supply_cost,
       CAST(i.qty_on_hand AS DOUBLE) * CAST(i.unit_cost AS DOUBLE) AS on_hand_value
FROM raw.inventory__usage i
JOIN ref.location_crosswalk x ON x.source_system = 'inventory' AND x.source_location = i.site_code
LEFT JOIN ref.inventory_category_map m ON m.vendor_category = i.vendor_category;

-- ---------------------------------------------------------------------
-- Marketing: utm_source + utm_medium -> channel
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW staging.stg_marketing AS
SELECT x.location_key, CAST(m.month AS DATE) AS month, COALESCE(c.channel, 'Other') AS channel,
       c.is_paid, m.utm_campaign AS campaign,
       CAST(m.cost AS DOUBLE) AS spend, CAST(m.sessions AS INTEGER) AS sessions,
       CAST(m.form_submits AS INTEGER) AS form_leads, CAST(m.appts_booked AS INTEGER) AS booked_appts
FROM raw.marketing__channel_performance m
JOIN ref.location_crosswalk x ON x.source_system = 'marketing' AND x.source_location = m.site_slug
LEFT JOIN ref.marketing_channel_map c ON c.utm_source = m.utm_source AND c.utm_medium = m.utm_medium;

-- ---------------------------------------------------------------------
-- Data quality: anything a mapping table doesn't recognize
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW staging.dq_unmapped AS
WITH src AS (
    SELECT 'open_dental' AS source_system, clinic_num AS source_location FROM raw.pms_open_dental__procedures
    UNION ALL SELECT 'dentrix_ascend', location_id FROM raw.pms_dentrix_ascend__procedures
    UNION ALL SELECT 'sensei', practice FROM raw.pms_sensei__procedures
    UNION ALL SELECT 'dolphin', office_code FROM raw.pms_dolphin__procedures
    UNION ALL SELECT 'tdo', office FROM raw.pms_tdo__procedures
    UNION ALL SELECT 'dentrix', clinic_id FROM raw.pms_dentrix__procedures
    UNION ALL SELECT 'dox', office FROM raw.pms_dox__procedures
    UNION ALL SELECT 'ukg', org_level1 FROM raw.ukg__timecards
    UNION ALL SELECT 'sage_intacct', locationid FROM raw.sage_intacct__gl_detail
    UNION ALL SELECT 'inventory', site_code FROM raw.inventory__usage
    UNION ALL SELECT 'marketing', site_slug FROM raw.marketing__channel_performance
)
SELECT 'location' AS kind, s.source_system || ' / ' || s.source_location AS value, COUNT(*) AS row_count
FROM src s LEFT JOIN ref.location_crosswalk x ON x.source_system = s.source_system AND x.source_location = s.source_location
WHERE x.location_key IS NULL GROUP BY 1, 2
UNION ALL SELECT 'cdt_code', cdt_code, COUNT(*) FROM staging.stg_pms_procedures WHERE procedure_category = 'Unmapped code' GROUP BY 1, 2
UNION ALL SELECT 'gl_account', account_no, COUNT(*) FROM staging.stg_sage_gl WHERE category = 'Unmapped account' GROUP BY 1, 2
UNION ALL SELECT 'ukg_job', job_code, COUNT(*) FROM staging.stg_ukg_labor WHERE role = 'Unmapped job' GROUP BY 1, 2
UNION ALL SELECT 'inventory_item', item_number, COUNT(*) FROM staging.stg_inventory WHERE category = 'Unmapped category' GROUP BY 1, 2
UNION ALL SELECT 'utm_campaign', campaign, COUNT(*) FROM staging.stg_marketing WHERE channel = 'Other' GROUP BY 1, 2;
