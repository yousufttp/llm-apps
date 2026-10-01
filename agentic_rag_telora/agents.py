import json
from typing import Any

from openai import OpenAI

ALLOWED_INTENTS = {
    "greeting_or_chitchat",
    "activation",
    "others",
    "out_of_scope",
    "needs_clarification",
}

ROUTER_PROMPT = """You classify customer messages for Telora, a wireless customer-support FAQ app.
Return only valid JSON with this shape: {"intent": "...", "reply": "...", "reason": "..."}.
The intent must be exactly one of: greeting_or_chitchat, activation, others, out_of_scope, needs_clarification.

Rules:
- A greeting plus a support question is classified by the support question.
- activation covers SIM, eSIM, line, device, or wireless-service activation.
- others covers billing, payments, account access, plans, promotions, and general wireless support.
- out_of_scope covers unrelated requests such as coding, writing, or general non-wireless tasks.
- needs_clarification covers vague messages with insufficient context, such as “It isn’t working”.
- reply should be a brief customer-facing response only for greeting_or_chitchat, out_of_scope, or needs_clarification; otherwise use an empty string.
- reason should be brief."""
ACTIVATION_PROMPT = """You are the Activation FAQ Agent. Answer questions about wireless service activation using only the supplied FAQ records. Identify the question, give a clear concise answer, ask one brief follow-up if unclear, and do not invent policies, steps, timelines, or technical details. Do not answer unrelated billing, device, or network questions."""
OTHER_FAQ_PROMPT = """You are the Other FAQ Agent. Answer general wireless-service questions using only the supplied FAQ records. Give a clear concise answer, ask one brief follow-up if unclear, and do not invent policies, fees, eligibility, timelines, or account details. Do not answer activation-specific questions or request passwords, full payment card numbers, or security codes."""


def _usage(response: Any) -> dict[str, Any]:
    usage = getattr(response, "usage", None)
    if usage is None:
        return {}
    return usage.model_dump() if hasattr(usage, "model_dump") else dict(usage)


def _safe_classification(reply: str = "") -> dict[str, Any]:
    return {
        "intent": "needs_clarification",
        "reply": reply or "Could you describe what you need help with regarding your wireless service?",
        "reason": "Router classification failed or returned an invalid intent.",
    }


def classify_intent(client: OpenAI, question: str,
                   context: list[dict[str, str]]) -> dict[str, Any]:
    messages = [
        {"role": "system", "content": ROUTER_PROMPT},
        *context,
        {"role": "user", "content": question},
    ]
    try:
        response = client.responses.create(model="gpt-4o-mini", input=messages)
        raw = response.output_text.strip()
        if raw.startswith("```"):
            raw = raw.strip("`").replace("json\n", "", 1).strip()
        parsed = json.loads(raw)
        intent = parsed.get("intent")
        if intent not in ALLOWED_INTENTS:
            raise ValueError("Unsupported intent")
        return {
            "intent": intent,
            "reply": str(parsed.get("reply") or ""),
            "reason": str(parsed.get("reason") or ""),
            "messages": messages,
            "usage": _usage(response),
        }
    except Exception:
        safe = _safe_classification()
        return {**safe, "messages": messages, "usage": {}}


def _call(client: OpenAI, system: str, prompt: str,
          context: list[dict[str, str]], faq_records: list[dict[str, Any]]) -> tuple[str, list[dict[str, str]], dict[str, Any]]:
    faq_context = "\n\n".join(
        f"FAQ ID: {record['id']}\nCategory: {record['category']}\n"
        f"Subcategory: {record['subcategory']}\nQuestion: {record['question']}\n"
        f"Answer: {record['answer']}"
        for record in faq_records
    )
    messages = [
        {"role": "system", "content": system},
        {"role": "system", "content": f"Retrieved FAQ records:\n{faq_context}"},
        *context,
        {"role": "user", "content": prompt},
    ]
    response = client.responses.create(model="gpt-4o-mini", input=messages)
    return response.output_text.strip(), messages, _usage(response)


def router_agent(client: OpenAI, state: dict[str, Any]) -> dict[str, Any]:
    classification = classify_intent(client, state["question"], state["messages"])
    intent = classification["intent"]
    route = intent if intent in {"activation", "others"} else None
    return {
        **state,
        "intent": intent,
        "next_agent": route,
        "router_reply": classification["reply"],
        "router_reason": classification["reason"],
        "router_messages": classification["messages"],
        "router_usage": classification["usage"],
    }


def activation_agent(client: OpenAI, state: dict[str, Any]) -> dict[str, Any]:
    answer, messages, usage = _call(client, ACTIVATION_PROMPT, state["question"], state["messages"], state["retrieved_faqs"])
    return {**state, "answer": answer, "agent_messages": messages, "agent_usage": usage}


def other_faq_agent(client: OpenAI, state: dict[str, Any]) -> dict[str, Any]:
    answer, messages, usage = _call(client, OTHER_FAQ_PROMPT, state["question"], state["messages"], state["retrieved_faqs"])
    return {**state, "answer": answer, "agent_messages": messages, "agent_usage": usage}
