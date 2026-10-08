from src.loader import load_incidents
from src.indexer import sync_documents


def main():

    documents = load_incidents()

    print(
        f"Found {len(documents)} incident(s) "
        "in source data."
    )

    sync_documents(documents)


if __name__ == "__main__":
    main()