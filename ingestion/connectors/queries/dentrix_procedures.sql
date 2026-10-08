-- Dentrix G-series -> procedures landing file.
-- TODO: replace view/column names with the DDP read-only views Dentrix provides.
SELECT c.clinic_id AS ClinicID, pl.appt_id AS ApptID, pl.patient_guid AS PatGUID,
       CONVERT(varchar(23), pl.proc_date, 121) AS ProcDate, pl.prov_id AS ProvID,
       pl.ada_code AS ADACode, pl.amount AS Amt, pl.adjustment_amount AS AdjAmt,
       CASE WHEN pl.chart_status = 102 THEN 'C' WHEN a.broken = 1 THEN 'B' ELSE 'D' END AS ApptStatus   -- TODO
FROM v_proc_log pl                                  -- TODO
JOIN v_clinic c ON c.clinic_id = pl.clinic_id       -- TODO
LEFT JOIN v_appointment a ON a.appt_id = pl.appt_id -- TODO
WHERE pl.proc_date >= ?
