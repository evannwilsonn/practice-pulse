-- Inventory: vendor categories -> shared supply categories
select x.location_key, {{ parse_date("i.period || '01'", '%Y%m%d') }} as month, i.item_number,
       i.description, coalesce(m.category, 'Unmapped category') as category,
       {{ num('i.qty_issued') }} * {{ num('i.unit_cost') }} as supply_cost,
       {{ num('i.qty_on_hand') }} * {{ num('i.unit_cost') }} as on_hand_value
from {{ source('raw', 'inventory__usage') }} i
join {{ ref('location_crosswalk') }} x on x.source_system = 'inventory' and x.source_location = i.site_code
left join {{ ref('inventory_category_map') }} m on m.vendor_category = i.vendor_category
