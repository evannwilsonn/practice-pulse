-- the scorecard table must have exactly one row per office per month
select location_key, month, count(*) from {{ ref('mart_location_monthly') }}
group by 1, 2 having count(*) > 1
