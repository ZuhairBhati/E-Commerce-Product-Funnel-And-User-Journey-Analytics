"""
Myntra Synthetic Dataset Generator
Constraints: 16 realism rules enforced (see comments)
Tables: users, events, orders
"""

import json, os
import numpy as np
import pandas as pd
from faker import Faker
from datetime import datetime, timedelta

# ==============================================================================
# SECTION 1: CONFIG
# ==============================================================================
SEED = 42
np.random.seed(SEED)
fake = Faker("en_IN")
Faker.seed(SEED)

N_USERS        = 150_000
TARGET_EVENTS  = 3_000_000
OUTPUT_DIR     = "./data/bronze"
WINDOW_DAYS    = 90
END_DATE       = datetime(2026, 6, 30)
START_DATE     = END_DATE - timedelta(days=WINDOW_DAYS)
WINDOW_SEC     = WINDOW_DAYS * 24 * 3600

# Funnel drop-off probabilities (constraint 1)
P_CAT_TO_PDP      = 0.40
P_PDP_TO_CART     = 0.55
P_CART_TO_CHECK   = 0.70
# Remaining funnel (unconstrained but realistic)
P_APP_TO_HOME     = 0.95
P_HOME_TO_SEARCH  = 0.70
P_SEARCH_TO_CAT   = 0.55
P_PDP_TO_WISH     = 0.20
P_CHECK_TO_PAY    = 0.85
P_PAY_TO_ORDER    = 0.90

STAGE_NAMES = [
    "app_open","home_view","search","category_page_view","pdp_view",
    "add_to_wishlist","add_to_cart","checkout_start","payment_page",
    "order_placed","order_returned",
]
STAGE_OFFSET_MIN = {
    "app_open":0,"home_view":1,"search":3,"category_page_view":5,
    "pdp_view":7,"add_to_wishlist":8,"add_to_cart":9,
    "checkout_start":11,"payment_page":13,"order_placed":14,"order_returned":15,
}

# constraint 10: Fashion 50%, Beauty 30%, Electronics 20%
CATEGORIES    = ["fashion","beauty","electronics"]
CATEGORY_P    = np.array([0.50, 0.30, 0.20])

SUBCATEGORY_MAP = {
    "fashion":     ["clothing","footwear","accessories","ethnic_wear","activewear"],
    "beauty":      ["skincare","makeup","haircare","fragrance","personal_care"],
    "electronics": ["smartphones","earphones","laptops","smartwatch","cables"],
}

# constraint 7 & 15: fashion highest, electronics lowest
CATEGORY_RETURN_PROB = {"fashion":0.25, "beauty":0.10, "electronics":0.05}

# constraint 11: GMV lognormal mu per category
GMV_PARAMS = {
    "fashion":     {"tier_1":(7.40,0.45),"tier_2":(7.00,0.45),"tier_3":(6.70,0.45)},
    "beauty":      {"tier_1":(7.00,0.45),"tier_2":(6.60,0.45),"tier_3":(6.30,0.45)},
    "electronics": {"tier_1":(9.20,0.40),"tier_2":(8.90,0.40),"tier_3":(8.60,0.40)},
}

PRICE_BANDS   = ["budget","mid","premium","luxury"]
PRICE_BAND_P  = [0.30, 0.40, 0.22, 0.08]

