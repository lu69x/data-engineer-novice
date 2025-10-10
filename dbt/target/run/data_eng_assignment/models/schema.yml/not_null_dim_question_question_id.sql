
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select question_id
from "warehouse"."analytics_analytics"."dim_question"
where question_id is null



  
  
      
    ) dbt_internal_test