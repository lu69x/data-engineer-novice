
    
    

select
    question_id as unique_field,
    count(*) as n_records

from "warehouse"."analytics_analytics"."dim_question"
where question_id is not null
group by question_id
having count(*) > 1


