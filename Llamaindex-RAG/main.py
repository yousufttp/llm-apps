from src.loader import load_incidents


def main():
    documents = load_incidents()

    print(f"Loaded {len(documents)} documents")

    first_document = documents[0]

    print("\nDOCUMENT TEXT:")
    print(first_document.text)

    print("\nMETADATA:")
    print(first_document.metadata)


if __name__ == "__main__":
    main()