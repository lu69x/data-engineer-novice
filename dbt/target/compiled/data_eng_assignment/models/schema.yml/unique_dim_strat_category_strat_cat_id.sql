
    
    

select
    strat_cat_id as unique_field,
    count(*) as n_records

from "warehouse"."analytics_analytics"."dim_strat_category"
where strat_cat_id is not null
group by strat_cat_id
having count(*) > 1


