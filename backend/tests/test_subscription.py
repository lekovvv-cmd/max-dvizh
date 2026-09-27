import json

import httpx
import pytest

from app.core.config import Settings
from app.modules.max_integration import subscribe_webhook


def configure(monkeypatch, handler):
    client = httpx.Client
    monkeypatch.setattr(
        subscribe_webhook,
        "settings",
        Settings(
            max_bot_token="private-token",
            max_webhook_url="https://example.org/api/v1/integrations/max/webhook",
            max_webhook_secret="private-secret",
        ),
    )
    monkeypatch.setattr(
        subscribe_webhook.httpx,
        "Client",
        lambda **kwargs: client(**kwargs, transport=httpx.MockTransport(handler)),
    )


@pytest.mark.parametrize("field", ["max_bot_token", "max_webhook_url", "max_webhook_secret"])
def test_subscription_requires_all_webhook_settings_before_http(monkeypatch, field):
    values = {
        "max_bot_token": "private-token",
        "max_webhook_url": "https://example.org/webhook",
        "max_webhook_secret": "private-secret",
    }
    values[field] = ""
    monkeypatch.setattr(subscribe_webhook, "settings", Settings(**values))

    def unexpected_http(**_kwargs):
        raise AssertionError("Invalid subscription configuration must not make HTTP requests")

    monkeypatch.setattr(subscribe_webhook.httpx, "Client", unexpected_http)
    with pytest.raises(SystemExit) as error:
        subscribe_webhook.subscribe()
    assert str(error.value) == "Set MAX_BOT_TOKEN, MAX_WEBHOOK_URL and MAX_WEBHOOK_SECRET"
    assert "private-" not in str(error.value)


def test_repeated_subscription_updates_one_url_and_verifies_types(monkeypatch, capsys):
    subscriptions = {}
    calls = []

    def handler(request):
        calls.append((request.method, request.url.path))
        assert request.headers["Authorization"] == "private-token"
        if request.method == "POST":
            body = json.loads(request.content)
            subscriptions[body["url"]] = {"url": body["url"], "update_types": body["update_types"]}
            return httpx.Response(200, json={"success": True})
        return httpx.Response(200, json={"subscriptions": list(subscriptions.values())})

    configure(monkeypatch, handler)
    subscribe_webhook.subscribe()
    subscribe_webhook.subscribe()
    assert len(subscriptions) == 1
    assert calls == [("POST", "/subscriptions"), ("GET", "/subscriptions")] * 2
    output = capsys.readouterr().out
    assert output.count("verified") == 2 and "private-" not in output


@pytest.mark.parametrize("failure", ["auth", "network", "missing_types", "invalid_json"])
def test_subscription_fails_safely_on_delivery_or_verification_errors(monkeypatch, failure):
    def handler(request):
        if failure == "auth":
            return httpx.Response(401, json={"message": "private-token private-secret"})
        if failure == "network":
            raise httpx.ConnectError("private-token", request=request)
        if failure == "invalid_json":
            return httpx.Response(200, text="private-secret")
        if request.method == "POST":
            return httpx.Response(200, json={"success": True})
        return httpx.Response(
            200,
            json={
                "subscriptions": [
                    {
                        "url": subscribe_webhook.settings.max_webhook_url,
                        "update_types": ["bot_started"],
                    }
                ]
            },
        )

    configure(monkeypatch, handler)
    with pytest.raises(SystemExit) as error:
        subscribe_webhook.subscribe()
    assert "private-" not in str(error.value)
    assert "failed" in str(error.value)
