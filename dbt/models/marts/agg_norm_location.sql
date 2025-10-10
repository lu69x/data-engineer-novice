{{ config(materialized='table') }}

select 
  *
from {{ ref('stg_cdi_normalized') }} as b
left join {{ ref('dim_location') }} as l
  on b.location_id = l.location_id