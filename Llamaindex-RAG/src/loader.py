import json
from pathlib import Path

from llama_index.core import Document


def load_incidents():
    file_path = (
        Path(__file__).resolve().parent.parent
        / "data"
        / "incidents.json"
    )

    with open(file_path, "r", encoding="utf-8") as file:
        incidents = json.load(file)

    documents = []

    for incident in incidents:
        document = Document(
            text=(
                f"Description: {incident['description']}\n"
                f"Root Cause: {incident['root_cause']}\n"
                f"Resolution: {incident['resolution']}"
            ),
            metadata={
                "incident_id": incident["incident_id"],
                "category": incident["category"],
                "error_code": incident["error_code"],
            },
        )

        documents.append(document)

    return documents