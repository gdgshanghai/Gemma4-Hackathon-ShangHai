"""Unit tests for the LLM strategy/factory layer."""

import asyncio
import unittest
from typing import Any
from unittest.mock import AsyncMock, patch

from app.core.llm.parsing import (
    LLMOutputFormatError,
    parse_json_object,
    strip_text_artifacts,
    validate_against_schema,
)
from app.core.llm.schema import to_gemini_schema


class TestSchemaNormalization(unittest.TestCase):
  def test_lowercase_to_uppercase_for_gemini(self):
    src = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "count": {"type": "integer"},
            "tags": {"type": "array", "items": {"type": "string"}},
        },
    }
    out = to_gemini_schema(src)
    self.assertEqual(out["type"], "OBJECT")
    self.assertEqual(out["properties"]["name"]["type"], "STRING")
    self.assertEqual(out["properties"]["count"]["type"], "INTEGER")
    self.assertEqual(out["properties"]["tags"]["type"], "ARRAY")
    self.assertEqual(out["properties"]["tags"]["items"]["type"], "STRING")
    self.assertEqual(src["type"], "object")  # original untouched


class TestFactoryDispatch(unittest.TestCase):
  def setUp(self):
    from app.core.llm import factory
    self.factory = factory
    self.factory.reset_llm_client_cache()

  def tearDown(self):
    self.factory.reset_llm_client_cache()

  def _patch_settings(self, **overrides):
    return patch.multiple(self.factory.settings, **overrides)

  def test_gemini_builds_gemini_adapter(self):
    from app.core.llm.providers.gemini import GeminiAdapter
    with self._patch_settings(
        llm_provider="gemini",
        llm_api_key="fake-key",
        llm_model=None,
        llm_base_url=None,
    ), patch.object(GeminiAdapter, "__init__", return_value=None):
      client = self.factory._build_client()
      self.assertIsInstance(client._inner, GeminiAdapter)

  def test_openai_with_custom_base_url_works_for_qwen(self):
    from app.core.llm.providers.openai_like import OpenAICompatibleAdapter
    captured = {}

    def fake_init(self, **kwargs):
      captured.update(kwargs)

    with self._patch_settings(
        llm_provider="openai",
        llm_api_key="sk-qwen",
        llm_model="qwen-plus",
        llm_base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    ), patch.object(OpenAICompatibleAdapter, "__init__", fake_init):
      client = self.factory._build_client()
      self.assertIsInstance(client._inner, OpenAICompatibleAdapter)

    self.assertEqual(captured["api_key"], "sk-qwen")
    self.assertEqual(captured["model"], "qwen-plus")
    self.assertEqual(
        captured["base_url"],
        "https://dashscope.aliyuncs.com/compatible-mode/v1",
    )

  def test_anthropic_builds_anthropic_adapter(self):
    from app.core.llm.providers.anthropic import AnthropicAdapter
    with self._patch_settings(
        llm_provider="anthropic", llm_api_key="sk-ant"
    ), patch.object(AnthropicAdapter, "__init__", return_value=None):
      client = self.factory._build_client()
      self.assertIsInstance(client._inner, AnthropicAdapter)

  def test_unknown_provider_raises(self):
    from app.core.llm.base import LLMProviderError
    with self._patch_settings(llm_provider="bogus", llm_api_key="x"):
      with self.assertRaises(LLMProviderError):
        self.factory._build_client()

  def test_missing_key_raises_unless_base_url_set(self):
    from app.core.llm.base import LLMProviderError
    with self._patch_settings(
        llm_provider="openai",
        llm_api_key=None,
        llm_base_url=None,
    ):
      with self.assertRaises(LLMProviderError):
        self.factory._build_client()

  def test_ollama_via_base_url_needs_no_key(self):
    from app.core.llm.providers.openai_like import OpenAICompatibleAdapter
    captured = {}

    def fake_init(self, **kwargs):
      captured.update(kwargs)

    with self._patch_settings(
        llm_provider="openai",
        llm_api_key=None,
        llm_base_url="http://localhost:11434/v1",
        llm_model="llama3.2",
    ), patch.object(OpenAICompatibleAdapter, "__init__", fake_init):
      self.factory._build_client()

    self.assertTrue(captured["api_key"])  # placeholder filled
    self.assertEqual(captured["base_url"], "http://localhost:11434/v1")

  def test_get_llm_client_caches_singleton(self):
    from app.core.llm.providers.gemini import GeminiAdapter
    with self._patch_settings(
        llm_provider="gemini", llm_api_key="fake"
    ), patch.object(GeminiAdapter, "__init__", return_value=None):
      first = self.factory.get_llm_client()
      second = self.factory.get_llm_client()
    self.assertIs(first, second)

  def test_provider_name_is_case_insensitive(self):
    from app.core.llm.providers.gemini import GeminiAdapter
    with self._patch_settings(
        llm_provider="Gemini", llm_api_key="fake"
    ), patch.object(GeminiAdapter, "__init__", return_value=None):
      client = self.factory.get_llm_client()
    self.assertIsInstance(client._inner, GeminiAdapter)


