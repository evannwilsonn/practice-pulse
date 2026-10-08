-- one row per office per month: the practice scorecard's base table
with appts as (
    select location_key, month,
           sum(gross_production) as gross_production,
           sum(net_production) as net_production,
           sum(case when status = 'completed' then 1 else 0 end) as completed_visits,
           sum(case when status = 'no_show' then 1 else 0 end) as no_shows,
           count(*) as scheduled,
           sum(case when is_new_patient and status = 'completed' then 1 else 0 end) as new_patients,
           sum(case when provider_type = 'Hygienist' then gross_production else 0 end) as hygiene_production
    from {{ ref('stg_pms_appointments') }} group by location_key, month
), pay as (
    select location_key, month, sum(amount) as collections,
           sum(case when payer = 'Insurance' then amount else 0 end) as insurance_collections
    from {{ ref('stg_pms_payments') }} group by location_key, month
), labor as (
    select location_key, month,
           sum(labor_cost) as labor_cost,
           sum(case when is_overtime then labor_cost else 0 end) as overtime_cost,
           sum(case when is_productive then hours else 0 end) as labor_hours,
           sum(case when is_overtime then hours else 0 end) as overtime_hours
    from {{ ref('stg_ukg_labor') }} group by location_key, month
), opex as (
    select location_key, month,
           sum(amount) as total_opex,
           sum(case when category = 'Doctor Compensation' then amount else 0 end) as doctor_comp,
           sum(case when account_no = '5200' then amount else 0 end) as lab_fees,
           sum(case when account_no in ('6040', '6050', '6060', '6070', '6080') then amount else 0 end) as payroll_taxes_benefits,
           sum(case when category in ('Occupancy', 'Utilities', 'Facilities & Maintenance') then amount else 0 end) as facility_costs
    from {{ ref('mart_opex_monthly') }} group by location_key, month
), supplies as (
    select location_key, month, sum(supply_cost) as supply_cost, sum(on_hand_value) as inventory_on_hand
    from {{ ref('stg_inventory') }} group by location_key, month
), mkt as (
    select location_key, month, sum(spend) as marketing_spend,
           sum(form_leads) as leads, sum(booked_appts) as booked_from_marketing
    from {{ ref('stg_marketing') }} group by location_key, month
)
select d.location_key, d.location_name, d.region, d.specialty, d.pms_system, a.month,
       a.gross_production, a.net_production, p.collections, p.insurance_collections,
       a.completed_visits, a.no_shows, a.scheduled, a.new_patients, a.hygiene_production,
       l.labor_cost, l.overtime_cost, l.labor_hours, l.overtime_hours,
       o.doctor_comp, o.lab_fees, o.payroll_taxes_benefits, o.facility_costs, o.total_opex,
       s.supply_cost, s.inventory_on_hand,
       m.marketing_spend, m.leads, m.booked_from_marketing,
       p.collections - coalesce(o.total_opex, 0) as operating_profit
from appts a
join {{ ref('dim_location') }} d on d.location_key = a.location_key
left join pay p      on p.location_key = a.location_key and p.month = a.month
left join labor l    on l.location_key = a.location_key and l.month = a.month
left join opex o     on o.location_key = a.location_key and o.month = a.month
left join supplies s on s.location_key = a.location_key and s.month = a.month
left join mkt m      on m.location_key = a.location_key and m.month = a.month
