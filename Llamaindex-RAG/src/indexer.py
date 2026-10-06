from llama_index.core import VectorStoreIndex
from llama_index.embeddings.ollama import OllamaEmbedding


def create_index(documents):

    embed_model = OllamaEmbedding(
        model_name="nomic-embed-text",
        base_url="http://localhost:11434"
    )

    index = VectorStoreIndex.from_documents(
        documents,
        embed_model=embed_model
    )

    return index