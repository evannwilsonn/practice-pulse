-- Dentrix G-series -> payments landing file. TODO: map DDP view/column names.
SELECT t.clinic_id AS ClinicID, CONVERT(varchar(23), t.trans_date, 121) AS TransDate,
       CASE WHEN t.is_insurance = 1 THEN 'InsPayment' ELSE 'PatPayment' END AS TransType,   -- TODO
       t.amount AS Amount
FROM v_payments t                                   -- TODO
WHERE t.trans_date >= ?
