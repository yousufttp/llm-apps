import asyncio
import json
import os
from concurrent.futures import ThreadPoolExecutor

import streamlit as st
from dotenv import load_dotenv

from agent import lookup_with_agent
from customer_data import validate_mobile_number


def run_agent_request(mobile_number: str, first_name: str = "", last_name: str = "") -> dict:
    """Run async MCP/OpenAI work on an isolated loop for Streamlit reruns."""
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(asyncio.run, lookup_with_agent(mobile_number, first_name, last_name))
        return future.result()

load_dotenv()
st.set_page_config(page_title="Customer Lookup MCP Demo", page_icon="📱", layout="wide")
st.title("📱 Customer Lookup")
st.caption("A LangGraph agent retrieves demo customer details through a local MCP server.")

with st.form("lookup_form"):
    mobile_number = st.text_input("Mobile number", placeholder="212-555-0101")
    first_name, last_name = st.columns(2)
    first_name = first_name.text_input("First name (optional)", placeholder="Ava")
    last_name = last_name.text_input("Last name (optional)", placeholder="Patel")
    submitted = st.form_submit_button("Search customer", type="primary")

if submitted:
    try:
        normalized = validate_mobile_number(mobile_number)
    except ValueError as error:
        st.warning(str(error))
        st.stop()

    if not os.getenv("OPENAI_API_KEY"):
        st.error("OPENAI_API_KEY is not configured. Copy .env.example to .env and add your key.")
        st.stop()

    with st.spinner("Contacting the customer lookup agent..."):
        try:
            result = run_agent_request(normalized, first_name, last_name)
        except Exception as error:
            st.error(f"Could not reach the MCP service or agent: {error}")
            st.stop()

    tool_result = result.get("tool_result")
    if isinstance(tool_result, str):
        try:
            tool_result = json.loads(tool_result)
        except json.JSONDecodeError:
            tool_result = None
    elif isinstance(tool_result, list):
        text_blocks = [block.get("text", "") for block in tool_result if isinstance(block, dict)]
        try:
            tool_result = json.loads("".join(text_blocks))
        except json.JSONDecodeError:
            tool_result = None

    if not isinstance(tool_result, dict) or not tool_result.get("found"):
        st.info("No customer was found for that mobile number.")
    else:
        customer = tool_result["customer"]
        st.success(f"Customer found: {customer['first_name']} {customer['last_name']}")
        first_name, last_name, contact, service = st.columns(4)
        first_name.subheader("First name")
        first_name.write(customer["first_name"])
        last_name.subheader("Last name")
        last_name.write(customer["last_name"])
        contact.subheader("Address")
        contact.write(customer["address"])
        service.subheader("Plan")
        service.write(customer["plan"])
        st.subheader("Devices")
        st.table(customer["devices"])
        left, right = st.columns(2)
        left.subheader("Promotions")
        for promotion in customer["promotions"]:
            left.write(f"• {promotion}")
        right.subheader("Billing")
        right.write(f"Last bill: ${customer['last_bill']['amount']:.2f} ({customer['last_bill']['status']})")
        right.write(f"Current bill: ${customer['current_bill']['amount']:.2f} ({customer['current_bill']['status']})")
        with st.expander("Agent response"):
            st.write(result["response"])

    with st.expander("🔧 Agent tool calling", expanded=True):
        calls = result.get("tool_calls", [])
        if not calls:
            st.caption("The agent did not report a tool call.")
        else:
            for index, call in enumerate(calls, start=1):
                st.markdown(f"**Call {index}: `{call['name']}`**")
                st.json(call["args"])
            st.caption("MCP tool result")
            st.json(tool_result if isinstance(tool_result, dict) else {"raw": tool_result})
