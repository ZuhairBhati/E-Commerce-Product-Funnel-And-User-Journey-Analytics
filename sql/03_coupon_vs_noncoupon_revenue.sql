-- Q3: What % of revenue and orders come from coupon vs non-coupon?
SELECT
    CASE WHEN coupon_applied = 1 THEN 'coupon' ELSE 'no_coupon' END AS order_type,
    COUNT(order_id)                             AS total_orders,
    ROUND(SUM(gmv), 2)                          AS total_gmv,
    ROUND(COUNT(order_id) * 100.0 /
        SUM(COUNT(order_id)) OVER (), 2)        AS order_share_pct,
    ROUND(SUM(gmv) * 100.0 /
        SUM(SUM(gmv)) OVER (), 2)               AS gmv_share_pct,
    ROUND(AVG(gmv), 2)                          AS avg_order_value
FROM silver_db.orders
GROUP BY coupon_applied;
