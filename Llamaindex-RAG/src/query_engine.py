from llama_index.core import PromptTemplate
from llama_index.core.vector_stores import (
    MetadataFilter,
    MetadataFilters,
)
from llama_index.llms.ollama import Ollama


QA_PROMPT = PromptTemplate(
    """
You are a telecom incident resolution assistant.

Use ONLY the historical incident context provided below.
Do not invent a root cause or resolution.

Historical Incident Context:
---------------------
{context_str}
---------------------

Customer Issue:
{query_str}

Return your answer in exactly this format:

Likely Root Cause:
<root cause>

Recommended Resolution:
<resolution>

If the historical incidents do not provide enough evidence,
say that there is insufficient information.
"""
)


def create_query_engine(index, category=None):

    llm = Ollama(
        model="llama3.2",
        base_url="http://localhost:11434",
        request_timeout=120.0,
        context_window=4096,
    )

    filters = None

    if category:
        filters = MetadataFilters(
            filters=[
                MetadataFilter(
                    key="category",
                    value=category,
                )
            ]
        )

    query_engine = index.as_query_engine(
        llm=llm,
        similarity_top_k=3,
        filters=filters,
        text_qa_template=QA_PROMPT,
    )

    return query_engine