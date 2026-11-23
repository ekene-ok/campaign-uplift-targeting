-- 02_segment_uplift.sql
-- Uplift by segment = treated arm minus control, within the same segment.
-- Because assignment was random, this difference is a causal effect for that segment.

CREATE OR REPLACE VIEW segment_uplift AS
WITH by_arm AS (
    SELECT 'Purchase history' AS dimension, purchase_history AS segment_value, segment AS arm,
           COUNT(*) AS n, AVG(visit) AS visit, AVG(spend) AS spend FROM customers GROUP BY ALL
    UNION ALL
    SELECT 'New customer', CASE WHEN newbie = 1 THEN 'New (last 12 months)' ELSE 'Existing' END, segment,
           COUNT(*), AVG(visit), AVG(spend) FROM customers GROUP BY ALL
    UNION ALL
    SELECT 'Channel', channel, segment, COUNT(*), AVG(visit), AVG(spend) FROM customers GROUP BY ALL
    UNION ALL
    SELECT 'Area', zip_code, segment, COUNT(*), AVG(visit), AVG(spend) FROM customers GROUP BY ALL
),
pivoted AS (
    SELECT dimension, segment_value,
           SUM(n)                                                   AS customers,
           MAX(visit) FILTER (WHERE arm = 'No E-Mail')              AS visit_control,
           MAX(visit) FILTER (WHERE arm = 'Mens E-Mail')            AS visit_mens,
           MAX(visit) FILTER (WHERE arm = 'Womens E-Mail')          AS visit_womens,
           MAX(spend) FILTER (WHERE arm = 'No E-Mail')              AS spend_control,
           MAX(spend) FILTER (WHERE arm = 'Mens E-Mail')            AS spend_mens,
           MAX(spend) FILTER (WHERE arm = 'Womens E-Mail')          AS spend_womens
    FROM by_arm
    GROUP BY dimension, segment_value
)
SELECT dimension, segment_value, customers,
       ROUND(visit_mens   - visit_control, 4) AS visit_uplift_mens,
       ROUND(visit_womens - visit_control, 4) AS visit_uplift_womens,
       ROUND(spend_mens   - spend_control, 3) AS spend_uplift_mens,
       ROUND(spend_womens - spend_control, 3) AS spend_uplift_womens,
       CASE WHEN visit_mens - visit_control >= visit_womens - visit_control
            THEN 'Mens E-Mail' ELSE 'Womens E-Mail' END AS better_email_by_visits
FROM pivoted
ORDER BY dimension, segment_value;
