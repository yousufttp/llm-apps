"""Streamlit UI for classifying incident reopen requests from Excel."""

from __future__ import annotations

import hashlib
import os
from io import BytesIO
from typing import Any, Callable, Iterable

import pandas as pd
import requests
import streamlit as st


REQUIRED_COLUMNS = ("Issue Description", "Short Description", "Resolution")
BATCH_SIZE = 64
DEFAULT_API_URL = "http://127.0.0.1:8000"
REQUEST_TIMEOUT_SECONDS = 120
QUESTION = {
    "valid reopen": {
        "type": "noul",
        "instructions": "Is `resolution` explains the customer that the original issue not resolved?",
        "criteria": {"true": "", "false": ""},
    }
}


def validate_columns(frame: pd.DataFrame) -> list[str]:
    """Return required columns that are absent from the first worksheet."""
    return [column for column in REQUIRED_COLUMNS if column not in frame.columns]


def prepare_incidents(frame: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Remove rows without a usable resolution and preserve source order/index."""
    resolution = frame["Resolution"]
    keep = resolution.notna() & resolution.astype(str).str.strip().ne("")
    prepared = frame.loc[keep].copy()
    return prepared, int((~keep).sum())


def _cell_text(value: Any) -> str:
    return "" if pd.isna(value) else str(value)


def build_states(frame: pd.DataFrame) -> list[dict[str, str]]:
    """Convert worksheet rows into the state records accepted by the API."""
    return [
        {
            "issue description": _cell_text(row["Issue Description"]),
            "short description": _cell_text(row["Short Description"]),
            "resolution": _cell_text(row["Resolution"]),
        }
        for _, row in frame.iterrows()
    ]


def _chunks(values: list[dict[str, str]], size: int = BATCH_SIZE) -> Iterable[list[dict[str, str]]]:
    for start in range(0, len(values), size):
        yield values[start : start + size]


def _parse_result(result: Any) -> tuple[bool | None, float | None, str]:
    if not isinstance(result, dict):
        return None, None, "The API returned a malformed result."
    if result.get("error"):
        return None, None, str(result["error"])

    answers = result.get("answers")
    answer = answers.get("valid reopen") if isinstance(answers, dict) else None
    probability = answer.get("noul") if isinstance(answer, dict) else None
    if isinstance(probability, bool) or not isinstance(probability, (int, float)):
        return None, None, "The API result is missing the valid reopen probability."

    probability = float(probability)
    if not 0.0 <= probability <= 1.0:
        return None, None, "The API returned a valid reopen probability outside 0–1."
    return probability >= 0.5, probability, ""


def classify_incidents(
    frame: pd.DataFrame,
    api_url: str,
    *,
    post: Callable[..., Any] = requests.post,
    progress: Callable[[int, int], None] | None = None,
) -> pd.DataFrame:
    """Classify incidents in API-sized batches and return the augmented rows."""
    output = frame.copy()
    states = build_states(output)
    verdicts: list[bool | None] = []
    probabilities: list[float | None] = []
    errors: list[str] = []
    endpoint = f"{api_url.rstrip('/')}/predict/batch"
    processed = 0

    for batch in _chunks(states):
        payload = {"states": batch, "questions": QUESTION}
        try:
            response = post(endpoint, json=payload, timeout=REQUEST_TIMEOUT_SECONDS)
            response.raise_for_status()
            body = response.json()
            results = body.get("results") if isinstance(body, dict) else None
            if not isinstance(results, list) or len(results) != len(batch):
                raise ValueError("The API returned an unexpected number of batch results.")
            parsed = [_parse_result(result) for result in results]
        except requests.Timeout:
            parsed = [(None, None, "The API request timed out.")] * len(batch)
        except requests.ConnectionError:
            parsed = [(None, None, "Could not connect to the API.")] * len(batch)
        except requests.RequestException as exc:
            parsed = [(None, None, f"API request failed: {exc}")] * len(batch)
        except (ValueError, TypeError) as exc:
            parsed = [(None, None, str(exc))] * len(batch)

        for verdict, probability, error in parsed:
            verdicts.append(verdict)
            probabilities.append(probability)
            errors.append(error)
        processed += len(batch)
        if progress:
            progress(processed, len(states))

    output["Valid Reopen"] = pd.array(verdicts, dtype="boolean")
    output["Valid Reopen Probability"] = probabilities
    output["Processing Error"] = errors
    return output


def workbook_bytes(frame: pd.DataFrame) -> bytes:
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        frame.to_excel(writer, index=False, sheet_name="Results")
    return buffer.getvalue()


def _read_workbook(uploaded_file: Any) -> pd.DataFrame:
    return pd.read_excel(uploaded_file, sheet_name=0, engine="openpyxl")


def run_app() -> None:
    st.set_page_config(page_title="Incident Reopen Classifier", page_icon="📋", layout="wide")
    st.markdown(
        """
        <style>
        [data-testid="stHeader"], [data-testid="stToolbar"] { display: none; }
        .stApp { padding-top: 0; }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.title("Incident Reopen Classifier")
    st.caption("Upload the first worksheet of an Excel workbook and classify each incident resolution.")

    api_url = os.getenv("LAYA_API_URL", DEFAULT_API_URL).strip()
    uploaded = st.file_uploader("Excel workbook", type=["xlsx"])

    upload_signature = None
    if uploaded is not None:
        upload_signature = hashlib.sha256(uploaded.getvalue()).hexdigest()
    if st.session_state.get("upload_signature") != upload_signature:
        st.session_state["upload_signature"] = upload_signature
        st.session_state.pop("incident_results", None)
        st.session_state.pop("incident_counts", None)

    frame: pd.DataFrame | None = None
    missing: list[str] = []
    read_error = ""
    if uploaded is not None:
        try:
            frame = _read_workbook(uploaded)
            missing = validate_columns(frame)
        except Exception as exc:
            read_error = f"Could not read the workbook: {exc}"

    if read_error:
        st.error(read_error)
    elif missing:
        st.error("Missing required columns: " + ", ".join(missing))
    elif frame is not None:
        st.success(f"Loaded {len(frame):,} rows from the first worksheet.")

    can_process = frame is not None and not missing and not read_error and bool(api_url)
    if st.button("Process incidents", type="primary", disabled=not can_process):
        assert frame is not None
        prepared, dropped = prepare_incidents(frame)
        if prepared.empty:
            st.warning("No rows have a non-blank Resolution value. Nothing was sent to the API.")
            st.session_state.pop("incident_results", None)
            st.session_state["incident_counts"] = (len(frame), dropped, 0, 0)
        else:
            bar = st.progress(0.0, text="Processing incidents…")

            def update_progress(done: int, total: int) -> None:
                bar.progress(done / total, text=f"Processed {done:,} of {total:,} incidents")

            results = classify_incidents(prepared, api_url, progress=update_progress)
            bar.empty()
            failed = int(results["Processing Error"].ne("").sum())
            st.session_state["incident_results"] = results
            st.session_state["incident_counts"] = (len(frame), dropped, len(results) - failed, failed)

    counts = st.session_state.get("incident_counts")
    if counts:
        uploaded_count, dropped_count, success_count, failed_count = counts
        columns = st.columns(4)
        for column, label, value in zip(
            columns,
            ("Uploaded", "Dropped", "Successful", "Failed"),
            (uploaded_count, dropped_count, success_count, failed_count),
        ):
            column.metric(label, f"{value:,}")

    results = st.session_state.get("incident_results")
    if isinstance(results, pd.DataFrame):
        st.subheader("Results")
        st.dataframe(
            results,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Valid Reopen Probability": st.column_config.ProgressColumn(
                    "Valid Reopen Probability", min_value=0.0, max_value=1.0, format="percent"
                )
            },
        )
        st.download_button(
            "Download results",
            data=workbook_bytes(results),
            file_name="incident_reopen_results.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )


def main() -> None:
    run_app()


if __name__ == "__main__":
    main()