class TestCallLLMWiring(unittest.TestCase):
  def test_call_llm_invokes_client_chat(self):
    from app.services import agent
    from app.services.agents import llm_io

    mock_client = AsyncMock()
    mock_client.chat = AsyncMock(return_value="hello world")

    with patch.object(llm_io, "get_llm_client", return_value=mock_client):
      result = asyncio.run(
          agent.call_llm(prompt="hi", system="be brief", json_schema=None)
      )

    self.assertEqual(result, "hello world")
    mock_client.chat.assert_awaited_once_with(
        prompt="hi", system="be brief", json_schema=None
    )


class TestParseJsonObject(unittest.TestCase):
  def test_plain_object(self):
    self.assertEqual(parse_json_object('{"a": 1}'), {"a": 1})

  def test_strips_markdown_code_fence(self):
    raw = "```json\n{\"a\": 1}\n```"
    self.assertEqual(parse_json_object(raw), {"a": 1})

  def test_double_encoded_string(self):
    inner = '{"a": 1}'
    outer = '"{\\"a\\": 1}"'  # JSON string whose body is a JSON object
    # Sanity: outer parses to inner string, inner parses to dict.
    import json as _json
    self.assertEqual(_json.loads(outer), inner)
    self.assertEqual(parse_json_object(outer), {"a": 1})

  def test_extracts_first_object_from_noise(self):
    raw = "sure, here you go:\n{\"a\": 1}\nthanks!"
    self.assertEqual(parse_json_object(raw), {"a": 1})

  def test_rejects_non_object_top_level(self):
    with self.assertRaises(LLMOutputFormatError):
      parse_json_object("[1, 2, 3]")

  def test_rejects_empty(self):
    with self.assertRaises(LLMOutputFormatError):
      parse_json_object("   ")

  def test_rejects_garbage(self):
    with self.assertRaises(LLMOutputFormatError):
      parse_json_object("not json at all")


class TestChatJsonDefault(unittest.TestCase):
  """The base ``chat_json`` should delegate to ``chat`` then parse."""

  def _make_client(self, raw_response: str):
    from app.core.llm.base import LLMClient

    class _StubClient(LLMClient):
      provider_name = "stub"

      async def chat(self, prompt, system=None, json_schema=None):
        return raw_response

    return _StubClient()

  def test_returns_dict_for_plain_json(self):
    client = self._make_client('{"ok": true}')
    result = asyncio.run(client.chat_json(prompt="x"))
    self.assertEqual(result, {"ok": True})

  def test_unwraps_double_encoded(self):
    client = self._make_client('"{\\"ok\\": true}"')
    result = asyncio.run(client.chat_json(prompt="x"))
    self.assertEqual(result, {"ok": True})

  def test_raises_format_error_on_garbage(self):
    client = self._make_client("definitely not json")
    with self.assertRaises(LLMOutputFormatError):
      asyncio.run(client.chat_json(prompt="x"))


