# 07 — Logical data model

Implementation may rename fields but preserve semantics.

## users
id, max_user_id unique, display_name, timestamps.

## groups
id, name, optional max_chat_id, default_city_slug, created_by, created_at.

## group_members
group_id, user_id, role, joined_at; unique(group_id,user_id).

## locations
id, user_id, label, latitude, longitude, city_slug, kind SAVED/CURRENT/MANUAL, is_ephemeral, created_at. Never expose other users' coordinates.

## intents
id, user_id, group_id, type ONE_TIME/RECURRING, status, name, city_slug, activity_category, available_from/to, recurrence_json, budget_max, origin_location_id, radius_km, min_people, max_people, expires_at, timestamps.

## leisure_items
id, provider, provider_id, item_type EVENT/PLACE/MODEL, city_slug, title, category, lat/lon, starts_at/ends_at, price_text, price_min, is_free, source_url, image_url, source_fetched_at, is_demo, raw_metadata optional.

## candidate_plans
id, group_id, leisure_item_id, city_slug, starts_at, ends_at, estimated_price_min, required_min_people, required_max_people, status, expires_at, timestamps.

## candidate_plan_members
candidate_plan_id, user_id, intent_id, compatibility EXACT/NEAR/CONFLICT, distance_km, budget_delta, deviations_json, considered_at. Never expose raw table.

## offers
id, candidate_plan_id, user_id, status PENDING/ACCEPTED/REJECTED/EXPIRED/INVALIDATED, is_near, exception_confirmed_at, expires_at, timestamps. Unique(candidate_plan_id,user_id).

## provider_sync_runs
provider, city_slug, started/finished, status, fetched_count, error_summary.

## outbox_notifications (recommended)
id, kind, user/group ref, payload, status, attempts, next_attempt_at, created_at.

## indexes
max_user_id; group_members(group_id,user_id); intents(group_id,status,city_slug); leisure_items(city_slug,starts_at); candidate_plans(group_id,status,starts_at); offers(user_id,status,expires_at).

Use real migrations; never hand-edit production schema.
