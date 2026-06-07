"""Tests for branch tree generation — Phase 3 debug infrastructure."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


# ═══════════════════════════════════════════════════════════
# Unit: _clean_json
# ═══════════════════════════════════════════════════════════

class TestCleanJson:
    def test_plain_json(self):
        from app.services.branch_generator import _clean_json

        result = _clean_json('{"foo": 1}')
        assert result == '{"foo": 1}'

    def test_markdown_fence(self):
        from app.services.branch_generator import _clean_json

        raw = '```json\n{"x": 42}\n```'
        result = _clean_json(raw)
        assert result == '{"x": 42}'

    def test_thought_tags(self):
        from app.services.branch_generator import _clean_json

        raw = '<thought>Let me think...</thought>\n{"ok": true}'
        result = _clean_json(raw)
        assert '"ok": true' in result

    def test_thinking_tags_case_insensitive(self):
        from app.services.branch_generator import _clean_json

        raw = '<THINKING>hmm</THINKING>\n{"a": 1}'
        result = _clean_json(raw)
        assert '"a": 1' in result

    def test_text_before_and_after_json(self):
        from app.services.branch_generator import _clean_json

        raw = 'Here is the JSON:\n{"key": "val"}\nThat is all.'
        result = _clean_json(raw)
        assert result == '{"key": "val"}'

    def test_multiple_json_blocks_picks_largest(self):
        from app.services.branch_generator import _clean_json

        raw = '{"a":1} and {"bbbbbb": 222222}'
        result = _clean_json(raw)
        assert '"bbbbbb"' in result

    def test_empty_input(self):
        from app.services.branch_generator import _clean_json

        assert _clean_json("") == ""
        assert _clean_json("   ") == ""
        assert _clean_json("no braces here") == "no braces here"

    def test_nested_braces(self):
        from app.services.branch_generator import _clean_json

        raw = '{"outer": {"inner": [1,2,3]}, "x": {"y": {"z": "deep"}}}'
        result = _clean_json(raw)
        assert '"deep"' in result

    def test_real_gemma_like_output(self):
        """Simulates a typical Gemma output: thought tags + markdown + JSON."""
        from app.services.branch_generator import _clean_json

        raw = """<thought>Okay, let me analyze this slide. It shows a bar chart
with Q1-Q4 revenue data. I will generate multiple speaking paths.</thought>

```json
{
  "branches": [
    {
      "branch_id": "b1",
      "predicted_text": "Let's look at our Q4 performance...",
      "action": {"type": "highlight", "bbox_1000": [100, 200, 400, 600], "duration_ms": 3000},
      "teleprompter": "Q4 highlight",
      "next_branches": []
    }
  ]
}
```

