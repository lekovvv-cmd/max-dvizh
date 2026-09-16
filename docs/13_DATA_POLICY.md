# 13 — Data provenance and external data policy

## Provenance required
Every CandidatePlan stores a source snapshot with provider, provider ID/type, provider URL if available, fetch timestamp, original price text, parsed price and demo/model flag. Browsed provider items do not become database rows.

## Distinguish
- provider fact;
- our calculation;
- approximate parsed value;
- model/demo data.

## Freshness
Define TTL by query type. Cache only the requested city/time/category slice; do not use old event data as current when date matters.

## Fallback priority
1. fresh live data;
2. valid recent Redis cache entry;
3. explicit demo/model data only for demonstration;
4. honest empty/error state.

Never fabricate a live event, restore a provider catalogue from PostgreSQL, or silently label model data as live.

## Official sources
The case recommends official resources such as Культура.РФ, PRO.Культура.РФ, Минспорт sources, Путешествуем.рф, Добро.рф, Пушкинская карта information and ФИАС.

KudaGo is a practical initial integration, not an official government source. Presentation must distinguish MVP practicality from future official/partner integrations.

## Our calculations
Distance km, compatibility, Near delta, ranking are product calculations, not provider facts.

## Price parser
Conservative. Low confidence → numeric null and original/source-safe text.
