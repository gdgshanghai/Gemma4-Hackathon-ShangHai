from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import httpx
import pytest

from backend.config import load_settings
from backend.orchestration.lm_studio import (
    LMStudioClient,
    ModelConfigurationError,
    ModelMismatchError,
    ModelNotCapableError,
    ModelProtocolError,
    ModelUnavailableError,
)


MODEL = "gemma-4-26b-a4b-it"
BASE_URL = "http://127.0.0.1:1234/v1"


def _tool_call_response(
    *, content: str | None = None, arguments: object = '{"session_id":"s1"}'
) -> dict[str, object]:
    return {
        "id": "chatcmpl-1",
        "model": MODEL,
        "choices": [
            {
                "index": 0,
                "finish_reason": "tool_calls",
                "message": {
                    "role": "assistant",
                    "content": content,
                    "tool_calls": [
                        {
                            "id": "call-1",
                            "type": "function",
                            "function": {
                                "name": "get_planning_context",
                                "arguments": arguments,
                            },
                        }
                    ],
                },
            }
        ],
    }


def _client(handler: Callable[[httpx.Request], httpx.Response]) -> LMStudioClient:
    return LMStudioClient(
        base_url=BASE_URL,
        model_id=MODEL,
        transport=httpx.MockTransport(handler),
    )


def test_chat_posts_exact_model_payload_and_parses_choice() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=_tool_call_response())

    result = _client(handler).chat_completion(
        messages=[{"role": "user", "content": "probe"}],
        tools=[{"type": "function", "function": {"name": "get_planning_context"}}],
        tool_choice="required",
        max_tokens=64,
    )

    payload = json.loads(seen[0].content)
    assert str(seen[0].url) == f"{BASE_URL}/chat/completions"
    assert payload == {
        "model": MODEL,
        "messages": [{"role": "user", "content": "probe"}],
        "tools": [
            {"type": "function", "function": {"name": "get_planning_context"}}
        ],
        "tool_choice": "required",
        "max_tokens": 64,
    }
    assert result.choice.finish_reason == "tool_calls"
    assert result.choice.content is None
    assert result.choice.tool_calls[0].id == "call-1"
    assert result.choice.tool_calls[0].function.arguments == '{"session_id":"s1"}'
    assert result.raw_response["id"] == "chatcmpl-1"


@pytest.mark.parametrize("content", [None, ""])
def test_empty_or_null_tool_call_content_is_preserved(content: str | None) -> None:
    client = _client(
        lambda _: httpx.Response(200, json=_tool_call_response(content=content))
    )

    result = client.chat_completion([], [], "required")

    assert result.choice.content is content
    assert result.choice.assistant_message() == {
        "role": "assistant",
        "content": content,
        "tool_calls": [
            {
                "id": "call-1",
                "type": "function",
                "function": {
                    "name": "get_planning_context",
                    "arguments": '{"session_id":"s1"}',
                },
            }
        ],
    }


def test_each_request_closes_its_http_client() -> None:
    class ClosingTransport(httpx.BaseTransport):
        def __init__(self) -> None:
            self.close_count = 0

        def handle_request(self, request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=_tool_call_response())

        def close(self) -> None:
            self.close_count += 1

    transport = ClosingTransport()
    client = LMStudioClient(BASE_URL, MODEL, transport=transport)

    client.chat_completion([], [], "required")
    client.chat_completion([], [], "required")

    assert transport.close_count == 2


def test_client_factory_receives_trust_env_false_despite_proxy_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen_kwargs: list[dict[str, object]] = []

    def factory(**kwargs: object) -> httpx.Client:
        seen_kwargs.append(kwargs)
        return httpx.Client(
            transport=httpx.MockTransport(
                lambda _: httpx.Response(200, json=_tool_call_response())
            ),
            **kwargs,  # type: ignore[arg-type]
        )

    monkeypatch.setenv("HTTP_PROXY", "http://proxy.invalid:9999")
    client = LMStudioClient(BASE_URL, MODEL, client_factory=factory)

    client.chat_completion([], [], "required")

    assert seen_kwargs == [{"timeout": 60.0, "trust_env": False}]


