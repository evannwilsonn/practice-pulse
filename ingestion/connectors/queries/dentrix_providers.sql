-- Dentrix G-series -> providers landing file. TODO: map DDP view/column names.
SELECT p.prov_id AS ProvID, p.clinic_id AS ClinicID,
       CASE WHEN p.is_hygienist = 1 THEN 'Hygienist' ELSE 'Dentist' END AS ProvType   -- TODO
FROM v_providers p                                  -- TODO
