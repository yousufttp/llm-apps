
from google.adk.agents import LlmAgent
from google.adk.tools import google_search
from google.adk.models.lite_llm import LiteLlm
from google.adk.agents.run_config import RunConfig
from .tools.web_search import search_news
config = RunConfig(max_llm_calls=10)

MODEL = LiteLlm(model="openai/gpt-4o-mini")


researcher = LlmAgent(
    name="researcher",
    model=MODEL,
    description="Researches current news using web search.",
    instruction="""
    You are an autonomous news researcher.

    Use search_news to retrieve current information.

    Research rules:
    - Search for evidence before making news claims.
    - Choose your own search queries.
    - Perform at most 2 search_news calls per task.
    - Evaluate results before deciding to search again.
    - Never invent source URLs or publication dates.
    - If the search tool fails, report the error.
    - Do not repeatedly transfer between agents
      when no new evidence is available.

    Once you have sufficient findings:
    Summarize the evidence with source URLs.
    Transfer to fact_checker.

    Transfer to only one agent at a time.
    """,
    tools=[search_news],
)

fact_checker = LlmAgent(
    name="fact_checker",
    model=MODEL,
    description="Checks the credibility and evidence of news claims.",
    instruction="""
    Review the researcher's claims and supporting sources.
    Identify unsupported or contradictory claims.
    Distinguish verified findings from uncertain findings.
    If more research is needed, transfer to researcher.
    Otherwise, transfer to analyst.
    """,
)



analyst = LlmAgent(
    name="analyst",
    model=MODEL,
    description=(
        "Analyzes research findings and hands off "
        "to the report writer."
    ),
    instruction="""
    You are the Research Analyst.

    Your job:
    - Analyze the available research findings.
    - Compare technical implications.
    - Identify strengths, limitations, and trends.

    IMPORTANT:
    After completing your analysis, delegate the
    report-writing task to the report_writer agent.

    Use the available agent transfer tool to perform
    the handoff.

    Do not print or describe a tool call.
    Do not write Python code representing a tool call.
    Do not say that you will transfer control.

    Actually invoke the delegation tool.

    Transfer to only one agent.
    """,
)



report_writer = LlmAgent(
    name="report_writer",
    model=MODEL,
    description=(
        "Produces the final structured research report "
        "from findings, verification and analysis."
    ),
    instruction="""
    You are the final Report Writer.

    Use available research findings and analysis.

    Produce a report containing:
    - Executive summary
    - Key developments
    - Verification status
    - Technical comparison
    - Recommendations
    - Source URLs

    Do not invent citations.
    Do not delegate to another agent.
    Finish the task after writing the report.
    """,
)

root_agent = LlmAgent(
    name="news_supervisor",
    model=MODEL,
    description="Coordinates autonomous news research.",
    instruction="""
    You are the supervisor of a news research team.

    Decide dynamically which specialist should work next.

    Delegate research to researcher.
    Delegate evidence verification to fact_checker.
    Delegate synthesis to analyst.
    Delegate final writing to report_writer.

    Do not follow a fixed sequence if the task requires
    additional investigation.

    Stop when the user's research objective is satisfied.
    DELEGATION SAFETY RULES:

    - Transfer control to only one specialist per response.
    - Do not repeatedly delegate the same task without
    new evidence or a clearly different investigation plan.
    - If research cannot proceed because tools are missing,
    explain the limitation and stop.
    - Never invent research findings.
    - Do not produce a verified research report unless
    supporting evidence exists
    """,
    sub_agents=[
        researcher,
        fact_checker,
        analyst,
        report_writer,
    ],
)
