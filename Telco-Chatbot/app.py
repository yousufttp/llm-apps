import os
import re
import uuid
from typing import Any

import streamlit as st
from cryptography.fernet import Fernet
from dotenv import load_dotenv
from openai import OpenAI

from agents import activation_agent, other_faq_agent, router_agent
from checkpoint import (
    initialize_database,
    list_sessions,
    load_checkpoint,
    save_checkpoint,
    save_feedback,
    update_feedback_follow_up,
)
from retrieval import retrieve_faqs, sync_embeddings

load_dotenv()
st.set_page_config(page_title="Telora", page_icon="💬")


def get_thread_id() -> str:
    if "active_thread_id" not in st.session_state:
        st.session_state.active_thread_id = str(uuid.uuid4())
    return st.session_state.active_thread_id


def new_chat() -> None:
    st.session_state.active_thread_id = str(uuid.uuid4())


initialize_database()

with st.sidebar:
    st.subheader("Telora")
    if st.button("＋ New chat", use_container_width=True):
        new_chat()
        st.rerun()

    if st.button("Refresh FAQ embeddings", use_container_width=True):
        st.session_state.refresh_faq_embeddings = True
        st.rerun()

    st.caption("Recent conversations")
    sessions = list_sessions()
    if not sessions:
        st.caption("No saved conversations yet.")
    else:
        active_thread_id = get_thread_id()
        session_ids = [session["thread_id"] for session in sessions]
        session_titles = {
            session["thread_id"]: session["title"] or "New conversation"
            for session in sessions
        }
        if active_thread_id not in session_titles:
            session_ids.insert(0, active_thread_id)
            session_titles[active_thread_id] = "New conversation"
        selected_thread = st.radio(
            "Chats",
            session_ids,
            index=session_ids.index(active_thread_id),
            format_func=lambda thread_id: session_titles[thread_id][:40],
            label_visibility="collapsed",
        )
        if selected_thread != get_thread_id():
            st.session_state.active_thread_id = selected_thread
            st.rerun()


def extract_pii(prompt: str) -> dict[str, str | None]:
    phone = re.search(r"(?:\+?\d[\d\s().-]{7,}\d)", prompt)
    name = re.search(r"(?:my name is|name is)\s+([A-Za-z][A-Za-z -]{1,60})", prompt, re.I)
    address = re.search(r"(?:my address is|address is)\s+(.+?)(?:[.!?]|$)", prompt, re.I)
    return {
        "customer_name": name.group(1).strip() if name else None,
        "mobile_number": phone.group(0).strip() if phone else None,
        "address": address.group(1).strip() if address else None,
    }


prompt = st.chat_input("Type your prompt...")
thread_id = get_thread_id()
encryption_key = os.getenv("CHAT_ENCRYPTION_KEY")
checkpoint = {"messages": [], "pii": {}, "title": None, "route": None}

if encryption_key:
    try:
        cipher = Fernet(encryption_key.encode())
        checkpoint = load_checkpoint(thread_id, cipher)
    except ValueError:
        st.error("CHAT_ENCRYPTION_KEY is invalid. Generate a valid Fernet key and try again.")
        cipher = None
else:
    cipher = None

active_title = checkpoint.get("title") or "New conversation"
st.title(active_title if active_title != "New conversation" else "Telora")
st.write("Ask a wireless-service question below.")

for message in checkpoint["messages"]:
    st.chat_message(message["role"]).write(message["content"])

if st.session_state.pop("refresh_faq_embeddings", False):
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        st.sidebar.error("OPENAI_API_KEY is not set.")
    else:
        try:
            with st.spinner("Refreshing FAQ embeddings…"):
                refresh_index = sync_embeddings(OpenAI(api_key=api_key), force_refresh=True)
            regenerated = sum(item["status"] == "regenerated" for item in refresh_index["statuses"])
            st.sidebar.success(f"FAQ index refreshed: {regenerated} regenerated.")
        except Exception as exc:
            st.sidebar.error(f"FAQ refresh failed: {exc}")

