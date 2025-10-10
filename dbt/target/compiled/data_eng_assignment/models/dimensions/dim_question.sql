

select distinct
  question_id,
  question,
  topic_id
from "warehouse"."analytics_analytics"."stg_cdi_clean"
where question_id is not null