class TestValidateAgainstSchema(unittest.TestCase):
  """``validate_against_schema`` enforces declared LLM output contracts."""

  _schema = {
      "type": "object",
      "properties": {
          "title": {"type": "string"},
          "tags": {"type": "array", "items": {"type": "string"}},
      },
      "required": ["title", "tags"],
  }

  def test_accepts_valid_payload(self):
    validate_against_schema({"title": "x", "tags": ["a"]}, self._schema)

  def test_rejects_missing_required(self):
    with self.assertRaises(LLMOutputFormatError):
      validate_against_schema({"title": "x"}, self._schema)

  def test_rejects_wrong_type(self):
    with self.assertRaises(LLMOutputFormatError):
      validate_against_schema({"title": 1, "tags": ["a"]}, self._schema)

  def test_rejects_nested_type_mismatch(self):
    with self.assertRaises(LLMOutputFormatError):
      validate_against_schema({"title": "x", "tags": [1, 2]}, self._schema)


class TestChatJsonSchemaEnforcement(unittest.TestCase):
  """chat_json must enforce json_schema when supplied (LSP across adapters)."""

  def _make_client(self, raw: str):
    from app.core.llm.base import LLMClient

    class _StubClient(LLMClient):
      provider_name = "stub"

      async def chat(self, prompt, system=None, json_schema=None):
        return raw

    return _StubClient()

  _schema = {
      "type": "object",
      "properties": {"a": {"type": "integer"}},
      "required": ["a"],
  }

  def test_passes_when_payload_matches_schema(self):
    client = self._make_client('{"a": 1}')
    result = asyncio.run(client.chat_json(prompt="x", json_schema=self._schema))
    self.assertEqual(result, {"a": 1})

  def test_raises_when_payload_violates_schema(self):
    client = self._make_client('{"a": "not-int"}')
    with self.assertRaises(LLMOutputFormatError):
      asyncio.run(client.chat_json(prompt="x", json_schema=self._schema))

  def test_no_schema_means_no_validation(self):
    client = self._make_client('{"anything": "goes"}')
    result = asyncio.run(client.chat_json(prompt="x"))
    self.assertEqual(result, {"anything": "goes"})


class TestStripTextArtifacts(unittest.TestCase):
  """``strip_text_artifacts`` normalises free-form LLM replies."""

  def test_empty_returns_empty(self):
    self.assertEqual(strip_text_artifacts(None), "")
    self.assertEqual(strip_text_artifacts("   "), "")

  def test_strips_code_fence(self):
    self.assertEqual(strip_text_artifacts("```text\nhello\n```"), "hello")
    self.assertEqual(strip_text_artifacts("```\nhi\n```"), "hi")

  def test_collapses_runs_and_blank_lines(self):
    self.assertEqual(
        strip_text_artifacts("foo   bar\n\n\n\nbaz"),
        "foo bar\n\nbaz",
    )

  def test_preserves_plain_text(self):
    self.assertEqual(strip_text_artifacts("hello world"), "hello world")


