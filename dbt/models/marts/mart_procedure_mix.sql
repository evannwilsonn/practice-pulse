-- production by CDT category (diagnostic, preventive, restorative, ortho, endo ...)
select location_key, month, procedure_category, count(*) as procedures, sum(gross_production) as gross_production
from {{ ref('stg_pms_procedures') }}
where status = 'completed' and cdt_code is not null
group by location_key, month, procedure_category
