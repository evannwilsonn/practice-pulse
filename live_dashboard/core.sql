WITH
loc AS (SELECT location_key, location_name, region, specialty, pms_system FROM `ref.dim_location` WHERE location_key < 99),
m AS (SELECT * FROM `marts.mart_location_monthly` WHERE location_key < 99),
src AS (
  SELECT CASE WHEN table_id LIKE 'pms_%procedures' THEN 'Practice management'
              WHEN table_id = 'sage_intacct__gl_detail' THEN 'Sage Intacct'
              WHEN table_id = 'ukg__timecards' THEN 'UKG'
              WHEN table_id = 'inventory__usage' THEN 'Inventory'
              WHEN table_id IN ('marketing__channel_performance', 'windsor__facebook_ads') THEN 'Marketing / websites' END AS source,
         row_count
  FROM `raw.__TABLES__`)
SELECT TO_JSON_STRING(STRUCT(
  (SELECT ARRAY_AGG(l ORDER BY location_key) FROM loc l) AS locations,
  (SELECT AS STRUCT
     ARRAY_AGG(FORMAT_DATE('%Y-%m', month) ORDER BY month, location_key) AS month,
     ARRAY_AGG(location_key ORDER BY month, location_key) AS location_key,
     ARRAY_AGG(ROUND(CAST(gross_production AS FLOAT64), 2) ORDER BY month, location_key) AS gross_production,
     ARRAY_AGG(ROUND(CAST(net_production AS FLOAT64), 2) ORDER BY month, location_key) AS net_production,
     ARRAY_AGG(ROUND(CAST(collections AS FLOAT64), 2) ORDER BY month, location_key) AS collections,
     ARRAY_AGG(completed_visits ORDER BY month, location_key) AS completed_visits,
     ARRAY_AGG(no_shows ORDER BY month, location_key) AS no_shows,
     ARRAY_AGG(scheduled ORDER BY month, location_key) AS scheduled,
     ARRAY_AGG(new_patients ORDER BY month, location_key) AS new_patients,
     ARRAY_AGG(ROUND(CAST(labor_cost AS FLOAT64), 2) ORDER BY month, location_key) AS labor_cost,
     ARRAY_AGG(ROUND(CAST(labor_hours AS FLOAT64), 1) ORDER BY month, location_key) AS labor_hours,
     ARRAY_AGG(ROUND(CAST(overtime_hours AS FLOAT64), 1) ORDER BY month, location_key) AS overtime_hours,
     ARRAY_AGG(ROUND(CAST(supply_cost AS FLOAT64), 2) ORDER BY month, location_key) AS supply_cost,
     ARRAY_AGG(ROUND(CAST(marketing_spend AS FLOAT64), 2) ORDER BY month, location_key) AS marketing_spend,
     ARRAY_AGG(ROUND(CAST(total_opex AS FLOAT64), 2) ORDER BY month, location_key) AS total_opex,
     ARRAY_AGG(ROUND(CAST(operating_profit AS FLOAT64), 2) ORDER BY month, location_key) AS operating_profit
   FROM m) AS monthly,
  (SELECT ARRAY_AGG(STRUCT(source, n) ORDER BY ord) FROM (
     SELECT source, SUM(row_count) AS n,
            CASE source WHEN 'Practice management' THEN 1 WHEN 'Sage Intacct' THEN 2 WHEN 'UKG' THEN 3 WHEN 'Inventory' THEN 4 ELSE 5 END AS ord
     FROM src WHERE source IS NOT NULL GROUP BY source)) AS sources,
  (SELECT COUNT(*) FROM `staging.dq_unmapped`) AS unmapped
)) AS j
