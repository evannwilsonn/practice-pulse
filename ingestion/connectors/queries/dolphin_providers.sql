-- Dolphin Management -> providers landing file. TODO: map table/column names.
-- (the ? since parameter is accepted but unused)
SELECT d.provider_code AS provider_code, o.office_code AS office_code, d.credential AS credential
FROM doctors d JOIN offices o ON o.office_id = d.office_id   -- TODO
WHERE ? IS NOT NULL
