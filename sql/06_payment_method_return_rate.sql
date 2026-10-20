-- Q6: Which payment method has the highest return rate?
SELECT
    payment_method,
    COUNT(order_id)                             AS total_orders,
    SUM(return_initiated)                       AS total_returns,
    ROUND(AVG(gmv), 2)                          AS avg_gmv,
    ROUND(SUM(return_initiated) * 100.0 /
        NULLIF(COUNT(order_id), 0), 2)          AS return_rate_pct,
    ROUND(COUNT(order_id) * 100.0 /
        SUM(COUNT(order_id)) OVER (), 2)        AS order_share_pct
FROM silver_db.orders
GROUP BY payment_method
ORDER BY return_rate_pct DESC;
