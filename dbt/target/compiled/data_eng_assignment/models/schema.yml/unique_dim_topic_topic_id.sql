
    
    

select
    topic_id as unique_field,
    count(*) as n_records

from "warehouse"."analytics_analytics"."dim_topic"
where topic_id is not null
group by topic_id
having count(*) > 1


