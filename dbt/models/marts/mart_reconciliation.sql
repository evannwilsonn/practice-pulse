-- does the GL agree with the operational systems? (variance should be near zero)
with gl as (
    select location_key, month,
           case mart_source when 'pms' then 'Revenue' when 'ukg' then 'Staff Wages'
                            when 'inventory' then 'Supplies' when 'marketing' then 'Marketing' end as category,
           sum(amount) as gl_amount
    from {{ ref('stg_sage_gl') }} where mart_source in ('pms', 'ukg', 'inventory', 'marketing')
    group by location_key, month, mart_source
), ops as (
    select location_key, month, 'Revenue' as category, sum(amount) as ops_amount, 'PMS payments' as ops_source
    from {{ ref('stg_pms_payments') }} group by location_key, month
    union all select location_key, month, 'Staff Wages', sum(labor_cost), 'UKG timecards' from {{ ref('stg_ukg_labor') }} group by location_key, month
    union all select location_key, month, 'Supplies', sum(supply_cost), 'Inventory usage' from {{ ref('stg_inventory') }} group by location_key, month
    union all select location_key, month, 'Marketing', sum(spend), 'Marketing feed' from {{ ref('stg_marketing') }} group by location_key, month
)
select o.location_key, o.month, o.category, o.ops_source, o.ops_amount, g.gl_amount,
       g.gl_amount - o.ops_amount as variance,
       (g.gl_amount - o.ops_amount) / nullif(o.ops_amount, 0) as variance_pct
from ops o
left join gl g on g.location_key = o.location_key and g.month = o.month and g.category = o.category
