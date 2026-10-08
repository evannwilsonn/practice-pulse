WITH w AS (SELECT * FROM `marts.mart_location_weekly` WHERE location_key < 99),
last_full AS (SELECT DATE_SUB(DATE_TRUNC(DATE_ADD(MAX(service_date), INTERVAL 1 DAY), WEEK(MONDAY)), INTERVAL 7 DAY) AS wk
              FROM `staging.stg_pms_appointments`),
pick AS (SELECT wk AS week FROM last_full UNION ALL SELECT DATE_SUB(wk, INTERVAL 7 DAY) FROM last_full UNION ALL SELECT DATE_SUB(wk, INTERVAL 52 WEEK) FROM last_full),
x AS (SELECT w.* FROM w JOIN pick USING (week))
SELECT TO_JSON_STRING(STRUCT(
  ARRAY_AGG(FORMAT_DATE('%Y-%m-%d', week) ORDER BY week, location_key) AS week,
  ARRAY_AGG(location_key ORDER BY week, location_key) AS location_key,
  ARRAY_AGG(ROUND(CAST(gross_production AS FLOAT64), 2) ORDER BY week, location_key) AS gross_production,
  ARRAY_AGG(ROUND(CAST(net_production AS FLOAT64), 2) ORDER BY week, location_key) AS net_production,
  ARRAY_AGG(ROUND(CAST(IFNULL(collections, 0) AS FLOAT64), 2) ORDER BY week, location_key) AS collections,
  ARRAY_AGG(completed_visits ORDER BY week, location_key) AS completed_visits,
  ARRAY_AGG(no_shows ORDER BY week, location_key) AS no_shows,
  ARRAY_AGG(scheduled ORDER BY week, location_key) AS scheduled,
  ARRAY_AGG(new_patients ORDER BY week, location_key) AS new_patients,
  ARRAY_AGG(ROUND(CAST(IFNULL(labor_cost, 0) AS FLOAT64), 2) ORDER BY week, location_key) AS labor_cost,
  ARRAY_AGG(ROUND(CAST(IFNULL(labor_hours, 0) AS FLOAT64), 1) ORDER BY week, location_key) AS labor_hours,
  ARRAY_AGG(ROUND(CAST(IFNULL(overtime_hours, 0) AS FLOAT64), 1) ORDER BY week, location_key) AS overtime_hours
)) AS j FROM x
