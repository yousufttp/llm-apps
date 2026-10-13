from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression


@dataclass(frozen=True)
class ClassificationResult:
    label: str
    confidence: float


class IncidentClassifier:
    def __init__(
        self,
        classifier: LogisticRegression,
        labels: list[str],
        *,
        confidence_threshold: float,
    ) -> None:
        self.classifier = classifier
        self.labels = labels
        self.confidence_threshold = confidence_threshold

    @classmethod
    def train(
        cls,
        embeddings: np.ndarray,
        labels: list[str],
        *,
        confidence_threshold: float,
    ) -> "IncidentClassifier":
        classifier = LogisticRegression(
            max_iter=2000,
            class_weight="balanced",
        )
        classifier.fit(embeddings, labels)
        return cls(
            classifier,
            labels=list(classifier.classes_),
            confidence_threshold=confidence_threshold,
        )

    def predict(self, embeddings: np.ndarray) -> list[ClassificationResult]:
        probabilities = self.classifier.predict_proba(embeddings)
        class_indices = probabilities.argmax(axis=1)
        return [
            ClassificationResult(
                label=str(self.classifier.classes_[class_index]),
                confidence=float(probabilities[row_index, class_index]),
            )
            for row_index, class_index in enumerate(class_indices)
        ]

    def save(self, path: str | Path) -> None:
        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(
            {
                "classifier": self.classifier,
                "labels": self.labels,
                "confidence_threshold": self.confidence_threshold,
            },
            output_path,
        )

    @classmethod
    def load(cls, path: str | Path) -> "IncidentClassifier":
        payload = joblib.load(path)
        return cls(
            payload["classifier"],
            list(payload["labels"]),
            confidence_threshold=float(payload["confidence_threshold"]),
        )