if prompt:
    st.session_state.pop("active_feedback", None)
    st.chat_message("user").write(prompt)
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        st.error("OPENAI_API_KEY is not set. Add it to your .env file and try again.")
    elif not encryption_key:
        st.error("CHAT_ENCRYPTION_KEY is not set. Add it to your .env file and try again.")
    elif cipher is not None:
        try:
            context = checkpoint["messages"][-10:]
            client = OpenAI(api_key=api_key)
            state: dict[str, Any] = {
                "thread_id": thread_id,
                "question": prompt,
                "messages": context,
                "next_agent": None,
                "answer": None,
                "retrieved_faqs": [],
            }
            with st.spinner("Thinking…"):
                state = router_agent(client, state)
                intent = state["intent"]
                route = state["next_agent"]
                state.update({
                    "retrieval_category": route,
                    "retrieval_query": prompt,
                    "retrieval_skipped": intent not in {"activation", "others"},
                    "retrieval_skip_reason": "",
                    "retrieval_status": [],
                    "source_faq_ids": [],
                    "similarity_scores": [],
                })
                if intent in {"activation", "others"}:
                    # The router intent is the only source of the retrieval category.
                    category = "activation" if intent == "activation" else "others"
                    state["retrieval_category"] = category
                    index = sync_embeddings(client)
                    retrieval = retrieve_faqs(
                        client, prompt, category,
                        top_k=int(os.getenv("FAQ_TOP_K", "3")),
                        min_similarity=float(os.getenv("FAQ_MIN_SIMILARITY", "0.75")),
                        index=index,
                    )
                    state.update({
                        "retrieved_faqs": retrieval["records"],
                        "embedding_model": retrieval["model"],
                        "retrieval_status": retrieval["statuses"],
                        "source_faq_ids": [record["id"] for record in retrieval["records"]],
                        "similarity_scores": [record["similarity"] for record in retrieval["records"]],
                        "retrieval_skipped": False,
                    })
                    if retrieval["records"]:
                        state = activation_agent(client, state) if category == "activation" else other_faq_agent(client, state)
                        answer = state["answer"]
                    else:
                        answer = "I could not find enough information in the approved FAQ for that question. Please contact the relevant support team for help."
                        state["answer"] = answer
                        state["agent_messages"] = [{
                            "status": "skipped",
                            "reason": f"No {category} FAQ matched the similarity threshold; specialist agent was not called.",
                        }]
                        state["agent_usage"] = {}
                else:
                    skip_reasons = {
                        "greeting_or_chitchat": "Greeting or chitchat",
                        "out_of_scope": "Outside Telora wireless-support scope",
                        "needs_clarification": "More information is needed",
                    }
                    state["retrieval_skip_reason"] = skip_reasons.get(intent, "Router classification failed")
                    answer = state["router_reply"] or "Could you describe what you need help with regarding your wireless service?"
                    state["answer"] = answer
                    state["agent_messages"] = []
                    state["agent_usage"] = {}
            messages = [
                *checkpoint["messages"],
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": answer},
            ]
            pii = checkpoint["pii"]
            pii.update({key: value for key, value in extract_pii(prompt).items() if value})
            title = checkpoint.get("title") or prompt.strip()[:80]
            save_checkpoint(thread_id, title, messages, route, pii, cipher)
            st.chat_message("assistant").write(answer)
            if intent in {"activation", "others"}:
                st.session_state.active_feedback = {
                    "request_id": str(uuid.uuid4()),
                    "thread_id": thread_id,
                    "original_question": prompt,
                    "previous_answer": answer,
                    "route": route,
                    "category": route,
                    "faq_ids": state.get("source_faq_ids", []),
                    "similarity_scores": state.get("similarity_scores", []),
                    "status": "pending",
                }

            with st.expander("Agent handoff details"):
                st.json({
                    "intent": state.get("intent"),
                    "routed_to": state.get("next_agent"),
                    "router_reason": state.get("router_reason"),
                    "input_sent": state.get("question"),
                    "agent_result": state.get("answer"),
                })

            agent_label = route.replace("_", " ").title() if route else "No FAQ agent"
            with st.expander(f"{agent_label} agent call"):
                st.write("Messages sent:")
                st.json(state.get("agent_messages", []))
                st.write("Token usage:")
                st.json(state.get("agent_usage", {}))
            with st.expander("Retrieval details"):
                st.write("Similarity is a relevance score, not a probability.")
                st.json({
                    "intent": state.get("intent"),
                    "retrieval_skipped": state.get("retrieval_skipped"),
                    "skip_reason": state.get("retrieval_skip_reason"),
                    "query": state.get("retrieval_query"),
                    "category": state.get("retrieval_category"),
                    "faq_ids": state.get("source_faq_ids", []),
                    "subcategories": [record["subcategory"] for record in state.get("retrieved_faqs", [])],
                    "similarity_scores": state.get("similarity_scores", []),
                    "embedding_model": state.get("embedding_model"),
                    "cache_status": state.get("retrieval_status", []),
                })
        except ValueError:
            st.error("CHAT_ENCRYPTION_KEY is invalid. Generate a valid Fernet key and try again.")
        except Exception as exc:
            st.error(f"The request failed: {exc}")