# constraint 6: Zipf-weighted search queries (fashion + beauty + electronics)
SEARCH_QUERIES = [
    # fashion
    "men's slim fit jeans","women's kurti online","running shoes men",
    "ethnic wear women","casual t-shirts","formal shirts men",
    "women's sneakers","lehenga choli","summer dresses women",
    "track pants men","sports bra","oversized hoodie",
    "handbags for women","watches for men","sunglasses women",
    # beauty
    "vitamin c serum","hyaluronic acid serum","niacinamide serum",
    "matte lipstick","waterproof kajal","sunscreen spf 50",
    "moisturiser for dry skin","hair oil for hair fall",
    "foundation for oily skin","anti dandruff shampoo",
    "retinol night serum","clay face mask","tinted lip balm",
    "perfume for women","body lotion winter",
    # electronics
    "wireless earbuds","smartphone under 15000","laptop for students",
    "smartwatch android","bluetooth speaker","phone case iphone",
    "usb c cable fast charging","gaming earphones","power bank 20000mah",
    "noise cancelling headphones","smart tv 43 inch","tablet for kids",
    "laptop bag","screen protector","mechanical keyboard",
]
_w = np.array([1.0/(i+1)**0.9 for i in range(len(SEARCH_QUERIES))])
SEARCH_QUERY_P = _w / _w.sum()

# ==============================================================================
# SECTION 2: USERS TABLE
# ==============================================================================
user_ids = np.array([f"U{100000+i}" for i in range(N_USERS)])

# constraint 5
AGE_BANDS  = ["18-22","22-28","28-35","35-45","45+"]
AGE_BAND_P = [0.15, 0.32, 0.30, 0.15, 0.08]
age_band   = np.random.choice(AGE_BANDS, size=N_USERS, p=AGE_BAND_P)

CITY_TIERS  = ["tier_1","tier_2","tier_3"]
CITY_TIER_P = [0.35, 0.40, 0.25]
city_tier   = np.random.choice(CITY_TIERS, size=N_USERS, p=CITY_TIER_P)

# constraint 2 & 9: android 58%, ios 22%, desktop 8%, tablet 12%
DEVICE_TYPES  = ["android","ios","desktop","tablet"]
DEVICE_TYPE_P = [0.58, 0.22, 0.08, 0.12]
device_type   = np.random.choice(DEVICE_TYPES, size=N_USERS, p=DEVICE_TYPE_P)

# constraint 3: organic + instagram > 55%
CHANNELS  = ["organic_search","instagram","paid_search","affiliate","email","direct","facebook"]
CHANNEL_P = [0.30, 0.28, 0.12, 0.10, 0.08, 0.07, 0.05]
acq_channel = np.random.choice(CHANNELS, size=N_USERS, p=CHANNEL_P)

# constraint 13: app ≥ 80%
PLATFORMS  = ["app","web"]
# mobile devices → mostly app; desktop → mostly web
platform = np.where(np.isin(device_type, ["android","ios"]),
                    np.random.choice(["app","web"], size=N_USERS, p=[0.95,0.05]),
                    np.random.choice(["app","web"], size=N_USERS, p=[0.25,0.75]))

signup_offset = np.random.randint(0, WINDOW_DAYS+275, size=N_USERS)
signup_date   = np.array([
    (START_DATE - timedelta(days=275) + timedelta(days=int(d))).date()
    for d in signup_offset
])

users = pd.DataFrame({
    "user_id": user_ids, "signup_date": signup_date,
    "city_tier": city_tier, "device_type": device_type,
    "platform": platform, "acquisition_channel": acq_channel,
    "age_band": age_band,
})

# ==============================================================================
# SECTION 3: EVENTS TABLE
# ==============================================================================
# constraint 8 & 9: mobile users get more sessions
DEVICE_LAMBDA = {"android":6.5,"ios":6.0,"desktop":4.5,"tablet":5.5}
sess_lambda   = np.vectorize(DEVICE_LAMBDA.get)(device_type) * 1.08
sess_per_user = np.random.poisson(sess_lambda).clip(min=1)

n_sess          = int(sess_per_user.sum())
sess_user_id    = np.repeat(user_ids, sess_per_user)
sess_user_idx   = np.repeat(np.arange(N_USERS), sess_per_user)
sess_start_off  = np.random.randint(0, WINDOW_SEC, size=n_sess)

sess_df = pd.DataFrame({
    "user_id": sess_user_id, "user_idx": sess_user_idx,
    "offset_sec": sess_start_off,
}).sort_values(["user_idx","offset_sec"]).reset_index(drop=True)

