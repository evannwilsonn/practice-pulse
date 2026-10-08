-- fails if any category's total GL figure drifts more than 1% from its operational source
select category, sum(variance) / nullif(sum(ops_amount), 0) as variance_pct
from {{ ref('mart_reconciliation') }}
group by category
having abs(sum(variance) / nullif(sum(ops_amount), 0)) > 0.01
