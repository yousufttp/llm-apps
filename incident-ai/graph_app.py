import os
import shutil
import json
from typing import TypedDict, List, Optional

from langchain_ollama import ChatOllama, OllamaEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate

from langgraph.graph import StateGraph, END


# ---------- Helpers ----------
def safe_json_loads(text: str) -> dict:
    text = text.strip()
    try:
        return json.loads(text)
    except Exception:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return json.loads(text[start:end+1])
    if start != -1 and end == -1:
        return json.loads(text[start:] + "\n}")
    raise ValueError("Could not parse JSON from LLM output.")


def format_context(docs):
    return "\n".join(
        f"- {d.metadata['id']} (category={d.metadata['category']}): {d.page_content}"
        for d in docs
    )


# ---------- Models ----------
llm = ChatOllama(model="llama3.2:latest", temperature=0)
emb = OllamaEmbeddings(model="nomic-embed-text:latest")


# ---------- Data ----------
INCIDENTS = [
    {"id": "INC001", "category": "Login", "text": "User cannot login to portal. Error: invalid token. Started after password reset."},
    {"id": "INC002", "category": "Billing", "text": "Customer charged twice for January invoice. Needs refund and reconciliation."},
    {"id": "INC003", "category": "Network", "text": "Intermittent packet loss on LTE site. High latency reported by multiple users."},
    {"id": "INC004", "category": "Login", "text": "After password reset, user gets 'token expired' and login fails. Clearing session fixes temporarily."},
]

docs = [Document(page_content=i["text"], metadata={"id": i["id"], "category": i["category"]}) for i in INCIDENTS]

# Clean start each run (for learning)
if os.path.exists("./chroma_incidents"):
    shutil.rmtree("./chroma_incidents")

db = Chroma.from_documents(documents=docs, embedding=emb, persist_directory="./chroma_incidents")
retriever = db.as_retriever(search_kwargs={"k": 2})


# ---------- Prompts ----------
triage_prompt = ChatPromptTemplate.from_messages([
    ("system",
     "You are an IT incident triage assistant.\n"
     "Rules:\n"
     "- Use ONLY the provided similar incidents as evidence.\n"
     "- Output MUST be valid JSON and NOTHING else.\n"
     "- If evidence is weak or mixed, lower confidence and ask ONE clarifying question.\n"),
    ("human",
     "New incident:\n{query}\n\n"
     "Similar incidents:\n{context}\n\n"
     "Return JSON with keys:\n"
     "- category (string)\n"
     "- confidence (0-100 integer)\n"
     "- evidence_ids (array of strings)\n"
     "- clarifying_question (string or empty)\n"
    ),
    ("system",
    "You are an IT incident triage assistant.\n"
    "Rules:\n"
    "- Use ONLY the provided similar incidents as evidence.\n"
    "- Output MUST be valid JSON and NOTHING else.\n"
    "- If evidence is weak or mixed, lower confidence and ask ONE clarifying question.\n"
    "- If you ask a question, make it specific to differentiate between: "
    "login/auth error, billing/payment, network/connectivity, or app crash/device.\n"
    )

    
])

rewrite_prompt = ChatPromptTemplate.from_messages([
    ("system",
     "Rewrite vague incidents into a short search query to find similar past incidents.\n"
     "Rules:\n"
     "- MUST include the most specific keywords from the user clarification.\n"
     "- Keep it under 15 words.\n"
     "- Return ONLY the query text, nothing else."),
    ("human",
     "Original incident:\n{original}\n\n"
     "User clarification:\n{clarification}\n\n"
     "Rewrite into one strong search query.")
])



# ---------- LangGraph State ----------
class TriageState(TypedDict):
    original_query: str
    query: str
    hits: List[str]
    context: str
    result: dict
    raw: str
    clarification: Optional[str]
    rewritten_query: Optional[str]


# ---------- Nodes ----------
def retrieve_node(state: TriageState) -> TriageState:
    hits_docs = retriever.invoke(state["query"])
    state["hits"] = [d.metadata["id"] for d in hits_docs]
    state["context"] = format_context(hits_docs)
    print("\n[retrieve] query:", state["query"])
    print("[retrieve] hits:", state["hits"])
    return state


def triage_node(state: TriageState) -> TriageState:
    text_prompt = triage_prompt.format(query=state["query"], context=state["context"])
    out = llm.invoke(text_prompt)
    raw = (out.content or "").strip()

    # Retry once if Ollama returned empty
    if not raw:
        out = llm.invoke(msg)
        raw = (out.content or "").strip()

    state["raw"] = raw
    print("\nRAW TRIAGE OUTPUT:\n", raw if raw else "<EMPTY>")

    try:
        state["result"] = safe_json_loads(raw)
    except Exception as e:
        state["result"] = {
            "category": "Unknown",
            "confidence": 0,
            "evidence_ids": [],
            "clarifying_question": "I got an empty/invalid response. Can you restate the issue briefly?"
        }
        print("\nJSON PARSE FAILED:", str(e))

    return state




def needs_clarification(state: TriageState) -> str:
    q = state["result"].get("clarifying_question", "")
    if q:
        return "ask_user"
    return "finish"


def ask_user_node(state: TriageState) -> TriageState:
    question = state["result"]["clarifying_question"]
    answer = input(f"\nClarifying question: {question}\nYour answer: ").strip()
    state["clarification"] = answer
    print("\n[ask_user] clarification:", state["clarification"])
    return state


def rewrite_node(state: TriageState) -> TriageState:
    text_prompt = rewrite_prompt.format(original=state["original_query"], clarification=state["clarification"] or "")
    rq = llm.invoke(text_prompt).content.strip().strip('"')
    state["rewritten_query"] = rq
    state["query"] = rq
    print("\n[rewrite] rewritten_query:", state["rewritten_query"])
    return state


def finish_node(state: TriageState) -> TriageState:
    return state


# ---------- Build graph ----------
g = StateGraph(TriageState)

g.add_node("retrieve", retrieve_node)
g.add_node("triage", triage_node)
g.add_node("ask_user", ask_user_node)
g.add_node("rewrite", rewrite_node)
g.add_node("finish", finish_node)

g.set_entry_point("retrieve")
g.add_edge("retrieve", "triage")
g.add_conditional_edges("triage", needs_clarification, {"ask_user": "ask_user", "finish": "finish"})
g.add_edge("ask_user", "rewrite")
g.add_edge("rewrite", "retrieve")  # loop back with improved query
g.add_edge("finish", END)

app = g.compile()

print("\n=== PRECHECK: direct LLM call ===")
test = llm.invoke("Return ONLY the word OK.")
print("Precheck output:", repr(test.content))
print("=== END PRECHECK ===\n")

if __name__ == "__main__":
    user_query = input("Enter new incident: ").strip()
    state: TriageState = {
        "original_query": user_query,
        "query": user_query,
        "hits": [],
        "raw": "",
        "context": "",
        "result": {},
        "clarification": None,
        "rewritten_query": None,
    }

    final_state = app.invoke(state)

    print("\n--- DEBUG ---")
    print("Hits:", final_state["hits"])
    if final_state.get("rewritten_query"):
        print("Rewritten query:", final_state["rewritten_query"])

    print("\n--- FINAL JSON ---")
    print(final_state["result"])
