from src.indexer import load_index
from src.query_engine import create_query_engine


def main():
    # Load already-persisted vectors from ChromaDB
    index = load_index()

    query = input("\nDescribe the customer issue: ")

    category = input(
        "Category filter (press Enter for no filter): "
    ).strip()

    query_engine = create_query_engine(
        index=index,
        category=category if category else None,
    )

    response = query_engine.query(query)

    print("\n--- RAG Response ---")
    print(response)

    print("\n--- Retrieved Evidence ---")

    for source_node in response.source_nodes:
        print(
            f"\nIncident: "
            f"{source_node.metadata['incident_id']}"
        )
        print(
            f"Category: "
            f"{source_node.metadata['category']}"
        )
        print(
            f"Score: {source_node.score:.4f}"
        )


if __name__ == "__main__":
    main()