-- Weekly (Monday-start) operating numbers per office, used for week-over-week comparisons.
-- Expenses, supplies and marketing are booked monthly, so they are not in this view.
with appts as (
    select location_key, {{ dbt.date_trunc('week', 'service_date') }} as week,
           sum(gross_production) as gross_production, sum(net_production) as net_production,
           sum(case when status = 'completed' then 1 else 0 end) as completed_visits,
           sum(case when status = 'no_show' then 1 else 0 end) as no_shows,
           count(*) as scheduled,
           sum(case when is_new_patient and status = 'completed' then 1 else 0 end) as new_patients
    from {{ ref('stg_pms_appointments') }} group by 1, 2
), pay as (
    select location_key, {{ dbt.date_trunc('week', 'paid_date') }} as week, sum(amount) as collections
    from {{ ref('stg_pms_payments') }} group by 1, 2
), labor as (
    select location_key, {{ dbt.date_trunc('week', 'work_date') }} as week,
           sum(labor_cost) as labor_cost,
           sum(case when is_productive then hours else 0 end) as labor_hours,
           sum(case when is_overtime then hours else 0 end) as overtime_hours
    from {{ ref('stg_ukg_labor') }} group by 1, 2
)
select a.location_key, a.week, a.gross_production, a.net_production, p.collections,
       a.completed_visits, a.no_shows, a.scheduled, a.new_patients,
       l.labor_cost, l.labor_hours, l.overtime_hours
from appts a
left join pay p on p.location_key = a.location_key and p.week = a.week
left join labor l on l.location_key = a.location_key and l.week = a.week
