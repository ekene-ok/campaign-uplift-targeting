-- 01_experiment_results.sql
-- Topline results of the randomised email test: 64,000 customers split evenly into
-- Mens E-Mail, Womens E-Mail and No E-Mail (control). Outcomes over the next two weeks.

CREATE OR REPLACE TABLE customers AS
SELECT ROW_NUMBER() OVER () AS customer_id, *,
       CASE WHEN mens = 1 AND womens = 1 THEN 'Bought both'
            WHEN mens = 1 THEN 'Bought mens only'
            ELSE 'Bought womens only' END AS purchase_history
FROM read_csv_auto('data/raw/hillstrom.csv');

CREATE OR REPLACE VIEW arm_results AS
SELECT segment                              AS arm,
       COUNT(*)                             AS customers,
       ROUND(AVG(visit), 4)                 AS visit_rate,
       ROUND(AVG(conversion), 5)            AS conversion_rate,
       ROUND(AVG(spend), 4)                 AS spend_per_customer,
       ROUND(SUM(spend), 0)                 AS total_spend
FROM customers
GROUP BY segment
ORDER BY spend_per_customer DESC;

-- Balance check: randomisation should make arms look alike before the email.
CREATE OR REPLACE VIEW balance_check AS
SELECT segment AS arm,
       ROUND(AVG(recency), 2) AS avg_recency_months,
       ROUND(AVG(history), 2) AS avg_past_spend,
       ROUND(AVG(newbie), 3)  AS share_new_customers,
       ROUND(AVG(mens), 3)    AS share_bought_mens,
       ROUND(AVG(womens), 3)  AS share_bought_womens
FROM customers
GROUP BY segment
ORDER BY arm;
