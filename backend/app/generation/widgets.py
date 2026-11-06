"""Incremental parser that separates prose tokens from <TemplateWidget> blocks.

The LLM streams plain text that may contain

    <TemplateWidget templateName="checklist"> {...json...} </TemplateWidget>

Rather than making every frontend re-implement tag parsing on partial frames, the backend
strips the block out of the token stream and emits it as a separate, validated `widget`
SSE event. Prose keeps streaming with no visible markup.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass

from pydantic import ValidationError

from app.core.models import ChecklistPayload

log = logging.getLogger(__name__)

OPEN = "<TemplateWidget"
CLOSE = "</TemplateWidget>"
_ATTR = re.compile(r'templateName\s*=\s*"([^"]+)"')
_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$")

VALIDATORS = {"checklist": ChecklistPayload}


@dataclass
class TextPart:
    text: str


@dataclass
class WidgetPart:
    template: str
    payload: dict


def _possible_prefix(buf: str) -> int:
    """Length of the longest suffix of buf that is a prefix of OPEN (could become a tag)."""
    for n in range(min(len(OPEN) - 1, len(buf)), 0, -1):
        if OPEN.startswith(buf[-n:]):
            return n
    return 0


def parse_widget(raw_open_tag: str, body: str) -> WidgetPart | None:
    m = _ATTR.search(raw_open_tag)
    template = m.group(1) if m else "checklist"
    body = _FENCE.sub("", body.strip())
    try:
        data = json.loads(body)
    except json.JSONDecodeError as e:
        log.warning("Widget JSON invalid: %s", e)
        return None
    validator = VALIDATORS.get(template)
    if validator:
        try:
            data = validator.model_validate(data).normalised().model_dump()
        except ValidationError as e:
            log.warning("Widget %s failed validation: %s", template, e.errors()[:3])
            return None
    return WidgetPart(template, data)


class WidgetStreamParser:
    def __init__(self) -> None:
        self._buf = ""
        self._in_widget = False
        self._open_tag = ""

    def feed(self, delta: str) -> list[TextPart | WidgetPart]:
        self._buf += delta
        out: list[TextPart | WidgetPart] = []
        while True:
            if not self._in_widget:
                idx = self._buf.find(OPEN)
                if idx == -1:
                    hold = _possible_prefix(self._buf)
                    emit = self._buf[: len(self._buf) - hold]
                    if emit:
                        out.append(TextPart(emit))
                    self._buf = self._buf[len(emit):]
                    return out
                if idx:
                    out.append(TextPart(self._buf[:idx]))
                tag_end = self._buf.find(">", idx)
                if tag_end == -1:
                    self._buf = self._buf[idx:]
                    return out
                self._open_tag = self._buf[idx : tag_end + 1]
                self._buf = self._buf[tag_end + 1 :]
                self._in_widget = True
            else:
                end = self._buf.find(CLOSE)
                if end == -1:
                    return out
                widget = parse_widget(self._open_tag, self._buf[:end])
                if widget:
                    out.append(widget)
                self._buf = self._buf[end + len(CLOSE) :]
                self._in_widget = False

    def flush(self) -> list[TextPart | WidgetPart]:
        """End of stream: an unterminated widget is attempted once, otherwise dropped."""
        out: list[TextPart | WidgetPart] = []
        if self._in_widget:
            widget = parse_widget(self._open_tag, self._buf)
            if widget:
                out.append(widget)
        elif self._buf:
            out.append(TextPart(self._buf))
        self._buf, self._in_widget = "", False
        return out
