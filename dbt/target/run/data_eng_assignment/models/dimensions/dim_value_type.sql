
  
  create view "warehouse"."analytics_analytics"."dim_value_type__dbt_tmp" as (
    

select distinct
  value_type_id,
  value_type,
  unit
from "warehouse"."analytics_analytics"."stg_cdi_clean"
where value_type_id is not null
  );
