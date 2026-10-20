-- Q1: Category → PDP conversion rate by city tier
-- Shows which tier has the worst drop-off at the critical funnel step
SELECT
    u.city_tier,
    COUNT(DISTINCT CASE WHEN e.event_name = 'category_page_view' THEN e.user_id END) AS users_at_category,
    COUNT(DISTINCT CASE WHEN e.event_name = 'pdp_view'           THEN e.user_id END) AS users_at_pdp,
    ROUND(
        COUNT(DISTINCT CASE WHEN e.event_name = 'pdp_view' THEN e.user_id END) * 100.0 /
        NULLIF(COUNT(DISTINCT CASE WHEN e.event_name = 'category_page_view' THEN e.user_id END), 0)
    , 2) AS conversion_rate_pct,
    ROUND(100 - (
        COUNT(DISTINCT CASE WHEN e.event_name = 'pdp_view' THEN e.user_id END) * 100.0 /
        NULLIF(COUNT(DISTINCT CASE WHEN e.event_name = 'category_page_view' THEN e.user_id END), 0)
    ), 2) AS dropoff_rate_pct
FROM silver_db.events e
JOIN silver_db.users  u ON e.user_id = u.user_id
WHERE e.event_name IN ('category_page_view', 'pdp_view')
GROUP BY u.city_tier
ORDER BY dropoff_rate_pct DESC;
