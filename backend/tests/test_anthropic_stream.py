"""Exercise AnthropicLLM through the real SDK with a mocked HTTP transport (no network)."""

import asyncio
import json

import anthropic

try:  # newer anthropic SDKs use httpx2
    import httpx2 as httpx
except ImportError:  # pragma: no cover
    import httpx

from app.generation.llm import AnthropicLLM, Usage
from app.generation.widgets import TextPart, WidgetPart, WidgetStreamParser

ANSWER = (
    "File Part A first [1].\n\n"
    '<TemplateWidget templateName="checklist">'
    '{"header_title":"SPICe+","categories":["Prep"],'
    '"items":[{"id":"s1","label":"Get DSC","category":"Prep","source_refs":[1]}]}'
    "</TemplateWidget>"
)


def _sse_body() -> bytes:
    def ev(name, data):
        return f"event: {name}\ndata: {json.dumps(data)}\n\n"

    parts = [
        ev("message_start", {"type": "message_start", "message": {
            "id": "msg_1", "type": "message", "role": "assistant", "model": "claude-test",
            "content": [], "stop_reason": None, "stop_sequence": None,
            "usage": {"input_tokens": 120, "output_tokens": 1, "cache_read_input_tokens": 100}}}),
        ev("content_block_start", {"type": "content_block_start", "index": 0,
                                   "content_block": {"type": "text", "text": ""}}),
    ]
    for i in range(0, len(ANSWER), 7):  # split mid-tag on purpose
        parts.append(ev("content_block_delta", {"type": "content_block_delta", "index": 0,
                                                "delta": {"type": "text_delta", "text": ANSWER[i:i + 7]}}))
    parts += [
        ev("content_block_stop", {"type": "content_block_stop", "index": 0}),
        ev("message_delta", {"type": "message_delta", "delta": {"stop_reason": "end_turn",
                                                                "stop_sequence": None},
                             "usage": {"output_tokens": 42}}),
        ev("message_stop", {"type": "message_stop"}),
    ]
    return "".join(parts).encode()


def test_anthropic_llm_streams_and_reports_usage():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, content=_sse_body(), headers={"content-type": "text/event-stream"})

    llm = AnthropicLLM("sk-test", "claude-test", 512)
    llm._client = anthropic.AsyncAnthropic(
        api_key="sk-test", http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler))
    )

    async def run():
        usage, parser, parts = Usage(), WidgetStreamParser(), []
        async for d in llm.stream(system="SYS", messages=[{"role": "user", "content": "q"}],
                                  chunks=[], query="q", usage=usage):
            parts += parser.feed(d)
        return usage, parts + parser.flush()

    usage, parts = asyncio.run(run())
    text = "".join(p.text for p in parts if isinstance(p, TextPart))
    widgets = [p for p in parts if isinstance(p, WidgetPart)]

    assert text.strip() == "File Part A first [1]."
    assert widgets[0].payload["items"][0]["label"] == "Get DSC"
    assert (usage.input_tokens, usage.output_tokens, usage.cache_read_tokens) == (120, 42, 100)
    assert seen["body"]["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert seen["body"]["stream"] is True and seen["body"]["model"] == "claude-test"
