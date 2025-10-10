

select distinct
  response_id,
  response
from "warehouse"."analytics_analytics"."stg_cdi_clean"
where response_id is not null