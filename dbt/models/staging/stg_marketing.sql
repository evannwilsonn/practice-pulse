-- Marketing: utm_source + utm_medium -> channel; Windsor.ai Meta Ads rows mapped to the Meta channel
select x.location_key, cast(m.month as date) as month, coalesce(c.channel, 'Other') as channel,
       c.is_paid, m.utm_campaign as campaign,
       {{ num('m.cost') }} as spend, {{ int('m.sessions') }} as sessions,
       {{ int('m.form_submits') }} as form_leads, {{ int('m.appts_booked') }} as booked_appts
from {{ source('raw', 'marketing__channel_performance') }} m
join {{ ref('location_crosswalk') }} x on x.source_system = 'marketing' and x.source_location = m.site_slug
left join {{ ref('marketing_channel_map') }} c on c.utm_source = m.utm_source and c.utm_medium = m.utm_medium
union all
-- Windsor.ai: one row per day and campaign, ad account id mapped to an office in the crosswalk
select x.location_key, {{ month_of('cast(w.date as date)') }}, 'Meta', true, w.campaign,
       {{ num('w.spend') }}, {{ int('w.clicks') }}, {{ int('w.actions_lead') }}, 0
from {{ source('raw', 'windsor__facebook_ads') }} w
join {{ ref('location_crosswalk') }} x on x.source_system = 'windsor_facebook' and x.source_location = w.account_id
