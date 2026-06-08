"""Tests for note_parse pipeline."""

import pytest

from backend.pipelines.note_parse import NoteParseError, parse_note


# ---------------------------------------------------------------------------
# Happy-path / basic parsing
# ---------------------------------------------------------------------------

def test_parse_note_content_only():
    """No positioning prefix, no @-category → defaults to 'note'."""
    s = parse_note("飞机声", 1.5)
    assert s.scene_code is None
    assert s.take_number is None
    assert s.category == "note"
    assert s.content == "飞机声"
    assert s.raw_text == "飞机声"
    assert s.ts == 1.5


def test_parse_note_with_scene_take():
    """Scene code + take number prefix."""
    s = parse_note("3A 2 飞机声", 0.0)
    assert s.scene_code == "3A"
    assert s.take_number == 2
    assert s.category == "note"
    assert s.content == "飞机声"


def test_parse_note_with_category_issue():
    """@-category without scene/take prefix."""
    s = parse_note("@issue 灯光问题", 2.0)
    assert s.scene_code is None
    assert s.take_number is None
    assert s.category == "issue"
    assert s.content == "灯光问题"


def test_parse_note_with_category_keep():
    """@keep category with empty content."""
    s = parse_note("@keep", 0.0)
    assert s.category == "keep"
    assert s.content == ""


def test_parse_note_full_format():
    """Scene + take + @-category + content."""
    s = parse_note("3A 2 @issue 开头有飞机声", 3.0)
    assert s.scene_code == "3A"
    assert s.take_number == 2
    assert s.category == "issue"
    assert s.content == "开头有飞机声"


def test_parse_note_current_take():
    """No positioning prefix → scene_code & take_number both None."""
    s = parse_note("@note some note text", 0.0)
    assert s.scene_code is None
    assert s.take_number is None


def test_parse_note_category_only():
    """Only a category marker, no content after it."""
    s = parse_note("@keep", 0.0)
    assert s.scene_code is None
    assert s.take_number is None
    assert s.category == "keep"
    assert s.content == ""


# ---------------------------------------------------------------------------
# Defaults & edge cases
# ---------------------------------------------------------------------------

def test_parse_note_category_defaults_to_note():
    """No @-marker → category is 'note'."""
    s = parse_note("just some text here", 0.0)
    assert s.category == "note"


def test_parse_note_trailing_spaces_trimmed():
    """Leading / trailing spaces on content are stripped."""
    s = parse_note("  飞机声  ", 0.0)
    assert s.content == "飞机声"


def test_parse_note_scene_code_with_special_chars():
    """Scene code can contain _, -, alnum."""
    s = parse_note("Scene_3A 2 test", 0.0)
    assert s.scene_code == "Scene_3A"
    assert s.take_number == 2
    assert s.content == "test"


# ---------------------------------------------------------------------------
# Error conditions
# ---------------------------------------------------------------------------

def test_parse_note_unknown_category_raises():
    """Unrecognised @-category raises NoteParseError."""
    with pytest.raises(NoteParseError, match="未知类别"):
        parse_note("@invalid xxx", 0.0)


def test_parse_note_content_too_long_raises():
    """Content longer than 2000 chars raises NoteParseError."""
    long_content = "x" * 2001
    with pytest.raises(NoteParseError, match="内容过长"):
        parse_note(long_content, 0.0)
