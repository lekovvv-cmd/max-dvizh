"""Cities available for company creation, independently of provider uptime."""

CITIES: dict[str, dict[str, str]] = {
    "msk": {"slug": "msk", "name": "Москва", "timezone": "Europe/Moscow"},
    "spb": {"slug": "spb", "name": "Санкт-Петербург", "timezone": "Europe/Moscow"},
    "ekb": {"slug": "ekb", "name": "Екатеринбург", "timezone": "Asia/Yekaterinburg"},
    "kzn": {"slug": "kzn", "name": "Казань", "timezone": "Europe/Moscow"},
    "nnv": {"slug": "nnv", "name": "Нижний Новгород", "timezone": "Europe/Moscow"},
    "nsk": {"slug": "nsk", "name": "Новосибирск", "timezone": "Asia/Novosibirsk"},
    "tmn": {"slug": "tmn", "name": "Тюмень", "timezone": "Asia/Yekaterinburg"},
}

# KudaGo has no Tyumen location; Geoapify supplies its places when configured.
GEOAPIFY_ONLY_CITIES = frozenset({"tmn"})
