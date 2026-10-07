from llama_index.core.postprocessor import LLMRerank
from llama_index.llms.ollama import Ollama


def create_reranker(top_n=3):

    llm = Ollama(
        model="llama3.2",
        base_url="http://localhost:11434",
        request_timeout=120.0,
        context_window=4096,
    )

    reranker = LLMRerank(
        choice_batch_size=5,
        top_n=top_n,
        llm=llm,
    )

    return reranker