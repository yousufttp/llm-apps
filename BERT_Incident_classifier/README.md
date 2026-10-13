# BERT Incident Classifier

Local Python project for classifying incident tickets into a support `group` and `category` from the ticket short description.

The project is built for a Windows 11 + VS Code + uv workflow. It reads historical labeled incidents from Excel, uses `google-bert/bert-base-uncased` as a frozen text encoder, trains a scikit-learn logistic regression classifier, and saves all artifacts locally for repeatable daily inference.

## What This Project Does

The workflow has two separate commands:

1. `train` downloads or loads BERT, encodes historical labeled incidents, trains the classifier, and saves local artifacts.
2. `classify-daily` loads the saved artifacts and classifies a new daily incident Excel file without retraining.

Daily output includes:

```text
incident_number, predicted_group, predicted_category, confidence, manual_review
```

Rows below the configured confidence threshold are marked for manual review.

## Project Structure

```text
.
├── main.py
├── pyproject.toml
├── README.md
├── src/
│   └── incident_classifier/
│       ├── cli.py
│       ├── data.py
│       ├── encoder.py
│       ├── inference.py
│       ├── model.py
│       └── training.py
└── tests/
    └── test_incident_classifier.py
```

The command name `incident-classifier` is defined in `pyproject.toml` and points to `incident_classifier.cli:main`. If you prefer running a Python file directly, use `uv run python main.py ...`.

## Input Files

Training Excel columns:

```text
incident_number, short_description, group, category
```

Daily Excel columns:

```text
incident_number, short_description
```

Keep real company Excel files local. The `.gitignore` excludes `*.xlsx`, model artifacts, generated outputs, and Python cache files.

## Setup

Run these commands in PowerShell from this folder:

```powershell
uv sync
```

## First-Time Model Download

The first training run needs internet access so Hugging Face can download:

```text
google-bert/bert-base-uncased
```

After training, the model and tokenizer are saved under:

```text
artifacts\bert-base-uncased\
```

Daily classification loads that local copy only.

## Train

The first training run downloads `google-bert/bert-base-uncased` from Hugging Face and saves the model, tokenizer, classifier, evaluation report, and confusion matrix locally.

```powershell
uv run incident-classifier train `
  --training-excel .\training_incidents.xlsx `
  --artifacts-dir .\artifacts `
  --confidence-threshold 0.65
```

Training writes:

```text
artifacts\bert-base-uncased\
artifacts\incident_classifier.joblib
artifacts\evaluation_report.txt
artifacts\confusion_matrix.csv
```

The train command uses an 80/20 split. It stratifies by the combined `group/category` label when each label has enough rows for both train and test sets; otherwise it falls back to a random 80/20 split and says so in the report.

The evaluation report includes precision, recall, and f1-score per label. It also calls out the focus categories:

```text
Pending Order
Activation
Switch
```

## Classify Daily Incidents

Daily classification loads the saved artifacts from disk with local model loading enabled.

```powershell
uv run incident-classifier classify-daily `
  --daily-excel .\daily_incidents.xlsx `
  --artifacts-dir .\artifacts `
  --output-excel .\classified_incidents.xlsx
```

Output columns:

```text
incident_number, predicted_group, predicted_category, confidence, manual_review
```

Rows below the confidence threshold are marked `manual_review = TRUE`.

## Running With Python File Commands

Training:

```powershell
uv run python main.py train `
  --training-excel .\training_incidents.xlsx `
  --artifacts-dir .\artifacts `
  --confidence-threshold 0.65
```

Daily inference:

```powershell
uv run python main.py classify-daily `
  --daily-excel .\daily_incidents.xlsx `
  --artifacts-dir .\artifacts `
  --output-excel .\classified_incidents.xlsx
```

## Checks

```powershell
uv run pytest
```

The tests use synthetic incident data and a fake encoder. They do not use real company data and do not download Hugging Face models.

## Notes

- BERT is frozen in v1. Only the logistic regression classifier is trained.
- Daily inference is intentionally separate from training so it can run without retraining.
- The saved classifier lives at `artifacts\incident_classifier.joblib`.
- The saved BERT model/tokenizer lives at `artifacts\bert-base-uncased\`.
- Real `.xlsx` files and downloaded model artifacts are ignored by git.
