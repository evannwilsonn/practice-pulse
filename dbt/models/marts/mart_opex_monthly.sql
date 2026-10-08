-- every operating expense line, each from its system of record:
-- staff wages from UKG, dental supplies from inventory, ad spend from the
-- marketing feed, everything else from Sage Intacct
with lines as (
    select location_key, month, account_no, 'Sage Intacct' as source, amount
    from {{ ref('stg_sage_gl') }} where is_opex and mart_source = 'gl'
    union all select location_key, month, gl_account_no, 'UKG', labor_cost from {{ ref('stg_ukg_labor') }}
    union all select location_key, month, '5300', 'Inventory', supply_cost from {{ ref('stg_inventory') }}
    union all select location_key, month, '6600', 'Marketing feed', spend from {{ ref('stg_marketing') }}
)
select l.location_key, l.month, a.category, l.account_no, a.account_title, l.source, sum(l.amount) as amount
from lines l
join {{ ref('gl_account_map') }} a on a.account_no = l.account_no
group by l.location_key, l.month, a.category, l.account_no, a.account_title, l.source
