from __future__ import annotations

from io import BytesIO

import pandas as pd
import pytest
import requests

import main


def incidents(count: int = 2) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Issue Description": [f"Issue {i}" for i in range(count)],
            "Short Description": [f"Short {i}" for i in range(count)],
            "Resolution": [f"Resolution {i}" for i in range(count)],
        }
    )


class Response:
    def __init__(self, body, error=None):
        self.body = body
        self.error = error

    def raise_for_status(self):
        if self.error:
            raise self.error

    def json(self):
        return self.body


def answer(probability: float):
    return {"answers": {"valid reopen": {"type": "noul", "noul": probability}}}


def test_prepare_incidents_drops_blank_resolutions_and_preserves_order():
    frame = incidents(4)
    frame.loc[1, "Resolution"] = "  "
    frame.loc[2, "Resolution"] = None
    prepared, dropped = main.prepare_incidents(frame)
    assert dropped == 2
    assert prepared.index.tolist() == [0, 3]


def test_validate_columns_requires_exact_names():
    frame = incidents().rename(columns={"Resolution": "resolution"})
    assert main.validate_columns(frame) == ["Resolution"]


def test_classification_batches_and_uses_true_probability():
    frame = incidents(65)
    batch_sizes = []

    def post(url, *, json, timeout):
        batch_sizes.append(len(json["states"]))
        assert url == "http://api.test/predict/batch"
        assert json["questions"] == main.QUESTION
        return Response({"results": [answer(0.5 if state["resolution"] == "Resolution 0" else 0.2) for state in json["states"]]})

    result = main.classify_incidents(frame, "http://api.test/", post=post)
    assert batch_sizes == [64, 1]
    assert bool(result.iloc[0]["Valid Reopen"]) is True
    assert result.iloc[0]["Valid Reopen Probability"] == 0.5
    assert bool(result.iloc[1]["Valid Reopen"]) is False
    assert result["Processing Error"].eq("").all()


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ({"results": [{"error": "model failed"}]}, "model failed"),
        ({"results": [{}]}, "missing the valid reopen probability"),
        ({"unexpected": []}, "unexpected number of batch results"),
    ],
)
def test_row_and_malformed_response_errors_are_retained(body, message):
    result = main.classify_incidents(incidents(1), "http://api.test", post=lambda *args, **kwargs: Response(body))
    assert pd.isna(result.iloc[0]["Valid Reopen"])
    assert message in result.iloc[0]["Processing Error"]


@pytest.mark.parametrize(
    ("exception", "message"),
    [(requests.Timeout(), "timed out"), (requests.ConnectionError(), "Could not connect")],
)
def test_transport_errors_are_retained(exception, message):
    def post(*args, **kwargs):
        raise exception

    result = main.classify_incidents(incidents(2), "http://api.test", post=post)
    assert result["Processing Error"].str.contains(message).all()


def test_successful_rows_survive_individual_failures():
    body = {"results": [answer(0.9), {"index": 1, "error": "bad row"}]}
    result = main.classify_incidents(incidents(2), "http://api.test", post=lambda *args, **kwargs: Response(body))
    assert bool(result.iloc[0]["Valid Reopen"]) is True
    assert result.iloc[1]["Processing Error"] == "bad row"


def test_results_can_be_downloaded_and_read_back():
    frame = incidents(1)
    frame["Valid Reopen"] = pd.array([True], dtype="boolean")
    frame["Valid Reopen Probability"] = [0.75]
    frame["Processing Error"] = [""]

    downloaded = pd.read_excel(BytesIO(main.workbook_bytes(frame)), engine="openpyxl")

    assert bool(downloaded.loc[0, "Valid Reopen"]) is True
    assert downloaded.loc[0, "Valid Reopen Probability"] == 0.75
