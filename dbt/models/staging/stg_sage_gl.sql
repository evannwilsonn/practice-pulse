-- Sage Intacct: account numbers -> categories; TR_TYPE sign applied
with g as (
    select g.*,
           -- Intacct returns MM/DD/YYYY over the API; ISO dates are accepted too
           case when g.entry_date like '__/__/____' then {{ parse_date('g.entry_date', '%m/%d/%Y') }}
                else cast(g.entry_date as date) end as entry_dt
    from {{ source('raw', 'sage_intacct__gl_detail') }} g
)
select x.location_key, {{ month_of('g.entry_dt') }} as month,
       g.accountno as account_no, g.accounttitle as account_title, g.departmentid as department,
       coalesce(a.category, 'Unmapped account') as category, a.is_opex, a.mart_source,
       -- debits positive for expenses; revenue (credits) flipped positive
       {{ num('g.amount') }} * {{ int('g.tr_type') }} * case when a.category = 'Revenue' then -1 else 1 end as amount
from g
join {{ ref('location_crosswalk') }} x on x.source_system = 'sage_intacct' and x.source_location = g.locationid
left join {{ ref('gl_account_map') }} a on a.account_no = g.accountno
