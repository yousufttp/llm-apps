import hashlib
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

        keywords = ", ".join(
            incident.get("keywords", [])
        )

        text = (
            f"Incident Category: {incident['category']}\n"
            f"Error Code: {incident['error_code']}\n"
            f"Description: {incident['description']}\n"
            f"Root Cause: {incident['root_cause']}\n"
            f"Resolution: {incident['resolution']}\n"
            f"Keywords: {keywords}"
        )

        content_hash = hashlib.sha256(
            text.encode("utf-8")
        ).hexdigest()

        document = Document(
            text=text,
            metadata={
                "incident_id": incident["incident_id"],
                "category": incident["category"],
                "error_code": incident["error_code"],
                "content_hash": content_hash,
            },
        )

        documents.append(document)

    return documents