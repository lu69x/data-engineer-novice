
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    

with child as (
    select strat_cat_id as from_field
    from "warehouse"."analytics_analytics"."dim_strat_value"
    where strat_cat_id is not null
),

parent as (
    select strat_cat_id as to_field
    from "warehouse"."analytics_analytics"."dim_strat_category"
)

select
    from_field

from child
left join parent
    on child.from_field = parent.to_field

where parent.to_field is null



  
  
      
    ) dbt_internal_test