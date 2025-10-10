

select 
  -- ระบุช่วงปี
  b.year as start_year,
  b.year_end as end_year, 

  -- หน่วย/ชนิดค่า และค่าตัวเลขหลัก (normalized)
  b.unit as value_unit,
  b.value_type as value_type,
  b.value as value,  

  -- หมายเหตุ/สัญลักษณ์เชิงอธิบาย
  b.value_footnote_symbol as footnote_symbole,
  b.value_footnote as footnote, 

  -- ช่วงความเชื่อมั่น (normalized)
  b.low_ci as confidence_value_low,
  b.high_ci as confidence_value_high,

  -- ข้อมูลจากตารางมิติคำถาม
  b.question_id as question_id,
  q.question as question_text,
  q.topic_id as topic_id,
  t.topic as topic_text
  
from "warehouse"."analytics_analytics"."stg_cdi_normalized" as b
left join "warehouse"."analytics_analytics"."dim_question" as q on q.question_id = b.question_id
left join "warehouse"."analytics_analytics"."dim_topic" as t on t.topic_id = q.topic_id