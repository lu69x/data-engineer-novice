
  
  create view "warehouse"."analytics_analytics"."dim_location__dbt_tmp" as (
    

select distinct
  cast(location_id as integer) as location_id,
  state                        as location_abbr,
  state_name                   as location_desc,
  cast(lon as double)          as lon,
  cast(lat as double)          as lat
from "warehouse"."analytics_analytics"."stg_cdi_clean"
where location_id is not null
  );
