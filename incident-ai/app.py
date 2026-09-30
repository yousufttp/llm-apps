import os
import shutil
import json
from langchain_ollama import ChatOllama, OllamaEmbeddings
from langchain_core.documents import Document
from langchain_chroma import Chroma
from langchain_core.prompts import ChatPromptTemplate


llm = ChatOllama(model="llama3.2:latest", temperature=0)
emb = OllamaEmbeddings(model="nomic-embed-text:latest")

INCIDENTS = [
    {"id": "INC001", "category": "Login", "text": "User cannot login to portal. Error: invalid token. Started after password reset."},
    {"id": "INC002", "category": "Billing", "text": "Customer charged twice for January invoice. Needs refund and reconciliation."},
    {"id": "INC003", "category": "Network", "text": "Intermittent packet loss on LTE site. High latency reported by multiple users."},
    {"id": "INC004", "category": "Login", "text": "After password reset, user gets 'token expired' and login fails. Clearing session fixes temporarily."},

]

docs = [
    Document(
        page_content=item["text"],
        metadata={"id": item["id"], "category": item["category"]}
    )
    for item in INCIDENTS
]

# Clean start (prevents duplicates while learning)
if os.path.exists("./chroma_incidents"):
    shutil.rmtree("./chroma_incidents")

db = Chroma.from_documents(
    documents=docs,
    embedding=emb,
    persist_directory="./chroma_incidents"
)

retriever = db.as_retriever(search_kwargs={"k": 2})

def safe_json_loads(text: str) -> dict:
    """
    Best-effort JSON parser for LLM output.
    - Extracts the first {...} block
    - Repairs missing closing braces if needed
    """
    text = text.strip()

    # Try normal parse first
    try:
        return json.loads(text)
    except Exception:
        pass

    # Extract from first "{" to last "}" if present
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = text[start:end+1]
        return json.loads(candidate)

    # If we have a "{" but no closing "}", try to close it
    if start != -1 and end == -1:
        candidate = text[start:] + "\n}"
        return json.loads(candidate)

    raise ValueError("Could not parse JSON from LLM output.")

def format_context(docs):
    lines = []
    for d in docs:
        lines.append(f"- {d.metadata['id']} (category={d.metadata['category']}): {d.page_content}")
    return "\n".join(lines)

prompt = ChatPromptTemplate.from_messages([
    ("system",
     "You are an IT incident triage assistant.\n"
     "Rules:\n"
     "- Use ONLY the provided similar incidents as evidence.\n"
     "- Output MUST be valid JSON and NOTHING else (no markdown, no notes).\n"
     "- If evidence is weak or mixed, lower confidence and ask ONE clarifying question.\n"),
    ("human",
     "New incident:\n{query}\n\n"
     "Similar incidents:\n{context}\n\n"
     "Return JSON with keys:\n"
     "- category (string)\n"
     "- confidence (0-100 integer)\n"
     "- evidence_ids (array of strings)\n"
     "- clarifying_question (string or empty)\n"
    )
])

rewrite_prompt = ChatPromptTemplate.from_messages([
    ("system",
     "You rewrite vague incidents into a short search query for finding similar past incidents. "
     "Return ONLY the rewritten query text."),
    ("human",
     "Original incident:\n{original}\n\n"
     "User clarification:\n{clarification}\n\n"
     "Rewrite into one short search query (max 15 words).")
])

print("Vector DB built. Trying retrieval + LLM reasoning...")

query = "Customer says the app is not working and they cannot proceed."
hits = retriever.invoke(query)
context = format_context(hits)

print("\nRetrieved IDs:", [h.metadata["id"] for h in hits])

msg = prompt.format_messages(query=query, context=context)
out = llm.invoke(msg)

result = safe_json_loads(out.content)

print("\nLLM JSON:\n", result)

# If the model asks a clarifying question, ask the user and rerun once
if result.get("clarifying_question"):
    user_answer = input("\nClarifying question: " + result["clarifying_question"] + "\nYour answer: ").strip()
    if user_answer:
        query2 = llm.invoke(
            rewrite_prompt.format_messages(original=query, clarification=user_answer)
        ).content.strip()
        hits2 = retriever.invoke(query2)
        print("\nRewritten query:", query2)
        print("Retrieved IDs (2nd pass):", [h.metadata["id"] for h in hits2])
        context2 = format_context(hits2)
        out2 = llm.invoke(prompt.format_messages(query=query2, context=context2))
        print("\nRAW out2.content:\n", out2.content)
        result2 = safe_json_loads(out.content)
        print("Evidence IDs (final):", result2.get("evidence_ids"))
        print("\nFINAL JSON:\n", result2)



