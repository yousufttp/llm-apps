from llama_index.core.node_parser import SentenceSplitter

from src.loader import load_incidents


def main():
    documents = load_incidents()

    splitter = SentenceSplitter(
        chunk_size=512,
        chunk_overlap=50,
    )

    nodes = splitter.get_nodes_from_documents(documents)

    print(f"Documents: {len(documents)}")
    print(f"Nodes: {len(nodes)}")

    for i, node in enumerate(nodes, start=1):
        print("\n" + "=" * 60)
        print(f"NODE {i}")
        print("=" * 60)

        print(f"Incident ID: {node.metadata['incident_id']}")
        print(f"Category: {node.metadata['category']}")
        print(f"Error Code: {node.metadata['error_code']}")

        print("\nTEXT:")
        print(node.text)


if __name__ == "__main__":
    main()