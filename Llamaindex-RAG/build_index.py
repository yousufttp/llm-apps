from src.loader import load_incidents
from src.indexer import create_index


def main():

    documents = load_incidents()

    print(f"Loaded {len(documents)} documents")

    create_index(documents)


if __name__ == "__main__":
    main()