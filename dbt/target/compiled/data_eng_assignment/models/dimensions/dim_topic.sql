

select distinct
  topic_id,
  topic
from "warehouse"."analytics_analytics"."stg_cdi_clean"
where topic_id is not null