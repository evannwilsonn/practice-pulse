-- =====================================================================
-- Marts: cross-system tables the dashboards read (Streamlit, Domo, or
-- the HTML preview). Each figure comes from its system of record; Sage
-- Intacct supplies the costs no operational system holds and is used to
-- reconcile the rest. Portable SQL (transpiled for Snowflake).
-- =====================================================================

-- every operating expense line, each taken from its system of record:
-- staff wages from UKG, dental supplies from inventory, ad spend from the
-- marketing feed, everything else from Sage Intacct
CREATE OR REPLACE TABLE marts.mart_opex_monthly AS
WITH lines AS (
    SELECT location_key, month, account_no, 'Sage Intacct' AS source, amount
    FROM staging.stg_sage_gl WHERE is_opex AND mart_source = 'gl'
    UNION ALL SELECT location_key, month, gl_account_no, 'UKG', labor_cost FROM staging.stg_ukg_labor
    UNION ALL SELECT location_key, month, '5300', 'Inventory', supply_cost FROM staging.stg_inventory
    UNION ALL SELECT location_key, month, '6600', 'Marketing feed', spend FROM staging.stg_marketing
)
SELECT l.location_key, l.month, a.category, l.account_no, a.account_title, l.source, SUM(l.amount) AS amount
FROM lines l
JOIN ref.gl_account_map a ON a.account_no = l.account_no
GROUP BY l.location_key, l.month, a.category, l.account_no, a.account_title, l.source;

CREATE OR REPLACE TABLE marts.mart_location_monthly AS
WITH appts AS (
    SELECT location_key, month,
           SUM(gross_production) AS gross_production,
           SUM(net_production) AS net_production,
           SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) AS completed_visits,
           SUM(CASE WHEN status = 'no_show' THEN 1 ELSE 0 END) AS no_shows,
           COUNT(*) AS scheduled,
           SUM(CASE WHEN is_new_patient AND status = 'completed' THEN 1 ELSE 0 END) AS new_patients,
           SUM(CASE WHEN provider_type = 'Hygienist' THEN gross_production ELSE 0 END) AS hygiene_production
    FROM staging.stg_pms_appointments GROUP BY location_key, month
), pay AS (
    SELECT location_key, month, SUM(amount) AS collections,
           SUM(CASE WHEN payer = 'Insurance' THEN amount ELSE 0 END) AS insurance_collections
    FROM staging.stg_pms_payments GROUP BY location_key, month
), labor AS (
    SELECT location_key, month,
           SUM(labor_cost) AS labor_cost,
           SUM(CASE WHEN is_overtime THEN labor_cost ELSE 0 END) AS overtime_cost,
           SUM(CASE WHEN is_productive THEN hours ELSE 0 END) AS labor_hours,
           SUM(CASE WHEN is_overtime THEN hours ELSE 0 END) AS overtime_hours
    FROM staging.stg_ukg_labor GROUP BY location_key, month
), opex AS (
    SELECT location_key, month,
           SUM(amount) AS total_opex,
           SUM(CASE WHEN category = 'Doctor Compensation' THEN amount ELSE 0 END) AS doctor_comp,
           SUM(CASE WHEN account_no = '5200' THEN amount ELSE 0 END) AS lab_fees,
           SUM(CASE WHEN account_no IN ('6040', '6050', '6060', '6070', '6080') THEN amount ELSE 0 END) AS payroll_taxes_benefits,
           SUM(CASE WHEN category IN ('Occupancy', 'Utilities', 'Facilities & Maintenance') THEN amount ELSE 0 END) AS facility_costs
    FROM marts.mart_opex_monthly GROUP BY location_key, month
), supplies AS (
    SELECT location_key, month, SUM(supply_cost) AS supply_cost, SUM(on_hand_value) AS inventory_on_hand
    FROM staging.stg_inventory GROUP BY location_key, month
), mkt AS (
    SELECT location_key, month, SUM(spend) AS marketing_spend,
           SUM(form_leads) AS leads, SUM(booked_appts) AS booked_from_marketing
    FROM staging.stg_marketing GROUP BY location_key, month
)
SELECT d.location_key, d.location_name, d.region, d.specialty, d.pms_system, a.month,
       a.gross_production, a.net_production, p.collections, p.insurance_collections,
       a.completed_visits, a.no_shows, a.scheduled, a.new_patients, a.hygiene_production,
       l.labor_cost, l.overtime_cost, l.labor_hours, l.overtime_hours,
       o.doctor_comp, o.lab_fees, o.payroll_taxes_benefits, o.facility_costs, o.total_opex,
       s.supply_cost, s.inventory_on_hand,
       m.marketing_spend, m.leads, m.booked_from_marketing,
       p.collections - COALESCE(o.total_opex, 0) AS operating_profit
