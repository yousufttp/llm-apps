from __future__ import annotations

from pathlib import Path

import numpy as np
import torch
from transformers import AutoModel, AutoTokenizer


class BertTextEncoder:
    def __init__(
        self,
        model: AutoModel,
        tokenizer: AutoTokenizer,
        *,
        device: str | None = None,
        max_length: int = 128,
        batch_size: int = 16,
    ) -> None:
        self.model = model
        self.tokenizer = tokenizer
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.max_length = max_length
        self.batch_size = batch_size
        self.model.to(self.device)
        self.model.eval()

    @classmethod
    def from_pretrained(
        cls,
        model_name_or_path: str | Path = "google-bert/bert-base-uncased",
        *,
        local_files_only: bool = False,
        max_length: int = 128,
        batch_size: int = 16,
    ) -> "BertTextEncoder":
        tokenizer = AutoTokenizer.from_pretrained(
            str(model_name_or_path), local_files_only=local_files_only
        )
        model = AutoModel.from_pretrained(
            str(model_name_or_path), local_files_only=local_files_only
        )
        return cls(model, tokenizer, max_length=max_length, batch_size=batch_size)

    def save_pretrained(self, path: str | Path) -> None:
        output_dir = Path(path)
        output_dir.mkdir(parents=True, exist_ok=True)
        self.tokenizer.save_pretrained(output_dir)
        self.model.save_pretrained(output_dir)

    def encode(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.empty((0, self.model.config.hidden_size), dtype=np.float32)

        vectors: list[np.ndarray] = []
        with torch.no_grad():
            for start in range(0, len(texts), self.batch_size):
                batch = texts[start : start + self.batch_size]
                encoded = self.tokenizer(
                    batch,
                    padding=True,
                    truncation=True,
                    max_length=self.max_length,
                    return_tensors="pt",
                )
                encoded = {key: value.to(self.device) for key, value in encoded.items()}
                outputs = self.model(**encoded)
                cls_embeddings = outputs.last_hidden_state[:, 0, :]
                vectors.append(cls_embeddings.cpu().numpy())

        return np.vstack(vectors).astype(np.float32)
