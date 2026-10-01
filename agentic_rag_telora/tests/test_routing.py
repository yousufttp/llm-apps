import json

from agents import classify_intent


class FakeResponse:
    def __init__(self, payload):
        self.output_text = json.dumps(payload) if isinstance(payload, dict) else payload
        self.usage = None


class FakeResponses:
    def __init__(self, payload):
        self.payload = payload
        self.calls = 0

    def create(self, **kwargs):
        self.calls += 1
        return FakeResponse(self.payload)


class FakeClient:
    def __init__(self, payload):
        self.responses = FakeResponses(payload)


def test_router_classifies_supported_intents():
    cases = [
        ("Hi", "greeting_or_chitchat"),
        ("Hello, my eSIM activation is pending", "activation"),
        ("How do I pay my bill?", "others"),
        ("Write me a Python function", "out_of_scope"),
        ("It isn't working", "needs_clarification"),
    ]
    for question, intent in cases:
        result = classify_intent(FakeClient({"intent": intent, "reply": "", "reason": ""}), question, [])
        assert result["intent"] == intent


def test_invalid_router_output_fails_to_clarification():
    result = classify_intent(FakeClient("not-json"), "hello", [])
    assert result["intent"] == "needs_clarification"
    assert result["reply"]
