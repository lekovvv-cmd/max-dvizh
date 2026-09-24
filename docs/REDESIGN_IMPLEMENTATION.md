# Текущая реализация

Новый продуктовый сценарий ДВИЖа описан в [PRODUCT.md](PRODUCT.md), его состояния и миграция — в [ARCHITECTURE.md](ARCHITECTURE.md), endpoint-контракт и MAX Webhook — в [API.md](API.md). Результат проверки отрисованного интерфейса — в [design-qa.md](../design-qa.md).

Прежний экран отдельных Offer/Plan более не используется frontend. Legacy таблицы и endpoints остаются для безопасной истории и миграции, но новые сигналы имеют `flow_version=2` и идут через DvizhSession, приватные реакции и окончательные подтверждения.
