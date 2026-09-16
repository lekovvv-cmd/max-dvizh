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
id, user_id, group_id, type ONE_TIME/RECURRING, status, name, city_slug, activity_category, available_from/to, recurrence_json, budget_max nullable, origin_location_id nullable, radius_km nullable, min_people, max_people, expires_at, timestamps. Radius requires origin; omitted means no constraint.

## candidate_plans
id, group_id, city_slug, starts_at, ends_at, estimated_price_min, required_min_people, required_max_people, status, expires_at, timestamps.

## candidate_plan_source_snapshots
id, candidate_plan_id unique, provider, provider_item_id, provider_item_type, title, category, venue_name nullable, starts_at/ends_at, latitude/longitude nullable, price_text nullable, parsed_price nullable, source_url nullable, image_url nullable, source_fetched_at, is_demo. Created only together with a CandidatePlan; never one row per browsed provider item.

## candidate_plan_members
candidate_plan_id, user_id, intent_id, compatibility EXACT/NEAR/UNVERIFIED, distance_km nullable, budget_delta, deviations_json, considered_at. Conflict is not persisted as a member. Never expose raw table.

## offers
id, candidate_plan_id, user_id, status PENDING/ACCEPTED/REJECTED/EXPIRED/INVALIDATED, is_near, exception_confirmed_at, expires_at, timestamps. Unique(candidate_plan_id,user_id).

## outbox_notifications (recommended)
id, kind, user/group ref, payload, status, attempts, next_attempt_at, created_at.

## indexes
max_user_id; group_members(group_id,user_id); intents(group_id,status,city_slug); candidate_plans(group_id,status,starts_at); candidate_plan_source_snapshots(candidate_plan_id); offers(user_id,status,expires_at).

## Redis, outside the relational model
KudaGo cities/events and normalized DTOs use actual city/time/category query keys with TTL. They are temporary cache-aside entries, not domain tables and not backup data in PostgreSQL.

Use real migrations; never hand-edit production schema.
