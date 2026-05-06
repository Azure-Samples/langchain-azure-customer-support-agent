"""Unit tests for the streaming event helper."""

from types import SimpleNamespace

from app.streaming import iter_message_events


def _ai(content="", tool_calls=None):
    msg = SimpleNamespace()
    msg.type = "ai"
    msg.content = content
    msg.tool_calls = tool_calls or []
    return msg


def test_text_chunk_yields_text_event():
    msg = _ai(content="hello")
    events = list(iter_message_events(msg))
    assert events == [{"kind": "text", "text": "hello"}]


def test_tool_call_yields_tool_event():
    msg = _ai(tool_calls=[{"name": "lookup_order", "args": {"order_id": 7}}])
    events = list(iter_message_events(msg))
    assert len(events) == 1
    assert events[0]["kind"] == "tool"
    assert events[0]["tool"]["name"] == "lookup_order"
    assert "7" in events[0]["tool"]["args_preview"]


def test_tool_result_with_doc_tags_yields_citations():
    tool_result = SimpleNamespace(type="tool", content="See [kb-001] and [kb-003]")
    events = list(iter_message_events(tool_result))
    assert events == [{"kind": "citations", "doc_ids": ["kb-001", "kb-003"]}]


def test_empty_string_yields_nothing():
    msg = _ai(content="")
    assert list(iter_message_events(msg)) == []
