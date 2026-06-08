"""Live integration tests: actually hit the configured LLM endpoint.

Skipped by default so CI / `python -m unittest discover` stays offline-clean.
Run only when you want to verify the SDK + your .env credentials work:

  set RUN_LIVE_LLM=1
  python -m unittest tests.test_llm_live -v
"""

import asyncio
import json
import os
import unittest

from app.services.agent import call_llm
from app.core.config import settings
from app.core.llm import get_llm_client


_SKIP_REASON = "set RUN_LIVE_LLM=1 to enable real network tests"


@unittest.skipUnless(os.getenv("RUN_LIVE_LLM"), _SKIP_REASON)
class TestLiveLLM(unittest.TestCase):
  """Smoke tests against the LLM provider configured in .env."""

  def test_print_active_config(self):
    """Sanity log: shows which provider/model/base_url is being hit."""
    print(
        f"\n[live-llm] provider={settings.llm_provider!r} "
        f"model={settings.llm_model!r} base_url={settings.llm_base_url!r} "
        f"timeout={settings.llm_timeout}s"
    )
    client = get_llm_client()
    print(f"[live-llm] adapter={type(client).__name__} resolved_model={client.model!r}")

  def test_plain_chat(self):
    """Free-form chat: model must return non-empty text."""
    out = asyncio.run(
        call_llm(
            prompt="请用中文回答：1+1等于几？只回答数字。",
            system="你是一个简洁的助手。",
        )
    )
    print(f"[live-llm] plain_chat => {out!r}")
    self.assertIsInstance(out, str)
    self.assertTrue(out.strip(), "model returned empty text")

  def test_json_schema_chat(self):
    """Structured output: model must return parseable JSON with expected keys."""
    schema = {
        "type": "object",
        "properties": {
            "answer": {"type": "integer", "description": "1+1的结果"},
            "explanation": {"type": "string", "description": "一句话解释"},
        },
        "required": ["answer", "explanation"],
    }
    out = asyncio.run(
        call_llm(
            prompt="计算 1+1，按 JSON 返回 answer 和 explanation 两个字段。",
            json_schema=schema,
        )
    )
    print(f"[live-llm] json_chat raw => {out!r}")
    data = json.loads(out)
    self.assertIn("answer", data)
    self.assertIn("explanation", data)


if __name__ == "__main__":
  unittest.main()