def test_injected_transport_client_explicitly_disables_environment_proxy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_client = httpx.Client
    seen_kwargs: list[dict[str, object]] = []

    def recording_client(*args: object, **kwargs: object) -> httpx.Client:
        seen_kwargs.append(kwargs)
        return real_client(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(httpx, "Client", recording_client)
    client = _client(lambda _: httpx.Response(200, json=_tool_call_response()))

    client.chat_completion([], [], "required")

    assert seen_kwargs[0]["trust_env"] is False


def test_metadata_uses_server_origin_and_never_v1_models() -> None:
    urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        urls.append(str(request.url))
        return httpx.Response(
            200,
            json={
                "data": [
                    {
                        "id": MODEL,
                        "state": "loaded",
                        "capabilities": ["tool_use", "vision"],
                        "quantization": "Q4_K_M",
                    }
                ]
            },
        )

    metadata = _client(handler).get_model_metadata()

    assert urls == ["http://127.0.0.1:1234/api/v0/models"]
    assert metadata.id == MODEL
    assert metadata.state == "loaded"
    assert metadata.capabilities == ("tool_use", "vision")
    assert metadata.quantization == "Q4_K_M"


@pytest.mark.parametrize(
    ("record", "error_type", "code"),
    [
        (None, ModelUnavailableError, "model_not_found"),
        (
            {"id": MODEL, "state": "not-loaded", "capabilities": ["tool_use"]},
            ModelUnavailableError,
            "model_not_loaded",
        ),
        (
            {"id": MODEL, "state": "loaded", "capabilities": ["vision"]},
            ModelNotCapableError,
            "model_tool_use_missing",
        ),
    ],
)
def test_metadata_requires_exact_loaded_tool_use_record(
    record: dict[str, object] | None,
    error_type: type[Exception],
    code: str,
) -> None:
    records = ([{"id": "other", "state": "loaded", "capabilities": ["tool_use"]}]
               if record is None else [record])
    client = _client(lambda _: httpx.Response(200, json={"data": records}))

    with pytest.raises(error_type) as raised:
        client.get_model_metadata()

    assert getattr(raised.value, "code") == code


@pytest.mark.parametrize("status", [400, 500])
def test_non_2xx_is_typed_without_prompt_leak(status: int) -> None:
    client = _client(lambda _: httpx.Response(status, text="server detail"))

    with pytest.raises(ModelUnavailableError) as raised:
        client.chat_completion(
            [{"role": "user", "content": "sensitive child prompt"}], [], "none"
        )

    assert raised.value.code == "model_http_error"
    assert "sensitive child prompt" not in str(raised.value)


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (httpx.ConnectError("refused"), "model_connection_refused"),
        (httpx.ReadTimeout("slow"), "model_timeout"),
    ],
)
def test_network_failures_map_to_stable_unavailable_errors(
    error: Exception, code: str
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise error

    with pytest.raises(ModelUnavailableError) as raised:
        _client(handler).chat_completion([], [], "none")

    assert raised.value.code == code


@pytest.mark.parametrize(
    ("body", "code"),
    [
        ({"model": MODEL, "choices": []}, "missing_choice"),
        ({"model": MODEL, "choices": [{}]}, "malformed_choice"),
        (
            _tool_call_response(arguments={"not": "a string"}),
            "invalid_tool_arguments_type",
        ),
        (
            {
                "model": MODEL,
                "choices": [
                    {
                        "finish_reason": "tool_calls",
                        "message": {"role": "assistant", "tool_calls": [{}]},
                    }
                ],
            },
            "invalid_tool_call",
        ),
    ],
)
def test_malformed_envelopes_raise_protocol_error(
    body: dict[str, object], code: str
) -> None:
    with pytest.raises(ModelProtocolError) as raised:
        _client(lambda _: httpx.Response(200, json=body)).chat_completion([], [], "auto")

    assert raised.value.code == code


def test_length_finish_reason_is_explicit_failure() -> None:
    body = {
        "model": MODEL,
        "choices": [
            {
                "finish_reason": "length",
                "message": {"role": "assistant", "content": "partial"},
            }
        ],
    }

    with pytest.raises(ModelProtocolError) as raised:
        _client(lambda _: httpx.Response(200, json=body)).chat_completion([], [], "none")

    assert raised.value.code == "model_output_truncated"


@pytest.mark.parametrize(
    ("finish_reason", "include_calls", "expected_code"),
    [
        ("tool_calls", False, "invalid_tool_call"),
        ("stop", True, "unexpected_tool_calls"),
        ("content_filter", False, "unsupported_finish_reason"),
        ("length", False, "model_output_truncated"),
        ("length", True, "model_output_truncated"),
    ],
)
def test_finish_reason_tool_call_matrix_rejects_invalid_combinations(
    finish_reason: str,
    include_calls: bool,
    expected_code: str,
) -> None:
    body = _tool_call_response()
    choice = body["choices"][0]  # type: ignore[index]
    choice["finish_reason"] = finish_reason  # type: ignore[index]
    if not include_calls:
        choice["message"] = {  # type: ignore[index]
            "role": "assistant",
            "content": "terminal content",
        }

    with pytest.raises(ModelProtocolError) as raised:
        _client(lambda _: httpx.Response(200, json=body)).chat_completion(
            [], [], "auto"
        )

    assert raised.value.code == expected_code


@pytest.mark.parametrize("content", [None, ""])
def test_finish_reason_tool_call_matrix_accepts_real_calls_with_empty_content(
    content: str | None,
) -> None:
    result = _client(
        lambda _: httpx.Response(200, json=_tool_call_response(content=content))
    ).chat_completion([], [], "required")

    assert result.choice.finish_reason == "tool_calls"
    assert result.choice.content is content
    assert len(result.choice.tool_calls) == 1


def test_response_model_must_match_exact_configured_id() -> None:
    body = _tool_call_response()
    body["model"] = "different-model"

    with pytest.raises(ModelMismatchError) as raised:
        _client(lambda _: httpx.Response(200, json=body)).chat_completion([], [], "auto")

    assert raised.value.code == "model_id_mismatch"


def test_named_tool_choice_object_is_rejected_before_transport() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json=_tool_call_response())

    with pytest.raises(ValueError, match="tool_choice"):
        _client(handler).chat_completion(
            [],
            [],
            {"type": "function", "function": {"name": "get_planning_context"}},  # type: ignore[arg-type]
        )

    assert calls == 0