# constraint 8: enforce 30-min inactivity gap
MIN_GAP = 30*60
def _enforce_gap(arr):
    out = arr.copy()
    for i in range(1, len(out)):
        if out[i]-out[i-1] < MIN_GAP:
            out[i] = out[i-1] + MIN_GAP
    return out

sess_df["offset_sec"] = (
    sess_df.groupby("user_idx")["offset_sec"]
    .transform(lambda s: _enforce_gap(s.to_numpy()))
)
sess_df["session_start"] = START_DATE + pd.to_timedelta(sess_df["offset_sec"], unit="s")
sess_df["session_id"]    = "S" + sess_df.index.astype(str).str.zfill(8)
n = len(sess_df)

# per-session assignments
sess_category   = np.random.choice(CATEGORIES, size=n, p=CATEGORY_P)
sess_price_band = np.random.choice(PRICE_BANDS, size=n, p=PRICE_BAND_P)
sess_product_id = np.array([f"P{np.random.randint(1,8000):05d}" for _ in range(n)])
sess_search_q   = np.random.choice(SEARCH_QUERIES, size=n, p=SEARCH_QUERY_P)

# utm_source loosely aligned to acquisition channel
UTM_MAP = {
    "organic_search":"organic","instagram":"instagram",
    "paid_search":"google","affiliate":"affiliate",
    "email":"email","direct":"direct","facebook":"facebook",
}
sess_user_channel = np.vectorize(lambda uid: acq_channel[int(uid[1:])-100000])(sess_user_id)
sess_utm = np.vectorize(UTM_MAP.get)(sess_user_channel)

# vectorized funnel (constraints 1, 7)
rand   = np.random.random(size=(10,n))
r_app  = np.ones(n, dtype=bool)
r_home = r_app  & (rand[0] < P_APP_TO_HOME)
r_srch = r_home & (rand[1] < P_HOME_TO_SEARCH)
r_cat  = r_srch & (rand[2] < P_SEARCH_TO_CAT)
r_pdp  = r_cat  & (rand[3] < P_CAT_TO_PDP)      # constraint 1
r_wish = r_pdp  & (rand[4] < P_PDP_TO_WISH)
r_cart = r_pdp  & (rand[5] < P_PDP_TO_CART)      # constraint 1
r_chk  = r_cart & (rand[6] < P_CART_TO_CHECK)    # constraint 1
r_pay  = r_chk  & (rand[7] < P_CHECK_TO_PAY)
r_ord  = r_pay  & (rand[8] < P_PAY_TO_ORDER)
ret_p  = np.vectorize(CATEGORY_RETURN_PROB.get)(sess_category)
r_ret  = r_ord  & (rand[9] < ret_p)

MASKS = {
    "app_open":r_app,"home_view":r_home,"search":r_srch,
    "category_page_view":r_cat,"pdp_view":r_pdp,"add_to_wishlist":r_wish,
    "add_to_cart":r_cart,"checkout_start":r_chk,"payment_page":r_pay,
    "order_placed":r_ord,"order_returned":r_ret,
}
WITH_PRODUCT  = {"pdp_view","add_to_wishlist","add_to_cart","checkout_start",
                 "payment_page","order_placed","order_returned"}
WITH_CATEGORY = WITH_PRODUCT | {"category_page_view"}

frames = []
for stage in STAGE_NAMES:
    idx = np.nonzero(MASKS[stage])[0]
    m   = len(idx)
    jit = STAGE_OFFSET_MIN[stage] + np.random.uniform(-0.5, 0.5, size=m)
    ts  = sess_df["session_start"].to_numpy()[idx] + pd.to_timedelta(jit, unit="m")
    hp  = stage in WITH_PRODUCT
    hc  = stage in WITH_CATEGORY
    frames.append(pd.DataFrame({
        "user_id":      sess_df["user_id"].to_numpy()[idx],
        "session_id":   sess_df["session_id"].to_numpy()[idx],
        "event_name":   stage,
        "event_timestamp": ts,
        "category":     sess_category[idx] if hc else None,
        "subcategory":  ([np.random.choice(SUBCATEGORY_MAP[c]) for c in sess_category[idx]]
                         if hc else None),
        "product_id":   sess_product_id[idx] if hp else None,
        "price_band":   sess_price_band[idx] if hp else None,
        "search_query": sess_search_q[idx] if stage=="search" else None,
        "utm_source":   sess_utm[idx],
    }))

