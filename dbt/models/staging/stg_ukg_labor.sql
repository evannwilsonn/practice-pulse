-- UKG: job codes -> roles, earning codes -> pay multiplier / overtime
select x.location_key, t.employee_number as employee_id, t.job_code,
       coalesce(j.role, 'Unmapped job') as role, j.is_clinical,
       cast(t.work_date as date) as work_date, {{ month_of('cast(t.work_date as date)') }} as month,
       t.earning_code, e.is_productive, e.is_overtime,
       -- the GL account these hours post to (ties UKG to Sage Intacct)
       case when not e.is_productive then '6030' when j.is_clinical then '6000' else '6010' end as gl_account_no,
       {{ num('t.hours') }} as hours,
       {{ num('t.hours') }} * {{ num('t.hourly_rate') }} * e.pay_multiplier as labor_cost
from {{ source('raw', 'ukg__timecards') }} t
join {{ ref('location_crosswalk') }} x on x.source_system = 'ukg' and x.source_location = t.org_level1
left join {{ ref('ukg_job_map') }} j on j.job_code = t.job_code
left join {{ ref('ukg_earning_map') }} e on e.earning_code = t.earning_code
