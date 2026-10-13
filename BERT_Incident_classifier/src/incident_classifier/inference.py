from __future__ import annotations

from pathlib import Path

import pandas as pd

from incident_classifier.data import load_daily_incidents, split_label
from incident_classifier.encoder import BertTextEncoder
from incident_classifier.model import IncidentClassifier


def classify_daily_excel(
    daily_excel: str | Path,
    artifacts_dir: str | Path,
    output_excel: str | Path,
    *,
    local_files_only: bool = True,
) -> pd.DataFrame:
    artifacts_path = Path(artifacts_dir)
    classifier = IncidentClassifier.load(artifacts_path / "incident_classifier.joblib")
    encoder = BertTextEncoder.from_pretrained(
        artifacts_path / "bert-base-uncased",
        local_files_only=local_files_only,
    )

    daily_df = load_daily_incidents(daily_excel)
    embeddings = encoder.encode(daily_df["short_description"].tolist())
    predictions = classifier.predict(embeddings)

    rows = []
    for incident_number, prediction in zip(
        daily_df["incident_number"].tolist(), predictions, strict=True
    ):
        group, category = split_label(prediction.label)
        rows.append(
            {
                "incident_number": incident_number,
                "predicted_group": group,
                "predicted_category": category,
                "confidence": round(prediction.confidence, 4),
                "manual_review": prediction.confidence
                < classifier.confidence_threshold,
            }
        )

    output_df = pd.DataFrame(rows)
    output_path = Path(output_excel)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_df.to_excel(output_path, index=False)
    return output_df
