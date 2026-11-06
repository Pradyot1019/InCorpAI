import json

from app.generation.widgets import TextPart, WidgetPart, WidgetStreamParser

PAYLOAD = {
    "header_title": "SPICe+ filing",
    "categories": ["Prep"],
    "items": [
        {"id": "a", "label": "Get DSC", "category": "Prep"},
        {"id": "a", "label": "Reserve name", "category": "Filing"},  # dup id, unknown category
    ],
}
STREAM = (
    "Here are the steps [1].\n\n"
    '<TemplateWidget templateName="checklist">\n' + json.dumps(PAYLOAD) + "\n</TemplateWidget>"
    " Trailing."
)


def run(deltas):
    p = WidgetStreamParser()
    parts = []
    for d in deltas:
        parts += p.feed(d)
    parts += p.flush()
    text = "".join(x.text for x in parts if isinstance(x, TextPart))
    widgets = [x for x in parts if isinstance(x, WidgetPart)]
    return text, widgets


def test_single_delta():
    text, widgets = run([STREAM])
    assert "<TemplateWidget" not in text and "Trailing." in text
    assert len(widgets) == 1


def test_character_by_character_stream():
    text, widgets = run(list(STREAM))
    assert text.strip() == "Here are the steps [1].\n\n Trailing.".strip()
    w = widgets[0].payload
    assert [i["id"] for i in w["items"]] == ["a", "step-2"]  # deduplicated
    assert "Filing" in w["categories"]  # normalised


def test_lone_angle_bracket_is_text():
    text, widgets = run(["a < b and ", "<Tem", "pest"])
    assert text == "a < b and <Tempest" and not widgets


def test_invalid_json_dropped():
    text, widgets = run(['x <TemplateWidget templateName="checklist">{bad json}</TemplateWidget> y'])
    assert text == "x  y" and widgets == []


def test_code_fenced_json_accepted():
    body = "```json\n" + json.dumps(PAYLOAD) + "\n```"
    _, widgets = run([f'<TemplateWidget templateName="checklist">{body}</TemplateWidget>'])
    assert len(widgets) == 1
