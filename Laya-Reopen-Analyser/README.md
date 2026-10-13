# Laya Reopen Analyser

Laya Reopen Analyser classifies incident records from an Excel workbook and identifies whether each resolution indicates that the original customer issue remains unresolved.

![Laya Reopen Analyser interface](GUI.png)

## Features

- Upload an `.xlsx` workbook through a Streamlit interface.
- Process incidents with the local Laya model through the `/predict/batch` endpoint.
- Add a `Valid Reopen` verdict and probability to every processed row.
- Preserve row-level errors and download the results as a new Excel workbook.
- Process large worksheets in API batches of 64 rows.

## Requirements

- Python 3.13 or newer
- [uv](https://docs.astral.sh/uv/)
- Internet access for the initial Laya model download

The first worksheet must contain these exact column names:

```text
Issue Description
Short Description
Resolution
```

Rows with an empty `Resolution` are excluded from processing.

## Installation

Clone the repository and install its locked dependencies:

```powershell
git clone https://github.com/yousufttp/Laya-Reopen-Analyser.git
cd Laya-Reopen-Analyser
uv sync
```

## Running the application

Start the API in one terminal:

```powershell
uv run python server.py
```

Wait until the API reports that startup is complete. The first launch can take longer while Laya downloads and loads its model.

Start the Streamlit interface in a second terminal:

```powershell
uv run streamlit run main.py
```

Open [http://localhost:8501](http://localhost:8501), upload the workbook, and select **Process incidents**.

The UI connects to `http://127.0.0.1:8000` by default. To use another API address, set `LAYA_API_URL` before starting Streamlit:

```powershell
$env:LAYA_API_URL = "http://server-address:8000"
uv run streamlit run main.py
```

## Tests

```powershell
uv run --with pytest python -m pytest -q
```
