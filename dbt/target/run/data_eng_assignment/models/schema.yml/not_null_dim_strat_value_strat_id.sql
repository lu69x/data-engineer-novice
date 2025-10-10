
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select strat_id
from "warehouse"."analytics_analytics"."dim_strat_value"
where strat_id is null



  
  
      
    ) dbt_internal_test