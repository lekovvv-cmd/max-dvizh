# 07 — Logical data model

Implementation may rename fields but preserve semantics.

## users
id, max_user_id unique, display_name, timestamps.

## groups
id, name, optional max_chat_id, default_city_slug, timezone_name, invite_token, nullable invite_expires_at, created_by, created_at.

## group_members
group_id, user_id, role, joined_at; unique(group_id,user_id).

## locations
id, user_id, label, optional address_text, real latitude/longitude, city_slug, kind SAVED/CURRENT/MANUAL, is_ephemeral, created_at. Never create fabricated coordinates or expose other users' coordinates.

## intents
id, user_id, group_id, signal_batch_id nullable, type ONE_TIME/RECURRING, status, name, city_slug inherited from Company, legacy activity_category plus activity_categories JSON, available_from/to, recurrence_json, budget_max nullable, origin_location_id nullable, radius_km nullable, min_people, max_people nullable, expires_at, timestamps. NULL max means current Company size. Radius requires a real user-owned same-city location.

## candidate_plans
id, group_id, city_slug, starts_at, ends_at, estimated_price_min, required_min_people, required_max_people, status, expires_at, timestamps.

## candidate_plan_source_snapshots
id, candidate_plan_id unique, provider, provider_item_id, provider_item_type, title, category, venue_name nullable, starts_at/ends_at, latitude/longitude nullable, price_text nullable, parsed_price nullable, source_url nullable, image_url nullable, source_fetched_at, is_demo, source_metadata JSON (category set, price kind, place address and opening-hours warning). Event occurrence identity includes start time; Place identity includes generated slot start. Created only together with a CandidatePlan.

## candidate_plan_members
candidate_plan_id, user_id, intent_id, compatibility EXACT/NEAR/UNVERIFIED, distance_km nullable, budget_delta, deviations_json, considered_at. Conflict is not persisted as a member. Never expose raw table.

## offers
id, candidate_plan_id, user_id, status PENDING/WAITING_CONDITION/ACCEPTED/WAITLISTED/REJECTED/EXPIRED/INVALIDATED/CANCELLED_BY_USER, is_near, exception_confirmed_at, responded_at, expires_at, timestamps. Unique(candidate_plan_id,user_id).

## outbox_notifications
id, kind, user ref, payload, status, attempts, dedupe_key unique, next_attempt_at, locked_at, created_at. `PROCESSING` claims prevent two workers from dispatching one row concurrently.

## indexes
max_user_id; group_members(group_id,user_id); intents(group_id,status,city_slug); candidate_plans(group_id,status,starts_at); candidate_plan_source_snapshots(candidate_plan_id); offers(user_id,status,expires_at).

## Redis, outside the relational model
KudaGo cities/events and normalized DTOs use actual city/time/category query keys with TTL. They are temporary cache-aside entries, not domain tables and not backup data in PostgreSQL.

Use real migrations; never hand-edit production schema.
## Provider check state

Each Intent stores the last provider check state (`NOT_CHECKED`, `PROVIDER_UNAVAILABLE`, `NO_SOURCE`, `NO_FEASIBLE_PLAN`, `OFFERS_READY`). This distinguishes an outage from an empty source and from incompatible concrete plans without exposing another member's constraints.
