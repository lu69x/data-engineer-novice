
  
  create view "warehouse"."analytics_analytics"."dim_response__dbt_tmp" as (
    

select distinct
  response_id,
  response
from "warehouse"."analytics_analytics"."stg_cdi_clean"
where response_id is not null
  );
