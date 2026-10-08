-- Dolphin Management -> payments landing file. TODO: map table/column names.
SELECT o.office_code AS office_code,
       CONVERT(varchar(10), pay.posted_date, 101) AS posted,
       CASE WHEN pay.payer_type = 'insurance' THEN 'INS' ELSE 'PAT' END AS source,   -- TODO
       pay.amount AS amount
FROM payments pay                                   -- TODO
JOIN offices o ON o.office_id = pay.office_id       -- TODO
WHERE pay.posted_date >= ?