feedback = st.session_state.get("active_feedback")
if feedback and feedback.get("thread_id") == thread_id:
    if feedback["status"] == "pending":
        st.write("Did this answer solve your problem?")
        yes_col, no_col = st.columns(2)
        if yes_col.button("Yes", key=f"feedback_yes_{feedback['request_id']}"):
            save_feedback(
                feedback["request_id"], thread_id, feedback["original_question"],
                None, feedback["faq_ids"], feedback["similarity_scores"], True,
            )
            feedback["status"] = "satisfied"
            st.session_state.active_feedback = feedback
            st.rerun()
        if no_col.button("No", key=f"feedback_no_{feedback['request_id']}"):
            save_feedback(
                feedback["request_id"], thread_id, feedback["original_question"],
                None, feedback["faq_ids"], feedback["similarity_scores"], False,
            )
            feedback["status"] = "needs_clarification"
            st.session_state.active_feedback = feedback
            st.rerun()
    elif feedback["status"] == "satisfied":
        st.success("Thank you for your feedback.")
    elif feedback["status"] == "needs_clarification":
        st.info("Sorry that didn’t resolve it. What is still happening? For example, is your activation pending, did it fail, or are you having trouble with your SIM/eSIM?")
        with st.form(f"clarification_form_{feedback['request_id']}"):
            clarification = st.text_area("Describe what is still unresolved:")
            submitted = st.form_submit_button("Submit clarification")
        if submitted:
            if not clarification.strip():
                st.warning("Please describe what is still happening.")
            elif cipher is not None and os.getenv("OPENAI_API_KEY"):
                try:
                    combined_query = (
                        f"Original question: {feedback['original_question']}\n"
                        f"Previous answer: {feedback['previous_answer']}\n"
                        f"Customer clarification: {clarification.strip()}"
                    )
                    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
                    with st.spinner("Checking the FAQ again…"):
                        index = sync_embeddings(client)
                        retrieval = retrieve_faqs(
                            client, combined_query, feedback["category"],
                            top_k=int(os.getenv("FAQ_TOP_K", "3")),
                            min_similarity=float(os.getenv("FAQ_MIN_SIMILARITY", "0.75")),
                            index=index,
                        )
                        follow_state: dict[str, Any] = {
                            "thread_id": thread_id,
                            "question": combined_query,
                            "messages": checkpoint["messages"][-10:],
                            "next_agent": feedback["route"],
                            "answer": None,
                            "retrieved_faqs": retrieval["records"],
                        }
                        if retrieval["records"]:
                            follow_state = (activation_agent if feedback["route"] == "activation" else other_faq_agent)(client, follow_state)
                            follow_answer = follow_state["answer"]
                        else:
                            follow_answer = "I’m sorry, but the available FAQ does not cover this clarified issue. Please contact the relevant support team for further help."
                            follow_state["answer"] = follow_answer
                            follow_state["agent_messages"] = []
                            follow_state["agent_usage"] = {}
                    follow_messages = [
                        *checkpoint["messages"],
                        {"role": "user", "content": clarification.strip()},
                        {"role": "assistant", "content": follow_answer},
                    ]
                    save_checkpoint(thread_id, checkpoint.get("title") or feedback["original_question"][:80], follow_messages, feedback["route"], checkpoint["pii"], cipher)
                    update_feedback_follow_up(
                        feedback["request_id"], clarification.strip(),
                        [record["id"] for record in retrieval["records"]],
                        [record["similarity"] for record in retrieval["records"]],
                    )
                    feedback["status"] = "follow_up_answered"
                    feedback["follow_up_retrieval"] = {
                        "query": combined_query,
                        "category": feedback["category"],
                        "faq_ids": [record["id"] for record in retrieval["records"]],
                        "subcategories": [record["subcategory"] for record in retrieval["records"]],
                        "similarity_scores": [record["similarity"] for record in retrieval["records"]],
                        "embedding_model": retrieval["model"],
                        "cache_status": retrieval["statuses"],
                    }
                    st.session_state.active_feedback = feedback
                    st.rerun()
                except Exception as exc:
                    st.error(f"The clarification request failed: {exc}")

    if feedback.get("status") == "follow_up_answered":
        with st.expander("Follow-up retrieval details"):
            st.write("Similarity is a relevance score, not a probability.")
            st.json(feedback.get("follow_up_retrieval", {}))