FROM appts a
JOIN ref.dim_location d ON d.location_key = a.location_key
LEFT JOIN pay p      ON p.location_key = a.location_key AND p.month = a.month
LEFT JOIN labor l    ON l.location_key = a.location_key AND l.month = a.month
LEFT JOIN opex o     ON o.location_key = a.location_key AND o.month = a.month
LEFT JOIN supplies s ON s.location_key = a.location_key AND s.month = a.month
LEFT JOIN mkt m      ON m.location_key = a.location_key AND m.month = a.month;

-- production by CDT category (diagnostic, preventive, restorative, ortho, endo ...)
CREATE OR REPLACE TABLE marts.mart_procedure_mix AS
SELECT location_key, month, procedure_category, COUNT(*) AS procedures, SUM(gross_production) AS gross_production
FROM staging.stg_pms_procedures
WHERE status = 'completed' AND cdt_code IS NOT NULL
GROUP BY location_key, month, procedure_category;

CREATE OR REPLACE TABLE marts.mart_marketing_channel_monthly AS
SELECT location_key, month, channel, SUM(spend) AS spend, SUM(sessions) AS sessions,
       SUM(form_leads) AS leads, SUM(booked_appts) AS booked
FROM staging.stg_marketing GROUP BY location_key, month, channel;

-- does the GL agree with the operational systems? (variance should be near zero)
CREATE OR REPLACE TABLE marts.mart_reconciliation AS
WITH gl AS (
    SELECT location_key, month,
           CASE mart_source WHEN 'pms' THEN 'Revenue' WHEN 'ukg' THEN 'Staff Wages'
                            WHEN 'inventory' THEN 'Supplies' WHEN 'marketing' THEN 'Marketing' END AS category,
           SUM(amount) AS gl_amount
    FROM staging.stg_sage_gl WHERE mart_source IN ('pms', 'ukg', 'inventory', 'marketing')
    GROUP BY location_key, month, mart_source
), ops AS (
    SELECT location_key, month, 'Revenue' AS category, SUM(amount) AS ops_amount, 'PMS payments' AS ops_source
    FROM staging.stg_pms_payments GROUP BY location_key, month
    UNION ALL SELECT location_key, month, 'Staff Wages', SUM(labor_cost), 'UKG timecards' FROM staging.stg_ukg_labor GROUP BY location_key, month
    UNION ALL SELECT location_key, month, 'Supplies', SUM(supply_cost), 'Inventory usage' FROM staging.stg_inventory GROUP BY location_key, month
    UNION ALL SELECT location_key, month, 'Marketing', SUM(spend), 'Marketing feed' FROM staging.stg_marketing GROUP BY location_key, month
)
SELECT o.location_key, o.month, o.category, o.ops_source, o.ops_amount, g.gl_amount,
       g.gl_amount - o.ops_amount AS variance,
       (g.gl_amount - o.ops_amount) / NULLIF(o.ops_amount, 0) AS variance_pct
FROM ops o
LEFT JOIN gl g ON g.location_key = o.location_key AND g.month = o.month AND g.category = o.category;