events = pd.concat(frames, ignore_index=True)
if len(events) > TARGET_EVENTS:
    events = events.sample(n=TARGET_EVENTS, random_state=SEED)
events = events.sort_values(["user_id","event_timestamp"]).reset_index(drop=True)
events.insert(0,"event_id",["E"+str(i).zfill(8) for i in range(len(events))])

# ==============================================================================
# SECTION 4: ORDERS TABLE
# ==============================================================================
sess_lookup = sess_df.set_index("session_id").copy()
sess_lookup["city_tier"] = city_tier[sess_lookup["user_idx"].to_numpy()]
sess_lookup["category"]  = pd.Series(sess_category,  index=sess_df["session_id"].to_numpy())
sess_lookup["returned"]  = pd.Series(r_ret,           index=sess_df["session_id"].to_numpy())

placed        = events[events["event_name"]=="order_placed"].copy()
placed_sess   = sess_lookup.loc[placed["session_id"]]
n_orders      = len(placed)
ord_tier      = placed_sess["city_tier"].to_numpy()
ord_cat       = placed_sess["category"].to_numpy()
ord_ret       = placed_sess["returned"].to_numpy()

# constraint 11: GMV lognormal per category × tier
gmv = np.empty(n_orders)
for cat in CATEGORIES:
    for tier in CITY_TIERS:
        mask = (ord_cat==cat) & (ord_tier==tier)
        mu,sigma = GMV_PARAMS[cat][tier]
        gmv[mask] = np.random.lognormal(mu, sigma, size=mask.sum())
gmv = np.round(gmv, 2)

# constraint 14: iOS users have higher AOV (~18% uplift over Android)
ord_device = users.set_index("user_id").loc[placed["user_id"].to_numpy(), "device_type"].to_numpy()
ios_mask   = ord_device == "ios"
gmv[ios_mask] = np.round(gmv[ios_mask] * 1.18, 2)

# constraint 4: tier-1 higher coupon usage
COUPON_P = {"tier_1":0.55,"tier_2":0.40,"tier_3":0.30}
coupon_p_arr  = np.vectorize(COUPON_P.get)(ord_tier)
coupon_applied = np.random.random(n_orders) < coupon_p_arr

# constraint 16: city tier → payment method
PAY_PROBS = {
    "tier_1": (["UPI","COD","card","BNPL"],[0.45,0.15,0.30,0.10]),
    "tier_2": (["UPI","COD","card","BNPL"],[0.45,0.25,0.20,0.10]),
    "tier_3": (["UPI","COD","card","BNPL"],[0.40,0.45,0.10,0.05]),
}
payment_method = np.empty(n_orders, dtype=object)
for tier,(methods,probs) in PAY_PROBS.items():
    mask = ord_tier==tier
    payment_method[mask] = np.random.choice(methods, size=mask.sum(), p=probs)

# constraint 12: COD → higher return uplift (+8%)
cod_mask = payment_method=="COD"
extra_ret = np.random.random(n_orders) < 0.08
ord_ret   = ord_ret | (cod_mask & extra_ret)

# category_mix JSON
category_mix = []
for cat in ord_cat:
    n_extra = np.random.choice([0,1,2], p=[0.55,0.30,0.15])
    extras  = (np.random.choice([c for c in CATEGORIES if c!=cat],
               size=n_extra, replace=False) if n_extra else np.array([]))
    mix     = {cat: round(np.random.uniform(0.55,0.85),2)}
    rem     = round(1.0-mix[cat],2)
    for i,ec in enumerate(extras):
        share   = round(rem/len(extras),2) if i<len(extras)-1 else rem
        mix[ec] = float(share)
        rem     = round(rem-share,2)
    category_mix.append(json.dumps(mix))