def test_direct_runtime_construction_rejects_remote_without_test_injection() -> None:
    with pytest.raises(ModelConfigurationError) as raised:
        LMStudioClient("http://example.com:1234/v1", MODEL)

    assert raised.value.code == "remote_model_host_forbidden"


def test_direct_remote_construction_remains_available_with_test_transport() -> None:
    client = LMStudioClient(
        "http://unit-test.invalid/v1",
        MODEL,
        transport=httpx.MockTransport(
            lambda _: httpx.Response(200, json=_tool_call_response())
        ),
    )

    assert client.chat_completion([], [], "required").choice.tool_calls[0].id == (
        "call-1"
    )


def test_client_tracks_production_real_versus_injected_transport(
    tmp_path: Path,
) -> None:
    production = LMStudioClient.from_settings(
        load_settings(project_root=tmp_path, environ={})
    )
    injected_transport = _client(
        lambda _: httpx.Response(200, json=_tool_call_response())
    )
    injected_factory = LMStudioClient(
        BASE_URL,
        MODEL,
        client_factory=lambda **kwargs: httpx.Client(
            transport=httpx.MockTransport(
                lambda _: httpx.Response(200, json=_tool_call_response())
            ),
            **kwargs,
        ),
    )

    assert production.is_production_real_lm is True
    assert production.evidence_provenance == "real_lm_native_fc"
    assert injected_transport.is_production_real_lm is False
    assert injected_transport.evidence_provenance == "synthetic_transport"
    assert injected_factory.is_production_real_lm is False
    assert injected_factory.evidence_provenance == "synthetic_transport"


def test_from_settings_rejects_nonapproved_model_before_transport(tmp_path: Path) -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(500)

    settings = load_settings(
        project_root=tmp_path,
        environ={"V13_LM_STUDIO_MODEL": "other-local-model"},
    )

    with pytest.raises(ModelConfigurationError) as raised:
        LMStudioClient.from_settings(
            settings, transport=httpx.MockTransport(handler)
        )

    assert raised.value.code == "unsupported_model_id"
    assert calls == 0


@pytest.mark.parametrize(
    "invalid_url",
    [
        "http://127.0.0.1:0/v1",
        "http://127.0.0.1:65536/v1",
        "http://127.0.0.1:99999/v1",
        "http://[::1/v1",
    ],
)
def test_invalid_base_url_is_rejected_during_construction(
    invalid_url: str,
) -> None:
    with pytest.raises(ModelConfigurationError) as raised:
        LMStudioClient(
            invalid_url,
            MODEL,
            transport=httpx.MockTransport(lambda _: httpx.Response(500)),
        )

    assert raised.value.code == "invalid_model_base_url"
