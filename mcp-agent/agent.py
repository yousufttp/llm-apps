import os
import json
from typing import Annotated, Any, TypedDict

from dotenv import load_dotenv
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_openai import ChatOpenAI
from langgraph.graph.message import add_messages
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

load_dotenv()


class AgentState(TypedDict, total=False):
    messages: Annotated[list[Any], add_messages]


SYSTEM_PROMPT = """You are a customer service lookup assistant. Use the customer lookup tool for mobile-number requests.
Only report facts returned by the tool. Never invent customer details. If no customer is found, say so clearly.
Keep the response concise and organize a found customer's name, address, devices, plan, promotions, and billing."""


async def build_graph(mcp_url: str | None = None):
    url = mcp_url or os.getenv("MCP_SERVER_URL", "http://localhost:8000/mcp")
    client = MultiServerMCPClient({"customer_lookup": {"url": url, "transport": "streamable_http"}})
    tools = await client.get_tools()
    model = ChatOpenAI(model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"), temperature=0)
    model_with_tools = model.bind_tools(tools)

    async def call_model(state: AgentState):
        response = await model_with_tools.ainvoke([("system", SYSTEM_PROMPT), *state["messages"]])
        return {"messages": [response]}

    graph = StateGraph(AgentState)
    graph.add_node("agent", call_model)
    graph.add_node("tools", ToolNode(tools))
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", tools_condition)
    graph.add_edge("tools", "agent")
    return graph.compile()


async def lookup_with_agent(mobile_number: str, first_name: str = "", last_name: str = "", mcp_url: str | None = None) -> dict[str, Any]:
    graph = await build_graph(mcp_url)
    criteria = f"mobile number {mobile_number}"
    if first_name.strip():
        criteria += f", first name {first_name.strip()}"
    if last_name.strip():
        criteria += f", last name {last_name.strip()}"
    result = await graph.ainvoke({"messages": [("user", f"Look up customer details using {criteria}.")]})
    messages = result["messages"]
    tool_result = next((message.content for message in messages if getattr(message, "type", "") == "tool"), None)
    if isinstance(tool_result, str):
        try:
            tool_result = json.loads(tool_result)
        except json.JSONDecodeError:
            pass
    elif isinstance(tool_result, list):
        text_blocks = [block.get("text", "") for block in tool_result if isinstance(block, dict)]
        combined = "".join(text_blocks)
        try:
            tool_result = json.loads(combined)
        except json.JSONDecodeError:
            pass
    final = messages[-1].content if messages else "No response received."
    tool_calls = []
    for message in messages:
        for call in getattr(message, "tool_calls", []) or []:
            tool_calls.append({"name": call.get("name"), "args": call.get("args", {})})
    return {"response": final, "tool_result": tool_result, "tool_calls": tool_calls}