orders = pd.DataFrame({
    "order_id":       ["O"+str(i).zfill(8) for i in range(n_orders)],
    "user_id":        placed["user_id"].to_numpy(),
    "order_date":     placed["event_timestamp"].to_numpy(),
    "gmv":            gmv,
    "category_mix":   category_mix,
    "payment_method": payment_method,
    "coupon_applied": coupon_applied,
    "return_initiated": ord_ret,
})

# ==============================================================================
# SECTION 5: VALIDATION
# ==============================================================================
print("="*65)
print("VALIDATION REPORT")
print("="*65)
print(f"users: {len(users):,} | events: {len(events):,} | orders: {len(orders):,}")

print("\n-- Funnel drop-offs (constraint 1) --")
fc = {s:int(MASKS[s].sum()) for s in STAGE_NAMES}
for a,b in [("category_page_view","pdp_view"),("pdp_view","add_to_cart"),("add_to_cart","checkout_start")]:
    conv = fc[b]/fc[a]
    print(f"  {a} → {b}: {conv:.1%} conv ({1-conv:.1%} drop)")

print("\n-- Device split (constraints 2,9) --")
ev_dev = events.merge(users[["user_id","device_type"]], on="user_id", how="left")
print(ev_dev[ev_dev["event_name"]=="app_open"]["device_type"].value_counts(normalize=True).round(3))

print("\n-- Platform split (constraint 13) --")
print(users["platform"].value_counts(normalize=True).round(3))

print("\n-- Channel mix (constraint 3) --")
cm = users["acquisition_channel"].value_counts(normalize=True)
print(cm.round(3))
print(f"  organic+instagram = {cm.get('organic_search',0)+cm.get('instagram',0):.1%}")

print("\n-- Age bands (constraint 5) --")
am = users["age_band"].value_counts(normalize=True)
print(f"  22-28+28-35 = {am.get('22-28',0)+am.get('28-35',0):.1%}")

print("\n-- GMV by category (constraint 11) --")
orders["_cat"] = orders["category_mix"].apply(lambda s: next(iter(json.loads(s))))
print(orders.groupby("_cat")["gmv"].mean().round(0))

print("\n-- GMV & coupon by city tier (constraint 4) --")
ou = orders.merge(users[["user_id","city_tier"]], on="user_id", how="left")
print(ou.groupby("city_tier")[["gmv"]].mean().round(0))
print(ou.groupby("city_tier")["coupon_applied"].mean().round(3))

print("\n-- Payment method by tier (constraint 16) --")
print(ou.groupby(["city_tier","payment_method"]).size().unstack(fill_value=0))

print("\n-- Return rate by category (constraints 7,12,15) --")
print(f"  Overall: {orders['return_initiated'].mean():.2%}")
print(orders.groupby("_cat")["return_initiated"].mean().round(3).sort_values(ascending=False))
orders.drop(columns=["_cat"], inplace=True)

print("\n-- iOS vs Android AOV (constraint 14) --")
ord_dev = orders.merge(users[["user_id","device_type"]], on="user_id", how="left")
print(ord_dev[ord_dev["device_type"].isin(["android","ios"])].groupby("device_type")["gmv"].mean().round(0))

# ==============================================================================
# SECTION 6: EXPORT TO PARQUET (BRONZE)
# ==============================================================================
os.makedirs(OUTPUT_DIR, exist_ok=True)
users.to_parquet(f"{OUTPUT_DIR}/users.parquet",  index=False)
events.to_parquet(f"{OUTPUT_DIR}/events.parquet", index=False)
orders.to_parquet(f"{OUTPUT_DIR}/orders.parquet", index=False)
print(f"\nBronze Parquet files saved to {OUTPUT_DIR}/")
