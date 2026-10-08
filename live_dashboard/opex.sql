WITH base AS (SELECT location_key, month, account_no, account_title, category, source, amount
              FROM `marts.mart_opex_monthly` WHERE location_key < 99),
first_m AS (SELECT MIN(month) AS m0, MAX(month) AS m1 FROM base),
acct AS (SELECT account_no, source, ANY_VALUE(account_title) AS title, ANY_VALUE(category) AS category,
                ROW_NUMBER() OVER (ORDER BY account_no, source) - 1 AS i
         FROM base GROUP BY account_no, source),
o AS (SELECT b.location_key AS k, DATE_DIFF(b.month, f.m0, MONTH) AS mi, a.i, CAST(ROUND(b.amount) AS INT64) AS amt
      FROM base b CROSS JOIN first_m f JOIN acct a USING (account_no, source)
      WHERE DIV(DATE_DIFF(f.m1, b.month, MONTH), 6) = __CHUNK__)
SELECT TO_JSON_STRING(STRUCT(
  (SELECT FORMAT_DATE('%Y-%m', m0) FROM first_m) AS first_month,
  (SELECT ARRAY_AGG(FORMAT('%s|%s|%s|%s', account_no, title, category, source) ORDER BY i) FROM acct) AS accounts,
  ARRAY_AGG(k ORDER BY mi, k, i) AS k, ARRAY_AGG(mi ORDER BY mi, k, i) AS m,
  ARRAY_AGG(i ORDER BY mi, k, i) AS i, ARRAY_AGG(amt ORDER BY mi, k, i) AS amt)) AS j
FROM o
