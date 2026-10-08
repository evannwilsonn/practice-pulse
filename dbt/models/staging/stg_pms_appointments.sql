-- one row per appointment; new patient = a completed new-patient code (D0150, D8660, D9310)
select location_key, pms_system, appointment_id, patient_key, service_date, month,
       max(provider_type) as provider_type, max(status) as status,
       max(case when is_new_patient_code then 1 else 0 end) = 1 as is_new_patient,
       sum(gross_production) as gross_production, sum(adjustments) as adjustments,
       sum(net_production) as net_production
from {{ ref('stg_pms_procedures') }}
group by location_key, pms_system, appointment_id, patient_key, service_date, month
