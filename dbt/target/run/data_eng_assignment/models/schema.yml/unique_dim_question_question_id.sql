
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    

select
    question_id as unique_field,
    count(*) as n_records

from "warehouse"."analytics_analytics"."dim_question"
where question_id is not null
group by question_id
having count(*) > 1



  
  
      
    ) dbt_internal_test