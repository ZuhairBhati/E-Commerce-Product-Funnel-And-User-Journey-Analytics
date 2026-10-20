-- Q5: Weekly GMV trend over the 90-day window
SELECT
    DATE_FORMAT(DATE(order_date), '%Y-%u')  AS year_week,
    MIN(DATE(order_date))                   AS week_start_date,
    COUNT(order_id)                         AS total_orders,
    ROUND(SUM(gmv), 2)                      AS weekly_gmv,
    ROUND(AVG(gmv), 2)                      AS avg_order_value,
    SUM(return_initiated)                   AS total_returns,
    ROUND(SUM(return_initiated) * 100.0 /
        NULLIF(COUNT(order_id), 0), 2)      AS return_rate_pct
FROM silver_db.orders
GROUP BY year_week
ORDER BY year_week;
