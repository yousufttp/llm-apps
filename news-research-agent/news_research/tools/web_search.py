
import os
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

# Locate news_research/.env
ENV_PATH = Path(__file__).resolve().parents[1] / ".env"

load_dotenv(dotenv_path=ENV_PATH)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def search_news(query: str) -> dict:
    """Search the live web for news and return sourced findings.

    Args:
        query: A focused news research search query.
    """
    try:
        response = client.responses.create(
            model="gpt-4.1-mini",
            tools=[{"type": "web_search"}],
            tool_choice="required",
            input=(
                "Search the web for this topic:\n"
                f"{query}\n\n"
                "Return up to 3 relevant findings with "
                "titles, dates, source URLs, and a brief "
                "summary. Do not invent citations."
            ),
            max_output_tokens=600,
        )

        searches = sum(
            item.type == "web_search_call"
            for item in response.output
        )

        return {
            "status": "success",
            "query": query,
            "searches_performed": searches,
            "findings": response.output_text[:4000],
            "usage": {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            } if response.usage else {},
        }

    except Exception as exc:
        return {
            "status": "error",
            "query": query,
            "error": str(exc)[:300],
        }
