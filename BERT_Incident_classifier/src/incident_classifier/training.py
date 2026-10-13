from __future__ import annotations

from collections import Counter
from pathlib import Path

import pandas as pd
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.model_selection import train_test_split

from incident_classifier.data import load_training_incidents
from incident_classifier.encoder import BertTextEncoder
from incident_classifier.model import IncidentClassifier


FOCUS_CATEGORIES = ["Pending Order", "Activation", "Switch"]


def train_from_excel(
    training_excel: str | Path,
    artifacts_dir: str | Path,
    *,
    confidence_threshold: float = 0.65,
    model_name: str = "google-bert/bert-base-uncased",
    test_size: float = 0.2,
    random_state: int = 42,
    encoder: BertTextEncoder | None = None,
) -> dict[str, Path | pd.DataFrame | str]:
    artifacts_path = Path(artifacts_dir)
    bert_path = artifacts_path / "bert-base-uncased"
    classifier_path = artifacts_path / "incident_classifier.joblib"
    report_path = artifacts_path / "evaluation_report.txt"
    confusion_path = artifacts_path / "confusion_matrix.csv"

    df = load_training_incidents(training_excel)
    if df["label"].nunique() < 2:
        raise ValueError("Training data must contain at least two group/category labels.")

    train_df, test_df, split_note = _split_data(
        df, test_size=test_size, random_state=random_state
    )

    text_encoder = encoder or BertTextEncoder.from_pretrained(model_name)
    train_embeddings = text_encoder.encode(train_df["short_description"].tolist())
    test_embeddings = text_encoder.encode(test_df["short_description"].tolist())

    classifier = IncidentClassifier.train(
        train_embeddings,
        train_df["label"].tolist(),
        confidence_threshold=confidence_threshold,
    )
    predictions = classifier.predict(test_embeddings)
    predicted_labels = [prediction.label for prediction in predictions]

    report = classification_report(
        test_df["label"].tolist(),
        predicted_labels,
        zero_division=0,
    )
    confusion_df = _confusion_dataframe(
        test_df["label"].tolist(),
        predicted_labels,
        labels=classifier.labels,
    )
    focus_report = _focus_category_report(
        test_df.assign(predicted_label=predicted_labels)
    )

    artifacts_path.mkdir(parents=True, exist_ok=True)
    classifier.save(classifier_path)
    text_encoder.save_pretrained(bert_path)
    report_path.write_text(
        "\n".join(
            [
                "Incident classifier evaluation",
                f"Rows: {len(df)}",
                f"Train rows: {len(train_df)}",
                f"Test rows: {len(test_df)}",
                split_note,
                "",
                "Per-label precision/recall/f1:",
                report,
                "",
                "Focus categories:",
                focus_report,
            ]
        ),
        encoding="utf-8",
    )
    confusion_df.to_csv(confusion_path)

    return {
        "bert_path": bert_path,
        "classifier_path": classifier_path,
        "report_path": report_path,
        "confusion_path": confusion_path,
        "confusion": confusion_df,
        "split_note": split_note,
    }


def _split_data(
    df: pd.DataFrame, *, test_size: float, random_state: int
) -> tuple[pd.DataFrame, pd.DataFrame, str]:
    counts = Counter(df["label"])
    test_count = max(1, round(len(df) * test_size))
    can_stratify = (
        min(counts.values()) >= 2
        and test_count >= len(counts)
        and len(df) - test_count >= len(counts)
    )
    stratify = df["label"] if can_stratify else None
    note = (
        "Split: 80/20 stratified by group/category label."
        if can_stratify
        else "Split: 80/20 random because one or more labels had too few rows for stratification."
    )
    train_df, test_df = train_test_split(
        df,
        test_size=test_size,
        random_state=random_state,
        stratify=stratify,
    )
    return train_df.copy(), test_df.copy(), note


def _confusion_dataframe(
    actual: list[str], predicted: list[str], *, labels: list[str]
) -> pd.DataFrame:
    matrix = confusion_matrix(actual, predicted, labels=labels)
    return pd.DataFrame(matrix, index=labels, columns=labels)


def _focus_category_report(results: pd.DataFrame) -> str:
    rows = []
    for category in FOCUS_CATEGORIES:
        actual_matches = results["category"] == category
        predicted_matches = results["predicted_label"].str.endswith(f"||{category}")
        total = int(actual_matches.sum())
        correct = int((actual_matches & predicted_matches).sum())
        rows.append(f"{category}: {correct}/{total} correct")
    return "\n".join(rows)
