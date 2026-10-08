from pathlib import Path

import chromadb

from llama_index.core import (
    VectorStoreIndex,
    StorageContext,
)

from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.vector_stores.chroma import ChromaVectorStore


PROJECT_ROOT = Path(__file__).resolve().parent.parent

CHROMA_PATH = PROJECT_ROOT / "chroma_db"

COLLECTION_NAME = "telecom_incidents"


def get_embedding_model():
    return OllamaEmbedding(
        model_name="nomic-embed-text",
        base_url="http://localhost:11434",
    )


def get_chroma_collection():

    client = chromadb.PersistentClient(
        path=str(CHROMA_PATH)
    )

    collection = client.get_or_create_collection(
        name=COLLECTION_NAME
    )

    return collection


def create_index(documents):

    print("Creating embeddings and storing in ChromaDB...")

    collection = get_chroma_collection()

    # Prevent accidental duplicate ingestion during experiments
    if collection.count() > 0:
        raise RuntimeError(
            "Collection already contains data. "
            "Use load_index() instead."
        )

    vector_store = ChromaVectorStore(
        chroma_collection=collection
    )

    storage_context = StorageContext.from_defaults(
        vector_store=vector_store
    )

    index = VectorStoreIndex.from_documents(
        documents,
        storage_context=storage_context,
        embed_model=get_embedding_model(),
    )

    print("Index stored successfully in ChromaDB")

    return index


def load_index():

    print("Loading existing index from ChromaDB...")

    collection = get_chroma_collection()

    if collection.count() == 0:
        raise RuntimeError(
            "ChromaDB collection is empty. "
            "Create the index first."
        )

    vector_store = ChromaVectorStore(
        chroma_collection=collection
    )

    index = VectorStoreIndex.from_vector_store(
        vector_store,
        embed_model=get_embedding_model(),
    )

    print("Index loaded successfully")

    return index

def sync_documents(documents):

    collection = get_chroma_collection()
    index = load_index()

    for document in documents:

        incident_id = document.metadata["incident_id"]
        new_hash = document.metadata["content_hash"]

        existing = collection.get(
            where={
                "incident_id": incident_id
            },
            include=["metadatas"],
        )

        # -------------------------
        # CASE 1: NEW INCIDENT
        # -------------------------

        if not existing["ids"]:

            print(
                f"{incident_id}: NEW -> inserting"
            )

            index.insert(document)

            continue

        # -------------------------
        # CASE 2/3: EXISTING INCIDENT
        # -------------------------

        existing_metadata = existing["metadatas"][0]

        existing_hash = existing_metadata.get(
            "content_hash"
        )

        # Same content
        if existing_hash == new_hash:

            print(
                f"{incident_id}: UNCHANGED -> skipping"
            )

            continue

        # -------------------------
        # CASE 3: CHANGED INCIDENT
        # -------------------------

        print(
            f"{incident_id}: CHANGED -> updating"
        )

        # Delete all existing vector records for this incident.
        # This also protects us from legacy duplicates.
        collection.delete(
            where={
                "incident_id": incident_id
            }
        )

        # Generate new embedding + insert
        index.insert(document)

    print("Ingestion completed.")