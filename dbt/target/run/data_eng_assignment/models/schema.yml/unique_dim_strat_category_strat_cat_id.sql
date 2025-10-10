
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    

select
    strat_cat_id as unique_field,
    count(*) as n_records

from "warehouse"."analytics_analytics"."dim_strat_category"
where strat_cat_id is not null
group by strat_cat_id
having count(*) > 1



  
  
      
    ) dbt_internal_test