class TestOpenAIAdapterSchemaInjection(unittest.TestCase):
  """OpenAICompatibleAdapter must inject schema text AND pick the right response_format."""

  _schema = {
      "type": "object",
      "properties": {
          "status": {"type": "string", "enum": ["success", "fail"]},
          "feedback": {"type": "string"},
      },
      "required": ["status", "feedback"],
  }

  def _build_adapter(self, base_url: str | None):
    from app.core.llm.providers.openai_like import OpenAICompatibleAdapter

    captured: dict[str, Any] = {}

    class _FakeChoice:
      def __init__(self):
        self.message = type("M", (), {"content": '{"status":"success","feedback":"ok"}'})()

    class _FakeResp:
      choices = [_FakeChoice()]

    class _FakeCompletions:
      async def create(self, **kwargs):
        captured["kwargs"] = kwargs
        return _FakeResp()

    class _FakeChat:
      completions = _FakeCompletions()

    class _FakeClient:
      chat = _FakeChat()

    adapter = OpenAICompatibleAdapter.__new__(OpenAICompatibleAdapter)
    adapter.model = "test-model"
    adapter.timeout = 30
    adapter.base_url = base_url
    adapter._client = _FakeClient()
    return adapter, captured

  def test_dashscope_uses_json_schema_strict_mode(self):
    from unittest.mock import patch
    adapter, captured = self._build_adapter(
        "https://dashscope.aliyuncs.com/compatible-mode/v1"
    )
    with patch("app.core.llm.providers.openai_like.settings") as mock_settings:
      mock_settings.llm_use_json_schema_response_format = None
      asyncio.run(adapter.chat(prompt="hi", json_schema=self._schema))
    rf = captured["kwargs"]["response_format"]
    self.assertEqual(rf["type"], "json_schema")
    self.assertEqual(rf["json_schema"]["schema"], self._schema)
    self.assertTrue(rf["json_schema"]["strict"])

  def test_ollama_falls_back_to_json_object(self):
    from unittest.mock import patch
    adapter, captured = self._build_adapter("http://localhost:11434/v1")
    with patch("app.core.llm.providers.openai_like.settings") as mock_settings:
      mock_settings.llm_use_json_schema_response_format = None
      asyncio.run(adapter.chat(prompt="hi", json_schema=self._schema))
    self.assertEqual(captured["kwargs"]["response_format"], {"type": "json_object"})

  def test_override_setting_forces_choice(self):
    from unittest.mock import patch
    adapter, captured = self._build_adapter("http://localhost:11434/v1")
    with patch("app.core.llm.providers.openai_like.settings") as mock_settings:
      mock_settings.llm_use_json_schema_response_format = True
      asyncio.run(adapter.chat(prompt="hi", json_schema=self._schema))
    self.assertEqual(captured["kwargs"]["response_format"]["type"], "json_schema")

  def test_schema_hint_injected_into_user_message(self):
    from unittest.mock import patch
    adapter, captured = self._build_adapter(
        "https://dashscope.aliyuncs.com/compatible-mode/v1"
    )
    with patch("app.core.llm.providers.openai_like.settings") as mock_settings:
      mock_settings.llm_use_json_schema_response_format = None
      asyncio.run(adapter.chat(prompt="my-task", json_schema=self._schema))
    user_msg = captured["kwargs"]["messages"][-1]["content"]
    self.assertIn("my-task", user_msg)
    self.assertIn("status", user_msg)
    self.assertIn("feedback", user_msg)
    self.assertIn("JSON", user_msg)


class TestOpenAIAdapterExceptionHandling(unittest.TestCase):
  """Strict→loose fallback must trigger ONLY on BadRequestError, not on timeouts."""

  _schema = {
      "type": "object",
      "properties": {"status": {"type": "string"}},
      "required": ["status"],
  }

  def _build_adapter_with_side_effects(self, base_url, side_effects):
    from app.core.llm.providers.openai_like import OpenAICompatibleAdapter

    call_log: list[dict] = []

    class _FakeChoice:
      def __init__(self, text):
        self.message = type("M", (), {"content": text})()

    class _FakeResp:
      def __init__(self, text):
        self.choices = [_FakeChoice(text)]

    class _FakeCompletions:
      async def create(self, **kwargs):
        call_log.append(kwargs)
        effect = side_effects[len(call_log) - 1]
        if isinstance(effect, Exception):
          raise effect
        return _FakeResp(effect)

    class _FakeChat:
      completions = _FakeCompletions()

    class _FakeClient:
      chat = _FakeChat()

    adapter = OpenAICompatibleAdapter.__new__(OpenAICompatibleAdapter)
    adapter.model = "test-model"
    adapter.timeout = 30
    adapter.base_url = base_url
    adapter._client = _FakeClient()
    return adapter, call_log

  def test_timeout_not_treated_as_strict_rejection(self):
    """APITimeoutError must surface as LLMProviderError without a fallback retry."""
    from unittest.mock import patch
    import openai
    from app.core.llm.base import LLMProviderError

    err = openai.APITimeoutError(request=None)
    adapter, call_log = self._build_adapter_with_side_effects(
        "https://dashscope.aliyuncs.com/compatible-mode/v1",
        [err],
    )
    with patch("app.core.llm.providers.openai_like.settings") as mock_settings:
      mock_settings.llm_use_json_schema_response_format = None
      with self.assertRaises(LLMProviderError):
        asyncio.run(adapter.chat(prompt="hi", json_schema=self._schema))

    # Critical: exactly one upstream call. No silent fallback retry.
    self.assertEqual(len(call_log), 1)
    self.assertEqual(call_log[0]["response_format"]["type"], "json_schema")

  def test_bad_request_falls_back_to_json_object(self):
    """BadRequestError on strict mode triggers one looser retry with a warning."""
    from unittest.mock import patch
    import openai

    # openai.BadRequestError needs a response argument; mimic minimally.
    class _FakeResp:
      status_code = 400
      headers = {}
      request = None
    err = openai.BadRequestError(
        message="response_format type not supported",
        response=_FakeResp(),  # type: ignore[arg-type]
        body=None,
    )
    adapter, call_log = self._build_adapter_with_side_effects(
        "https://dashscope.aliyuncs.com/compatible-mode/v1",
        [err, '{"status":"success"}'],
    )
    with patch("app.core.llm.providers.openai_like.settings") as mock_settings, \
         self.assertLogs("app.core.llm.providers.openai_like", level="WARNING") as captured_logs:
      mock_settings.llm_use_json_schema_response_format = None
      result = asyncio.run(adapter.chat(prompt="hi", json_schema=self._schema))

    self.assertEqual(result, '{"status":"success"}')
    self.assertEqual(len(call_log), 2)
    self.assertEqual(call_log[0]["response_format"]["type"], "json_schema")
    self.assertEqual(call_log[1]["response_format"], {"type": "json_object"})
    self.assertTrue(
        any("strict json_schema rejected" in line for line in captured_logs.output),
        captured_logs.output,
    )