That covers the main speaking paths for this slide."""

        result = _clean_json(raw)
        assert "b1" in result
        assert "branches" in result
        assert "Q4 performance" in result
        # Should not contain thought content or markdown
        assert "thought>" not in result
        assert "```" not in result
        assert "bar chart" not in result  # from the <thought> block

    def test_unbalanced_braces_returns_text(self):
        from app.services.branch_generator import _clean_json

        raw = '{"a": {"b": "c"}'
        # No fully balanced (depth 0→0) block, falls back to original text
        result = _clean_json(raw)
        assert result == raw


# ═══════════════════════════════════════════════════════════
# Unit: _parse_branch_node
# ═══════════════════════════════════════════════════════════

class TestParseBranchNode:
    def test_valid_highlight_node(self):
        from app.services.branch_generator import _parse_branch_node
        from app.schemas.live import BranchActionType

        raw = {
            "branch_id": "b1",
            "predicted_text": "Our revenue grew 35%.",
            "action": {
                "type": "highlight",
                "bbox_1000": [100, 200, 300, 400],
                "duration_ms": 5000,
            },
            "teleprompter": "Revenue +35%",
            "next_branches": [],
        }
        node = _parse_branch_node(raw)
        assert node.branch_id == "b1"
        assert node.predicted_text == "Our revenue grew 35%."
        assert node.action.type == BranchActionType.HIGHLIGHT
        assert node.action.bbox_1000 == [100, 200, 300, 400]
        assert node.action.duration_ms == 5000
        assert node.teleprompter == "Revenue +35%"
        assert node.next_branches == []

    def test_unknown_action_type_falls_back_to_none(self):
        from app.services.branch_generator import _parse_branch_node
        from app.schemas.live import BranchActionType

        raw = {
            "branch_id": "b2",
            "predicted_text": "Something",
            "action": {"type": "laser_beam", "bbox_1000": [0, 0, 500, 500]},
            "next_branches": [],
        }
        node = _parse_branch_node(raw)
        assert node.action.type == BranchActionType.NONE

    def test_missing_action_defaults(self):
        from app.services.branch_generator import _parse_branch_node
        from app.schemas.live import BranchActionType

        raw = {
            "branch_id": "b3",
            "predicted_text": "Minimal node",
        }
        node = _parse_branch_node(raw)
        assert node.action.type == BranchActionType.NONE
        assert node.action.bbox_1000 == []
        assert node.teleprompter == "Minimal node"  # falls back to predicted_text

    def test_recursive_children(self):
        from app.services.branch_generator import _parse_branch_node

        raw = {
            "branch_id": "root",
            "predicted_text": "Root",
            "action": {"type": "none"},
            "next_branches": [
                {
                    "branch_id": "child",
                    "predicted_text": "Child",
                    "action": {"type": "circle", "bbox_1000": [10, 20, 30, 40]},
                    "next_branches": [
                        {
                            "branch_id": "grandchild",
                            "predicted_text": "Grandchild",
                            "action": {"type": "transition"},
                            "next_branches": [],
                        }
                    ],
                }
            ],
        }
        root = _parse_branch_node(raw)
        assert len(root.next_branches) == 1
        child = root.next_branches[0]
        assert child.branch_id == "child"
        assert len(child.next_branches) == 1
        gc = child.next_branches[0]
        assert gc.branch_id == "grandchild"


# ═══════════════════════════════════════════════════════════
# Unit: _trim_depth
# ═══════════════════════════════════════════════════════════

class TestTrimDepth:
    @staticmethod
    def _make_node(bid: str, children: list = None):  # type: ignore[no-untyped-def]
        from app.services.branch_generator import BranchNode
        from app.schemas.live import BranchAction, BranchActionType

        return BranchNode(
            branch_id=bid,
            predicted_text=f"Text for {bid}",
            action=BranchAction(type=BranchActionType.NONE),
            teleprompter="",
            next_branches=children or [],
        )

    def test_depth_1_keeps_only_top(self):
        from app.services.branch_generator import _trim_depth

        tree = [
            self._make_node("a", [self._make_node("a1"), self._make_node("a2")]),
            self._make_node("b", [self._make_node("b1")]),
        ]
        result = _trim_depth(tree, 1)
        assert len(result) == 2
        assert all(len(n.next_branches) == 0 for n in result)

    def test_depth_2_keeps_children_only(self):
        from app.services.branch_generator import _trim_depth

        tree = [
            self._make_node("a", [
                self._make_node("a1", [self._make_node("a1x")]),
                self._make_node("a2"),
            ]),
        ]
        result = _trim_depth(tree, 2)
        a = result[0]
        assert len(a.next_branches) == 2
        for child in a.next_branches:
            assert len(child.next_branches) == 0

    def test_depth_3_keeps_full_tree(self):
        from app.services.branch_generator import _trim_depth

        tree = [
            self._make_node("a", [
                self._make_node("a1", [self._make_node("a1x")]),
            ]),
        ]
        result = _trim_depth(tree, 3)
        gc = result[0].next_branches[0].next_branches[0]
        assert gc.branch_id == "a1x"


# ═══════════════════════════════════════════════════════════
# Integration: /api/v1/branches endpoint
# ═══════════════════════════════════════════════════════════

class TestBranchesEndpoint:
    def test_missing_parse_id(self):
        """404 when parse_id is not in cache."""
        resp = client.post(
            "/api/v1/branches",
            json={"parse_id": "nonexistent", "slide_index": 0, "max_depth": 3},
        )
        assert resp.status_code == 404
        assert "parse cache" in resp.json()["detail"].lower()

    def test_slide_index_out_of_range(self, monkeypatch):
        """400 when slide_index is beyond the slide count."""
        from app.api.v1.live import routes as live_routes
        from app.schemas.pptx import SlideImage, SlideResult

        slides = [
            SlideResult(
                slide_index=0,
                slide_id=None,
                slide_width_emu=9144000,
                slide_height_emu=6858000,
                image=SlideImage(width_px=960, height_px=540, image_base64="data:image/png;base64,abc"),
                elements=[],
                warnings=[],
            )
        ]
        monkeypatch.setattr(live_routes.ParseCache, "get", lambda _pid: slides)

        resp = client.post(
            "/api/v1/branches",
            json={"parse_id": "test", "slide_index": 99, "max_depth": 3},
        )
        assert resp.status_code == 400
        assert "out of range" in resp.json()["detail"]

    def test_slide_has_no_image(self, monkeypatch):
        """400 when the selected slide has no image data."""
        from app.api.v1.live import routes as live_routes
        from app.schemas.pptx import SlideResult

        slides = [
            SlideResult(
                slide_index=0,
                slide_id=None,
                slide_width_emu=9144000,
                slide_height_emu=6858000,
                image=None,  # no image
                elements=[],
                warnings=[],
            )
        ]
        monkeypatch.setattr(live_routes.ParseCache, "get", lambda _pid: slides)

        resp = client.post(
            "/api/v1/branches",
            json={"parse_id": "test", "slide_index": 0, "max_depth": 3},
        )
        assert resp.status_code == 400
        assert "no image" in resp.json()["detail"].lower()

    def test_generate_success(self, monkeypatch):
        """200 with branches when generation succeeds."""
        from app.api.v1.live import routes as live_routes
        from app.schemas.live import (
            BranchAction,
            BranchActionType,
            BranchNode,
            BranchTreeResponse,
        )
        from app.schemas.pptx import SlideImage, SlideResult

        slides = [
            SlideResult(
                slide_index=0,
                slide_id=None,
                slide_width_emu=9144000,
                slide_height_emu=6858000,
                image=SlideImage(width_px=960, height_px=540, image_base64="data:image/png;base64,abc"),
                elements=[],
                warnings=[],
            )
        ]
        monkeypatch.setattr(live_routes.ParseCache, "get", lambda _pid: slides)

        async def fake_generate(
            self,
            slide_image_base64: str,
            slide_index: int = 0,
            total_slides: int = 1,
            max_depth: int = 3,
            prev_slide_text: str | None = None,
            next_slide_text: str | None = None,
        ) -> BranchTreeResponse:
            return BranchTreeResponse(
                slide_index=slide_index,
                total_slides=total_slides,
                branches=[
                    BranchNode(
                        branch_id="b1",
                        predicted_text="Hello world",
                        action=BranchAction(
                            type=BranchActionType.HIGHLIGHT,
                            bbox_1000=[100, 200, 300, 400],
                            duration_ms=3000,
                        ),
                        teleprompter="Say hello",
                        next_branches=[],
                    )
                ],
                generation_time_ms=1234.5,
            )

        monkeypatch.setattr(
            live_routes.BranchGenerator, "generate", fake_generate,
        )

        resp = client.post(
            "/api/v1/branches",
            json={"parse_id": "test", "slide_index": 0, "max_depth": 3},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["slide_index"] == 0
        assert body["total_slides"] == 1
        assert len(body["branches"]) == 1
        assert body["branches"][0]["branch_id"] == "b1"
        assert body["generation_time_ms"] == 1234.5

    def test_generate_error(self, monkeypatch):
        """200 with error field when generation fails (graceful degradation)."""
        from app.api.v1.live import routes as live_routes
        from app.schemas.live import BranchTreeResponse
        from app.schemas.pptx import SlideImage, SlideResult

        slides = [
            SlideResult(
                slide_index=0,
                slide_id=None,
                slide_width_emu=9144000,
                slide_height_emu=6858000,
                image=SlideImage(width_px=960, height_px=540, image_base64="data:image/png;base64,abc"),
                elements=[],
                warnings=[],
            )
        ]
        monkeypatch.setattr(live_routes.ParseCache, "get", lambda _pid: slides)

        async def fake_error(*args, **kwargs):  # type: ignore[no-untyped-def]
            return BranchTreeResponse(
                slide_index=0,
                total_slides=1,
                error="LLM returned empty response after cleaning",
            )

        monkeypatch.setattr(live_routes.BranchGenerator, "generate", fake_error)

        resp = client.post(
            "/api/v1/branches",
            json={"parse_id": "test", "slide_index": 0, "max_depth": 3},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["error"] == "LLM returned empty response after cleaning"
        assert body["branches"] == []
