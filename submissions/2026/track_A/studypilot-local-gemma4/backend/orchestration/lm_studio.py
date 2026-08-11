"""Strict request-scoped client for LM Studio's local HTTP APIs."""

from __future__ import annotations

import ipaddress
from collections.abc import Callable, Mapping, Sequence
from typing import Any, Literal
from urllib.parse import SplitResult, urlsplit, urlunsplit

import httpx
from pydantic import ConfigDict

from backend.config import APPROVED_LM_STUDIO_MODEL, Settings
from backend.contracts.models import StrictModel


ToolChoice = Literal["none", "auto", "required"]


class LMStudioError(RuntimeError):
    """Base error with a stable code and no request content in its message."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class ModelConfigurationError(LMStudioError):
    """The production model target is unsafe or unsupported."""


class ModelUnavailableError(LMStudioError):
    """The configured local model cannot currently serve a request."""


class ModelNotCapableError(LMStudioError):
    """The configured model lacks native tool-use support."""


class ModelProtocolError(LMStudioError):
    """LM Studio returned an invalid or unusable response."""


class ModelMismatchError(ModelProtocolError):
    """A response was produced by a different model id."""


class _FrozenStrictModel(StrictModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        validate_assignment=True,
        frozen=True,
    )


class ModelMetadata(_FrozenStrictModel):
    id: str
    state: str
    capabilities: tuple[str, ...]
    quantization: str | None = None


class AssistantFunctionCall(_FrozenStrictModel):
    name: str
    arguments: str


class AssistantToolCall(_FrozenStrictModel):
    id: str
    type: Literal["function"]
    function: AssistantFunctionCall


class ParsedChatChoice(_FrozenStrictModel):
    content: str | None
    finish_reason: str
    tool_calls: tuple[AssistantToolCall, ...] = ()

    def assistant_message(self) -> dict[str, Any]:
        message: dict[str, Any] = {
            "role": "assistant",
            "content": self.content,
        }
        if self.tool_calls:
            message["tool_calls"] = [
                {
                    "id": call.id,
                    "type": call.type,
                    "function": {
                        "name": call.function.name,
                        "arguments": call.function.arguments,
                    },
                }
                for call in self.tool_calls
            ]
        return message


class ChatCompletionResult(_FrozenStrictModel):
    choice: ParsedChatChoice
    raw_response: dict[str, Any]


class PreflightResult(_FrozenStrictModel):
    metadata: ModelMetadata
    first: ChatCompletionResult
    second: ChatCompletionResult


ClientFactory = Callable[..., httpx.Client]


class LMStudioClient:
    """Stateless client that creates a fresh HTTP client for every request."""

    def __init__(
        self,
        base_url: str,
        model_id: str,
        *,
        timeout: float | httpx.Timeout = 60.0,
        transport: httpx.BaseTransport | None = None,
        client_factory: ClientFactory | None = None,
    ) -> None:
        if transport is not None and client_factory is not None:
            raise ValueError("transport and client_factory are mutually exclusive")
        if (
            transport is None
            and client_factory is None
            and model_id != APPROVED_LM_STUDIO_MODEL
        ):
            raise ModelConfigurationError("unsupported_model_id")
        parsed = _validate_base_url(base_url)
        if (
            transport is None
            and client_factory is None
            and not _is_loopback_hostname(parsed.hostname)
        ):
            raise ModelConfigurationError("remote_model_host_forbidden")
        self.base_url = base_url.rstrip("/")
        self.model_id = model_id
        self.timeout = timeout
        self._transport = transport
        self._client_factory = client_factory
        self._is_production_real_lm = False
        self._server_origin = urlunsplit((parsed.scheme, parsed.netloc, "", "", ""))

    @classmethod
    def from_settings(
        cls,
        settings: Settings,
        *,
        timeout: float | httpx.Timeout = 60.0,
        transport: httpx.BaseTransport | None = None,
        client_factory: ClientFactory | None = None,
    ) -> LMStudioClient:
        if settings.mock_enabled:
            raise ModelConfigurationError("mock_model_forbidden")
        if settings.lm_studio_model != APPROVED_LM_STUDIO_MODEL:
            raise ModelConfigurationError("unsupported_model_id")
        parsed = _validate_base_url(settings.lm_studio_base_url)
        if not _is_loopback_hostname(parsed.hostname):
            raise ModelConfigurationError("remote_model_host_forbidden")
        client = cls(
            settings.lm_studio_base_url,
            settings.lm_studio_model,
            timeout=timeout,
            transport=transport,
            client_factory=client_factory,
        )
        client._is_production_real_lm = transport is None and client_factory is None
        return client

    @property
    def is_production_real_lm(self) -> bool:
        return self._is_production_real_lm

    @property
    def evidence_provenance(self) -> Literal[
        "real_lm_native_fc", "synthetic_transport"
    ]:
        if self._is_production_real_lm:
            return "real_lm_native_fc"
        return "synthetic_transport"

    def chat_completion(
        self,
        messages: Sequence[Mapping[str, Any]],
        tools: Sequence[Mapping[str, Any]],
        tool_choice: ToolChoice,
        *,
        max_tokens: int | None = None,
    ) -> ChatCompletionResult:
        if not isinstance(tool_choice, str) or tool_choice not in {
            "none",
            "auto",
            "required",
        }:
            raise ValueError("tool_choice must be none, auto, or required")
        payload: dict[str, Any] = {
            "model": self.model_id,
            "messages": list(messages),
            "tools": list(tools),
            "tool_choice": tool_choice,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        raw = self._request_json(
            "POST",
            f"{self.base_url}/chat/completions",
            json_payload=payload,
        )
        return ChatCompletionResult(
            choice=_parse_chat_choice(raw, self.model_id),
            raw_response=raw,
        )

    def get_model_metadata(self) -> ModelMetadata:
        raw = self._request_json(
            "GET",
            f"{self._server_origin}/api/v0/models",
            json_payload=None,
        )
        records = raw.get("data")
        if not isinstance(records, list):
            raise ModelProtocolError("malformed_model_metadata")
        record = next(
            (
                candidate
                for candidate in records
                if isinstance(candidate, dict) and candidate.get("id") == self.model_id
            ),
            None,
        )
        if record is None:
            raise ModelUnavailableError("model_not_found")
        state = record.get("state")
        capabilities = record.get("capabilities")
        if not isinstance(state, str) or not isinstance(capabilities, list) or not all(
            isinstance(capability, str) for capability in capabilities
        ):
            raise ModelProtocolError("malformed_model_metadata")
        if state != "loaded":
            raise ModelUnavailableError("model_not_loaded")
        if "tool_use" not in capabilities:
            raise ModelNotCapableError("model_tool_use_missing")
        quantization = record.get("quantization")
        if quantization is not None and not isinstance(quantization, str):
            raise ModelProtocolError("malformed_model_metadata")
        return ModelMetadata(
            id=self.model_id,
            state=state,
            capabilities=tuple(capabilities),
            quantization=quantization,
        )

    def _request_json(
        self,
        method: str,
        url: str,
        *,
        json_payload: dict[str, Any] | None,
    ) -> dict[str, Any]:
        try:
            with self._new_client() as client:
                response = client.request(method, url, json=json_payload)
        except httpx.InvalidURL as error:
            raise ModelConfigurationError("invalid_model_base_url") from error
        except httpx.TimeoutException as error:
            raise ModelUnavailableError("model_timeout") from error
        except httpx.ConnectError as error:
            raise ModelUnavailableError("model_connection_refused") from error
        except httpx.HTTPError as error:
            raise ModelUnavailableError("model_transport_error") from error
        if not 200 <= response.status_code < 300:
            raise ModelUnavailableError("model_http_error")
        try:
            raw = response.json()
        except ValueError as error:
            raise ModelProtocolError("malformed_json_response") from error
        if not isinstance(raw, dict):
            raise ModelProtocolError("malformed_response_envelope")
        return raw

    def _new_client(self) -> httpx.Client:
        client_kwargs = {"timeout": self.timeout, "trust_env": False}
        if self._client_factory is not None:
            return self._client_factory(**client_kwargs)
        return httpx.Client(transport=self._transport, **client_kwargs)


def _parse_chat_choice(raw: dict[str, Any], model_id: str) -> ParsedChatChoice:
    if raw.get("model") != model_id:
        raise ModelMismatchError("model_id_mismatch")
    choices = raw.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ModelProtocolError("missing_choice")
    choice = choices[0]
    if not isinstance(choice, dict):
        raise ModelProtocolError("malformed_choice")
    finish_reason = choice.get("finish_reason")
    message = choice.get("message")
    if not isinstance(finish_reason, str) or not isinstance(message, dict):
        raise ModelProtocolError("malformed_choice")
    if finish_reason == "length":
        raise ModelProtocolError("model_output_truncated")
    if finish_reason not in {"stop", "tool_calls"}:
        raise ModelProtocolError("unsupported_finish_reason")
    content = message.get("content")
    if content is not None and not isinstance(content, str):
        raise ModelProtocolError("malformed_choice")
    raw_calls = message.get("tool_calls", [])
    if not isinstance(raw_calls, list):
        raise ModelProtocolError("invalid_tool_call")
    calls = tuple(_parse_tool_call(item) for item in raw_calls)
    if finish_reason == "tool_calls" and not calls:
        raise ModelProtocolError("invalid_tool_call")
    if finish_reason != "tool_calls" and calls:
        raise ModelProtocolError("unexpected_tool_calls")
    return ParsedChatChoice(
        content=content,
        finish_reason=finish_reason,
        tool_calls=calls,
    )


def _parse_tool_call(raw: object) -> AssistantToolCall:
    if not isinstance(raw, dict):
        raise ModelProtocolError("invalid_tool_call")
    function = raw.get("function")
    if (
        not isinstance(raw.get("id"), str)
        or not raw.get("id")
        or raw.get("type") != "function"
        or not isinstance(function, dict)
        or not isinstance(function.get("name"), str)
        or not function.get("name")
    ):
        raise ModelProtocolError("invalid_tool_call")
    arguments = function.get("arguments")
    if not isinstance(arguments, str):
        raise ModelProtocolError("invalid_tool_arguments_type")
    return AssistantToolCall(
        id=raw["id"],
        type="function",
        function=AssistantFunctionCall(
            name=function["name"],
            arguments=arguments,
        ),
    )


def _validate_base_url(url: str) -> SplitResult:
    try:
        parsed = urlsplit(url)
        port = parsed.port
        httpx.URL(url)
    except (ValueError, httpx.InvalidURL) as error:
        raise ModelConfigurationError("invalid_model_base_url") from error
    if parsed.scheme not in {"http", "https"} or parsed.hostname is None:
        raise ModelConfigurationError("invalid_model_base_url")
    if port is not None and not 1 <= port <= 65_535:
        raise ModelConfigurationError("invalid_model_base_url")
    return parsed


def _is_loopback_hostname(hostname: str | None) -> bool:
    if hostname is None:
        return False
    if hostname.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(hostname).is_loopback
    except ValueError:
        return False
