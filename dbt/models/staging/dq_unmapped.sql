-- Data quality: anything a mapping table doesn't recognize (should be empty)
with src as (
    select 'open_dental' as source_system, clinic_num as source_location from {{ source('raw', 'pms_open_dental__procedures') }}
    union all select 'dentrix_ascend', location_id from {{ source('raw', 'pms_dentrix_ascend__procedures') }}
    union all select 'sensei', practice from {{ source('raw', 'pms_sensei__procedures') }}
    union all select 'dolphin', office_code from {{ source('raw', 'pms_dolphin__procedures') }}
    union all select 'tdo', office from {{ source('raw', 'pms_tdo__procedures') }}
    union all select 'dentrix', clinic_id from {{ source('raw', 'pms_dentrix__procedures') }}
    union all select 'dox', office from {{ source('raw', 'pms_dox__procedures') }}
    union all select 'ukg', org_level1 from {{ source('raw', 'ukg__timecards') }}
    union all select 'sage_intacct', locationid from {{ source('raw', 'sage_intacct__gl_detail') }}
    union all select 'inventory', site_code from {{ source('raw', 'inventory__usage') }}
    union all select 'marketing', site_slug from {{ source('raw', 'marketing__channel_performance') }}
)
select 'location' as kind, s.source_system || ' / ' || s.source_location as value, count(*) as row_count
from src s
left join {{ ref('location_crosswalk') }} x on x.source_system = s.source_system and x.source_location = s.source_location
where x.location_key is null group by 1, 2
union all select 'cdt_code', cdt_code, count(*) from {{ ref('stg_pms_procedures') }} where procedure_category = 'Unmapped code' group by 1, 2
union all select 'gl_account', account_no, count(*) from {{ ref('stg_sage_gl') }} where category = 'Unmapped account' group by 1, 2
union all select 'ukg_job', job_code, count(*) from {{ ref('stg_ukg_labor') }} where role = 'Unmapped job' group by 1, 2
union all select 'inventory_item', item_number, count(*) from {{ ref('stg_inventory') }} where category = 'Unmapped category' group by 1, 2
union all select 'utm_campaign', campaign, count(*) from {{ ref('stg_marketing') }} where channel = 'Other' group by 1, 2
