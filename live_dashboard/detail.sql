WITH
ch AS (SELECT * FROM `marts.mart_marketing_channel_monthly` WHERE location_key < 99),
mx AS (SELECT * FROM `marts.mart_procedure_mix` WHERE location_key < 99),
rc AS (SELECT * FROM `marts.mart_reconciliation` WHERE location_key < 99)
SELECT TO_JSON_STRING(STRUCT(
  (SELECT AS STRUCT
     ARRAY_AGG(location_key ORDER BY month, location_key, channel) AS location_key,
     ARRAY_AGG(FORMAT_DATE('%Y-%m', month) ORDER BY month, location_key, channel) AS month,
     ARRAY_AGG(channel ORDER BY month, location_key, channel) AS channel,
     ARRAY_AGG(ROUND(CAST(spend AS FLOAT64), 2) ORDER BY month, location_key, channel) AS spend,
     ARRAY_AGG(leads ORDER BY month, location_key, channel) AS leads,
     ARRAY_AGG(booked ORDER BY month, location_key, channel) AS booked
   FROM ch) AS channels,
  (SELECT AS STRUCT
     ARRAY_AGG(location_key ORDER BY month, location_key, procedure_category) AS location_key,
     ARRAY_AGG(FORMAT_DATE('%Y-%m', month) ORDER BY month, location_key, procedure_category) AS month,
     ARRAY_AGG(procedure_category ORDER BY month, location_key, procedure_category) AS cat,
     ARRAY_AGG(ROUND(CAST(gross_production AS FLOAT64), 0) ORDER BY month, location_key, procedure_category) AS prod
   FROM mx) AS mix,
  (SELECT AS STRUCT
     ARRAY_AGG(location_key ORDER BY month, location_key, category) AS location_key,
     ARRAY_AGG(FORMAT_DATE('%Y-%m', month) ORDER BY month, location_key, category) AS month,
     ARRAY_AGG(category ORDER BY month, location_key, category) AS category,
     ARRAY_AGG(ops_source ORDER BY month, location_key, category) AS ops_source,
     ARRAY_AGG(ROUND(CAST(IFNULL(ops_amount, 0) AS FLOAT64), 2) ORDER BY month, location_key, category) AS ops_amount,
     ARRAY_AGG(ROUND(CAST(IFNULL(gl_amount, 0) AS FLOAT64), 2) ORDER BY month, location_key, category) AS gl_amount
   FROM rc) AS recon
)) AS j
