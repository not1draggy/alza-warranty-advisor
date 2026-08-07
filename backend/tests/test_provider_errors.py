"""Why a provider call failed has to survive all the way to the customer.

A rejected key, an unknown model name and a network outage all stop the
analysis. Only two of them are fixed by editing the environment, so collapsing
them into one message costs whoever is debugging a great deal of time.
"""

import httpx
import pytest
from anthropic import APIConnectionError, APIStatusError

from app.core.errors import ProviderReason, ProviderUnavailable
from app.services.llm.anthropic_client import _status_error
from app.services.llm.base import LLMProvider
from app.services.llm.registry import LLMRouter


def status_error(code: int) -> APIStatusError:
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx.Response(code, request=request)
    return APIStatusError("boom", response=response, body=None)


class TestStatusMapping:
    @pytest.mark.parametrize(
        ("code", "expected"),
        [
            (401, ProviderReason.REJECTED_CREDENTIALS),
            (403, ProviderReason.REJECTED_CREDENTIALS),
            (404, ProviderReason.MODEL_UNAVAILABLE),
            (402, ProviderReason.QUOTA_EXHAUSTED),
            (429, ProviderReason.RATE_LIMITED),
            (500, ProviderReason.UNREACHABLE),
        ],
    )
    def test_each_status_maps_to_its_own_reason(self, code: int, expected: ProviderReason):
        assert _status_error(status_error(code), "claude-opus-5").reason is expected

    def test_an_unknown_model_names_the_model(self):
        error = _status_error(status_error(404), "claude-does-not-exist")
        assert "claude-does-not-exist" in str(error)
        assert "ANTHROPIC_MODEL" in str(error)

    def test_a_rejected_key_names_the_variable(self):
        assert "ANTHROPIC_API_KEY" in str(_status_error(status_error(401), "m"))

    def test_configuration_faults_are_distinguishable_from_outages(self):
        assert ProviderReason.REJECTED_CREDENTIALS.is_configuration
        assert ProviderReason.MODEL_UNAVAILABLE.is_configuration
        assert ProviderReason.NOT_CONFIGURED.is_configuration
        assert not ProviderReason.UNREACHABLE.is_configuration
        assert not ProviderReason.RATE_LIMITED.is_configuration


class Failing(LLMProvider):
    def __init__(self, name: str, error: ProviderUnavailable) -> None:
        self.name = name
        self._error = error

    @property
    def configured(self) -> bool:
        return True

    async def complete_json(self, **kwargs):
        raise self._error

    async def complete_text(self, **kwargs) -> str:
        raise self._error


class TestRouterReporting:
    async def test_a_configuration_fault_wins_over_a_later_outage(self):
        # Failing over to a second provider must not bury the reason the first
        # one failed, which is the only one anybody can act on.
        router = LLMRouter(
            [
                Failing(
                    "anthropic",
                    ProviderUnavailable("key rejected", reason=ProviderReason.REJECTED_CREDENTIALS),
                ),
                Failing(
                    "openai",
                    ProviderUnavailable("host down", reason=ProviderReason.UNREACHABLE),
                ),
            ]
        )
        with pytest.raises(ProviderUnavailable) as caught:
            await router.complete_json(system="s", user="u", schema={"properties": {}})
        assert caught.value.reason is ProviderReason.REJECTED_CREDENTIALS

    async def test_with_no_provider_at_all_it_says_so(self):
        router = LLMRouter([])
        with pytest.raises(ProviderUnavailable) as caught:
            await router.complete_json(system="s", user="u", schema={"properties": {}})
        assert caught.value.reason is ProviderReason.NOT_CONFIGURED

    async def test_transient_failures_report_the_last_one(self):
        router = LLMRouter(
            [
                Failing("a", ProviderUnavailable("a down", reason=ProviderReason.UNREACHABLE)),
                Failing("b", ProviderUnavailable("b limited", reason=ProviderReason.RATE_LIMITED)),
            ]
        )
        with pytest.raises(ProviderUnavailable) as caught:
            await router.complete_json(system="s", user="u", schema={"properties": {}})
        assert caught.value.reason is ProviderReason.RATE_LIMITED


def test_connection_errors_are_not_status_errors():
    # Guards the split: a genuine network failure must not be reported as a
    # configuration problem.
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    assert not isinstance(APIConnectionError(request=request), APIStatusError)
