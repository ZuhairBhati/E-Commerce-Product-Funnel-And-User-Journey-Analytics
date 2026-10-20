-- Q2: Which acquisition channel drives highest average GMV per order?
SELECT
    u.acquisition_channel,
    COUNT(o.order_id)        AS total_orders,
    ROUND(AVG(o.gmv), 2)    AS avg_gmv,
    ROUND(SUM(o.gmv), 2)    AS total_gmv,
    ROUND(AVG(o.gmv) * 100.0 /
        NULLIF((SELECT AVG(gmv) FROM silver_db.orders), 0), 2) AS index_vs_avg
FROM silver_db.orders o
JOIN silver_db.users  u ON o.user_id = u.user_id
GROUP BY u.acquisition_channel
ORDER BY avg_gmv DESC;
