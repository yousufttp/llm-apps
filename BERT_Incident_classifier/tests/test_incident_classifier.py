from __future__ import annotations

import numpy as np
import pandas as pd

from incident_classifier.data import load_daily_incidents, load_training_incidents
from incident_classifier.inference import classify_daily_excel
from incident_classifier.training import train_from_excel


class FakeEncoder:
    def encode(self, texts: list[str]) -> np.ndarray:
        vectors = []
        for text in texts:
            normalized = text.lower()
            vectors.append(
                [
                    float("order" in normalized or "pending" in normalized),
                    float("activate" in normalized or "activation" in normalized),
                    float("switch" in normalized),
                    float(len(normalized) % 7) / 7.0,
                ]
            )
        return np.asarray(vectors, dtype=np.float32)

    def save_pretrained(self, path) -> None:
        path.mkdir(parents=True, exist_ok=True)
        (path / "fake-model.txt").write_text("synthetic encoder", encoding="utf-8")


def test_loaders_validate_expected_columns(tmp_path):
    training_path = tmp_path / "training.xlsx"
    daily_path = tmp_path / "daily.xlsx"

    pd.DataFrame(
        {
            "incident_number": ["INC001"],
            "short_description": ["Pending order is delayed"],
            "group": ["Fulfillment"],
            "category": ["Pending Order"],
        }
    ).to_excel(training_path, index=False)
    pd.DataFrame(
        {
            "incident_number": ["INC002"],
            "short_description": ["Activation did not complete"],
        }
    ).to_excel(daily_path, index=False)

    training_df = load_training_incidents(training_path)
    daily_df = load_daily_incidents(daily_path)

    assert training_df.loc[0, "label"] == "Fulfillment||Pending Order"
    assert daily_df.loc[0, "incident_number"] == "INC002"


def test_training_saves_artifacts_and_reports_focus_categories(tmp_path):
    training_path = tmp_path / "training.xlsx"
    artifacts_dir = tmp_path / "artifacts"
    training_rows = [
        ("INC001", "pending order waiting for item", "Fulfillment", "Pending Order"),
        ("INC002", "order stuck in pending queue", "Fulfillment", "Pending Order"),
        ("INC003", "activate service failed", "Provisioning", "Activation"),
        ("INC004", "activation workflow errored", "Provisioning", "Activation"),
        ("INC005", "switch request failed", "Network", "Switch"),
        ("INC006", "customer switch did not complete", "Network", "Switch"),
        ("INC007", "pending order needs review", "Fulfillment", "Pending Order"),
        ("INC008", "activation retry needed", "Provisioning", "Activation"),
        ("INC009", "switch port issue", "Network", "Switch"),
    ]
    pd.DataFrame(
        training_rows,
        columns=["incident_number", "short_description", "group", "category"],
    ).to_excel(training_path, index=False)

    result = train_from_excel(
        training_path,
        artifacts_dir,
        confidence_threshold=0.5,
        encoder=FakeEncoder(),
    )

    assert result["classifier_path"].exists()
    assert result["bert_path"].exists()
    report_text = result["report_path"].read_text(encoding="utf-8")
    assert "Pending Order" in report_text
    assert "Activation" in report_text
    assert "Switch" in report_text
    assert result["confusion_path"].exists()


def test_daily_inference_uses_saved_artifacts_without_retraining(tmp_path, monkeypatch):
    training_path = tmp_path / "training.xlsx"
    daily_path = tmp_path / "daily.xlsx"
    output_path = tmp_path / "classified.xlsx"
    artifacts_dir = tmp_path / "artifacts"

    pd.DataFrame(
        [
            ("INC001", "pending order waiting", "Fulfillment", "Pending Order"),
            ("INC002", "order pending manual check", "Fulfillment", "Pending Order"),
            ("INC003", "activation failed", "Provisioning", "Activation"),
            ("INC004", "activate service retry", "Provisioning", "Activation"),
            ("INC005", "switch request failed", "Network", "Switch"),
            ("INC006", "customer switch blocked", "Network", "Switch"),
            ("INC007", "pending order manual review", "Fulfillment", "Pending Order"),
            ("INC008", "activation did not finish", "Provisioning", "Activation"),
            ("INC009", "switch failed after request", "Network", "Switch"),
        ],
        columns=["incident_number", "short_description", "group", "category"],
    ).to_excel(training_path, index=False)
    pd.DataFrame(
        [
            ("INC101", "pending order delayed"),
            ("INC102", "activation error"),
        ],
        columns=["incident_number", "short_description"],
    ).to_excel(daily_path, index=False)

    train_from_excel(
        training_path,
        artifacts_dir,
        confidence_threshold=0.99,
        encoder=FakeEncoder(),
    )

    class LocalFakeBert:
        @classmethod
        def from_pretrained(cls, model_path, *, local_files_only):
            assert local_files_only is True
            assert model_path == artifacts_dir / "bert-base-uncased"
            return FakeEncoder()

    monkeypatch.setattr("incident_classifier.inference.BertTextEncoder", LocalFakeBert)

    output_df = classify_daily_excel(daily_path, artifacts_dir, output_path)

    assert output_path.exists()
    assert output_df.columns.tolist() == [
        "incident_number",
        "predicted_group",
        "predicted_category",
        "confidence",
        "manual_review",
    ]
    assert output_df["manual_review"].all()
