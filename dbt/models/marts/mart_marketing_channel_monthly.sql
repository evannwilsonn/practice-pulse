select location_key, month, channel, sum(spend) as spend, sum(sessions) as sessions,
       sum(form_leads) as leads, sum(booked_appts) as booked
from {{ ref('stg_marketing') }} group by location_key, month, channel