class TestCallLLMJsonSchemaRetry(unittest.TestCase):
  """call_llm_json retries once on schema-violation when enabled."""

  _schema = {
      "type": "object",
      "properties": {"status": {"type": "string"}},
      "required": ["status"],
  }

  def test_retries_once_with_error_hint_then_succeeds(self):
    from app.services import agent
    from app.services.agents import llm_io
    from app.core.llm.parsing import LLMOutputFormatError

    mock_client = AsyncMock()
    mock_client.chat_json = AsyncMock(side_effect=[
        LLMOutputFormatError("schema violation at <root>: 'status' is a required property"),
        {"status": "success"},
    ])

    with patch.object(llm_io, "get_llm_client", return_value=mock_client), \
         patch.object(agent.settings, "llm_retry_on_schema_violation", True), \
         patch.object(agent.settings, "llm_retry_on_timeout", False):
      result = asyncio.run(
          agent.call_llm_json(prompt="orig", json_schema=self._schema)
      )

    self.assertEqual(result, {"status": "success"})
    self.assertEqual(mock_client.chat_json.await_count, 2)
    second_prompt = mock_client.chat_json.await_args_list[1].kwargs["prompt"]
    self.assertIn("orig", second_prompt)
    self.assertIn("schema violation", second_prompt.lower())

  def test_no_retry_when_disabled(self):
    from app.services import agent
    from app.services.agents import llm_io
    from app.core.llm.parsing import LLMOutputFormatError

    mock_client = AsyncMock()
    mock_client.chat_json = AsyncMock(
        side_effect=LLMOutputFormatError("schema violation at <root>: missing 'status'")
    )

    with patch.object(llm_io, "get_llm_client", return_value=mock_client), \
         patch.object(agent.settings, "llm_retry_on_schema_violation", False), \
         patch.object(agent.settings, "llm_retry_on_timeout", False):
      with self.assertRaises(LLMOutputFormatError):
        asyncio.run(agent.call_llm_json(prompt="x", json_schema=self._schema))

    self.assertEqual(mock_client.chat_json.await_count, 1)

  def test_only_one_schema_retry_then_raises(self):
    from app.services import agent
    from app.services.agents import llm_io
    from app.core.llm.parsing import LLMOutputFormatError

    mock_client = AsyncMock()
    mock_client.chat_json = AsyncMock(
        side_effect=LLMOutputFormatError("schema violation at <root>: missing 'status'")
    )

    with patch.object(llm_io, "get_llm_client", return_value=mock_client), \
         patch.object(agent.settings, "llm_retry_on_schema_violation", True), \
         patch.object(agent.settings, "llm_retry_on_timeout", False):
      with self.assertRaises(LLMOutputFormatError):
        asyncio.run(agent.call_llm_json(prompt="x", json_schema=self._schema))

    self.assertEqual(mock_client.chat_json.await_count, 2)


if __name__ == "__main__":
  unittest.main()
