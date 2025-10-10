
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select strat_cat_id
from "warehouse"."analytics_analytics"."dim_strat_category"
where strat_cat_id is null



  
  
      
    ) dbt_internal_test