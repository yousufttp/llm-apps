from src.indexer import get_chroma_collection


collection = get_chroma_collection()

print("Collection:", collection.name)
print("Stored vectors:", collection.count())

results = collection.get(
    include=["metadatas"]
)

print("\nIncidents:")

for metadata in results["metadatas"]:
    print(
        metadata.get("incident_id"),
        metadata.get("category"),
        metadata.get("error_code"),
    )