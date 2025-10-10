
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select value_type_id
from "warehouse"."analytics_analytics"."dim_value_type"
where value_type_id is null



  
  
      
    ) dbt_internal_test