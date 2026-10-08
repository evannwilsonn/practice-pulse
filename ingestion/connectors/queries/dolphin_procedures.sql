-- Dolphin Management (on-prem SQL Server) -> procedures landing file.
-- TODO: Dolphin's schema is not publicly documented. Map the table and
-- column names below with Dolphin support or by inspecting the database
-- with a read-only login. The output column names must stay as written.
-- The single ? parameter is the "since" date.
SELECT
    o.office_code            AS office_code,       -- TODO office / location table
    v.visit_id               AS visit_id,          -- TODO appointment / visit key
    p.patient_id             AS patient_ref,
    CONVERT(varchar(10), v.visit_date, 101) AS service_date,   -- MM/DD/YYYY
    v.provider_code          AS provider_code,
    t.ada_code               AS ada_code,          -- CDT code (D8080, D8670, ...)
    t.fee                    AS fee_usd,
    t.adjustment             AS contractual_adj,
    CASE v.status WHEN 'kept' THEN 'C' WHEN 'missed' THEN 'NS' ELSE 'X' END AS status   -- TODO status values
FROM visits v                                       -- TODO
JOIN offices o ON o.office_id = v.office_id         -- TODO
JOIN patients p ON p.patient_id = v.patient_id      -- TODO
LEFT JOIN transactions t ON t.visit_id = v.visit_id -- TODO
WHERE v.visit_date >= ?
