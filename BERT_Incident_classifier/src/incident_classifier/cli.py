from __future__ import annotations

import argparse
from pathlib import Path

from incident_classifier.inference import classify_daily_excel
from incident_classifier.training import train_from_excel


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="incident-classifier",
        description="Train and run a local BERT incident classifier.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    train_parser = subparsers.add_parser("train", help="Train classifier artifacts.")
    train_parser.add_argument("--training-excel", required=True, type=Path)
    train_parser.add_argument("--artifacts-dir", default=Path("artifacts"), type=Path)
    train_parser.add_argument("--confidence-threshold", default=0.65, type=float)
    train_parser.add_argument(
        "--model-name", default="google-bert/bert-base-uncased"
    )

    daily_parser = subparsers.add_parser(
        "classify-daily", help="Classify a daily Excel file from saved artifacts."
    )
    daily_parser.add_argument("--daily-excel", required=True, type=Path)
    daily_parser.add_argument("--artifacts-dir", default=Path("artifacts"), type=Path)
    daily_parser.add_argument(
        "--output-excel", default=Path("classified_incidents.xlsx"), type=Path
    )

    args = parser.parse_args()
    if args.command == "train":
        result = train_from_excel(
            args.training_excel,
            args.artifacts_dir,
            confidence_threshold=args.confidence_threshold,
            model_name=args.model_name,
        )
        print(f"Saved BERT model/tokenizer: {result['bert_path']}")
        print(f"Saved classifier: {result['classifier_path']}")
        print(f"Saved evaluation report: {result['report_path']}")
        print(f"Saved confusion matrix: {result['confusion_path']}")
        print(result["split_note"])
    elif args.command == "classify-daily":
        output_df = classify_daily_excel(
            args.daily_excel,
            args.artifacts_dir,
            args.output_excel,
            local_files_only=True,
        )
        review_count = int(output_df["manual_review"].sum())
        print(f"Wrote predictions: {args.output_excel}")
        print(f"Manual review rows: {review_count}")


if __name__ == "__main__":
    main()
