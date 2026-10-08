with unioned as (
    select 'open_dental' as source_system, clinic_num as source_location, cast(pay_date as date) as paid_date,
           case pay_type when 'Insurance' then 'Insurance' else 'Patient' end as payer, {{ num('pay_amt') }} as amount
    from {{ source('raw', 'pms_open_dental__payments') }}
    union all
    select 'dentrix_ascend', location_id, cast(substr(transaction_date, 1, 10) as date),
           case transaction_type when 'INSURANCE_PAYMENT' then 'Insurance' else 'Patient' end, {{ num('amount') }}
    from {{ source('raw', 'pms_dentrix_ascend__payments') }}
    union all
    select 'sensei', practice, {{ parse_date('date_col', '%d-%b-%Y') }},
           case transaction_type when 'Insurance Payment' then 'Insurance' else 'Patient' end, {{ num('amount') }}
    from {{ source('raw', 'pms_sensei__payments') }}
    union all
    select 'dolphin', office_code, {{ parse_date('posted', '%m/%d/%Y') }},
           case source when 'INS' then 'Insurance' else 'Patient' end, {{ num('amount') }}
    from {{ source('raw', 'pms_dolphin__payments') }}
    union all
    select 'tdo', office, {{ parse_date('posted_date', '%Y%m%d') }},
           case payer_type when 'Ins' then 'Insurance' else 'Patient' end, {{ num('amount') }}
    from {{ source('raw', 'pms_tdo__payments') }}
    union all
    select 'dentrix', clinic_id, cast(substr(trans_date, 1, 10) as date),
           case trans_type when 'InsPayment' then 'Insurance' else 'Patient' end, {{ num('amount') }}
    from {{ source('raw', 'pms_dentrix__payments') }}
    union all
    select 'dox', office, {{ parse_date('pmt_date', '%m-%d-%Y') }},
           case pmt_source when 'Insurance' then 'Insurance' else 'Patient' end, {{ num('amount') }}
    from {{ source('raw', 'pms_dox__payments') }}
)
select x.location_key, u.paid_date, {{ month_of('u.paid_date') }} as month, u.payer, u.amount
from unioned u
join {{ ref('location_crosswalk') }} x on x.source_system = u.source_system and x.source_location = u.source_location
