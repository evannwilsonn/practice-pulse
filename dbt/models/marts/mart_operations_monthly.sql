-- Operations page of the practice scorecard: operating expenses by category
-- per office and month, next to that office's collections so each category
-- can be shown as a share of collections and compared across offices.
with opex as (
    select location_key, month, category, sum(amount) as amount
    from {{ ref('mart_opex_monthly') }}
    group by location_key, month, category
), pay as (
    select location_key, month, sum(amount) as collections
    from {{ ref('stg_pms_payments') }}
    group by location_key, month
)
select o.location_key, d.location_name, d.region, d.specialty, o.month, o.category,
       o.amount as opex_amount,
       p.collections,
       o.amount / nullif(p.collections, 0) as pct_of_collections
from opex o
join {{ ref('dim_location') }} d on d.location_key = o.location_key
left join pay p on p.location_key = o.location_key and p.month = o.month
