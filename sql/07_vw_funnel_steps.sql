-- vw_funnel_steps
-- Session-level funnel view: each user counted once per session per step.
-- A user who visits category_page_view twice in one session counts as 1.
-- Downstream queries JOIN this view instead of raw events.

DROP VIEW IF EXISTS silver_db.vw_funnel_steps;
CREATE VIEW silver_db.vw_funnel_steps AS

WITH ranked_events AS (
    -- Deduplicate: keep earliest occurrence of each event per user per session
    SELECT
        user_id,
        session_id,
        event_name,
        event_date,
        category,
        price_band,
        ROW_NUMBER() OVER (
            PARTITION BY user_id, session_id, event_name
            ORDER BY event_timestamp ASC
        ) AS rn
    FROM silver_db.events
    WHERE event_name IN (
        'app_open', 'home_view', 'search', 'category_page_view',
        'pdp_view', 'add_to_wishlist', 'add_to_cart',
        'checkout_start', 'payment_page', 'order_placed', 'order_returned'
    )
),

session_funnel AS (
    -- One row per user × session × funnel step
    SELECT
        user_id,
        session_id,
        event_name,
        event_date,
        category,
        price_band
    FROM ranked_events
    WHERE rn = 1
),

-- Attach user dimensions for segmentation queries
enriched AS (
    SELECT
        sf.user_id,
        sf.session_id,
        sf.event_name,
        sf.event_date,
        sf.category,
        sf.price_band,
        u.device_type,
        u.city_tier,
        u.acquisition_channel,
        u.age_band,
        u.platform
    FROM session_funnel sf
    JOIN silver_db.users u ON sf.user_id = u.user_id
)

SELECT * FROM silver_db.vw_funnel_steps;