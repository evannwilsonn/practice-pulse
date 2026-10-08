-- PMS: seven vendors, seven formats, one shape (one row per procedure line)
with unioned as (
    -- Open Dental (ShortQuery). AptStatus 2 = Complete, 5 = Broken, 3 = Unscheduled list
    select 'open_dental' as source_system, p.clinic_num as source_location,
           'OD-' || p.apt_num as appointment_id, 'OD-' || p.pat_num as patient_id,
           cast(p.proc_date as date) as service_date, p.prov_num as provider_id,
           nullif(p.proc_code, '') as cdt_code, {{ num('p.proc_fee') }} as fee, {{ num('p.write_off') }} as writeoff,
           case p.apt_status when '2' then 'completed' when '5' then 'no_show' when '3' then 'cancelled' end as status,
           case pr.is_secondary when '1' then 'Hygienist' else 'Dentist' end as provider_type
    from {{ source('raw', 'pms_open_dental__procedures') }} p
    left join {{ source('raw', 'pms_open_dental__providers') }} pr
           on pr.prov_num = p.prov_num and pr.clinic_num = p.clinic_num
    union all
    -- Dentrix Ascend (flattened API JSON)
    select 'dentrix_ascend', p.location_id, p.appointment_id, p.patient_id,
           cast(substr(p.procedure_date, 1, 10) as date), p.provider_id,
           nullif(p.ada_code, ''), {{ num('p.fee') }}, {{ num('p.adjustment_total') }},
           case p.appointment_status when 'COMPLETE' then 'completed' when 'BROKEN' then 'no_show' when 'CANCELLED' then 'cancelled' end,
           case pr.provider_type when 'HYGIENIST' then 'Hygienist' else 'Dentist' end
    from {{ source('raw', 'pms_dentrix_ascend__procedures') }} p
    left join {{ source('raw', 'pms_dentrix_ascend__providers') }} pr on pr.provider_id = p.provider_id
    union all
    -- Sensei Cloud (report export, dates like 05-Mar-2025)
    select 'sensei', p.practice, 'SN-' || p.appointment_no, 'SN-' || p.patient_no,
           {{ parse_date('p.date_of_service', '%d-%b-%Y') }}, p.provider,
           nullif(p.procedure, ''), {{ num('p.charge') }}, {{ num('p.adj') }},
           case p.appt_status when 'Completed' then 'completed' when 'No Show' then 'no_show' when 'Canceled' then 'cancelled' end,
           case pr.provider_type when 'Hygienist' then 'Hygienist' else 'Dentist' end
    from {{ source('raw', 'pms_sensei__procedures') }} p
    left join {{ source('raw', 'pms_sensei__providers') }} pr on pr.practice = p.practice and pr.provider = p.provider
    union all
    -- Dolphin Management (SQL extract), orthodontics
    select 'dolphin', p.office_code, p.visit_id, p.patient_ref,
           {{ parse_date('p.service_date', '%m/%d/%Y') }}, p.provider_code,
           nullif(p.ada_code, ''), {{ num('p.fee_usd') }}, {{ num('p.contractual_adj') }},
           case p.status when 'C' then 'completed' when 'NS' then 'no_show' when 'X' then 'cancelled' end,
           'Dentist'
    from {{ source('raw', 'pms_dolphin__procedures') }} p
    union all
    -- TDO (report export), endodontics
    select 'tdo', p.office, 'TDO-' || p.visit_id, 'TDO-' || p.chart_no,
           {{ parse_date('p.visit_date', '%Y%m%d') }}, p.doctor,
           nullif(p.cdt, ''), {{ num('p.gross') }}, {{ num('p.adjustment') }},
           case p.status when 'Seen' then 'completed' when 'No-Show' then 'no_show' when 'Cancelled' then 'cancelled' end,
           'Dentist'
    from {{ source('raw', 'pms_tdo__procedures') }} p
    union all
    -- Dentrix G-series (read-only SQL extract; SQL Server datetimes)
    select 'dentrix', p.clinic_id, 'DX-' || p.appt_id, 'DX-' || p.pat_guid,
           cast(substr(p.proc_date, 1, 10) as date), p.prov_id,
           nullif(p.adacode, ''), {{ num('p.amt') }}, {{ num('p.adj_amt') }},
           case p.appt_status when 'C' then 'completed' when 'B' then 'no_show' when 'D' then 'cancelled' end,
           case pr.prov_type when 'Hygienist' then 'Hygienist' else 'Dentist' end
    from {{ source('raw', 'pms_dentrix__procedures') }} p
    left join {{ source('raw', 'pms_dentrix__providers') }} pr on pr.prov_id = p.prov_id and pr.clinic_id = p.clinic_id
    union all
    -- Dental Office Xpress (report export)
    select 'dox', p.office, 'DOX-' || p.appt_no, 'DOX-' || p.acct_no,
           {{ parse_date('p.svc_date', '%m-%d-%Y') }}, p.provider,
           nullif(p.code, ''), {{ num('p.fee') }}, {{ num('p.discount') }},
           case p.appt_result when 'Done' then 'completed' when 'Missed' then 'no_show' when 'Canc' then 'cancelled' end,
           case pr.type when 'RDH' then 'Hygienist' else 'Dentist' end
    from {{ source('raw', 'pms_dox__procedures') }} p
    left join {{ source('raw', 'pms_dox__providers') }} pr on pr.office = p.office and pr.provider = p.provider
)
select x.location_key, u.source_system as pms_system, u.appointment_id,
       -- patient IDs are hashed so no raw patient identifier reaches the marts
       {{ dbt.hash("u.source_system || u.patient_id") }} as patient_key,
       u.service_date, {{ month_of('u.service_date') }} as month,
       u.provider_type, u.status, u.cdt_code,
       case when u.cdt_code is null then null else coalesce(c.category, 'Unmapped code') end as procedure_category,
       coalesce(c.is_new_patient_code, false) as is_new_patient_code,
       u.fee as gross_production, u.writeoff as adjustments, u.fee - u.writeoff as net_production
from unioned u
join {{ ref('location_crosswalk') }} x on x.source_system = u.source_system and x.source_location = u.source_location
left join {{ ref('cdt_procedure_map') }} c on c.cdt_code = u.cdt_code
