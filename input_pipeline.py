from __future__ import annotations

import io
import json

import pandas as pd

from research import prepare_financials
from sec_connector import SecInputError, company_facts_to_frame, fetch_company_facts


MAX_IDENTIFIERS = 5
MAX_UPLOAD_BYTES = 10 * 1024 * 1024


def parse_identifiers(value: str) -> list[str]:
    identifiers = list(
        dict.fromkeys(item.strip().upper() for item in value.replace("\n", ",").split(",") if item.strip())
    )
    if not identifiers:
        raise SecInputError("Enter at least one ticker or CIK.")
    if len(identifiers) > MAX_IDENTIFIERS:
        raise SecInputError(f"At most {MAX_IDENTIFIERS} identifiers may be loaded in one run.")
    return identifiers


def _check_upload_size(content: bytes) -> None:
    if not content:
        raise ValueError("The uploaded file is empty.")
    if len(content) > MAX_UPLOAD_BYTES:
        raise ValueError("The uploaded file exceeds the 10 MB in-memory limit.")


def financial_csv_from_bytes(content: bytes) -> pd.DataFrame:
    _check_upload_size(content)
    try:
        frame = pd.read_csv(io.BytesIO(content))
    except (UnicodeDecodeError, pd.errors.ParserError) as error:
        raise ValueError("The uploaded CSV could not be parsed as a tabular financial file.") from error
    return prepare_financials(frame, input_source="uploaded_csv")


def company_facts_json_from_bytes(
    content: bytes,
    *,
    ticker: str | None = None,
    years: int = 5,
) -> pd.DataFrame:
    _check_upload_size(content)
    try:
        payload = json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("The uploaded file is not valid UTF-8 SEC Company Facts JSON.") from error
    frame = company_facts_to_frame(payload, ticker=ticker or None, years=years)
    return prepare_financials(frame, input_source="uploaded_sec_json")


def online_company_facts(
    identifiers: list[str],
    *,
    years: int,
    user_agent: str | None = None,
) -> pd.DataFrame:
    if not identifiers:
        raise SecInputError("Enter at least one ticker or CIK.")
    if len(identifiers) > MAX_IDENTIFIERS:
        raise SecInputError(f"At most {MAX_IDENTIFIERS} identifiers may be loaded in one run.")
    frames = [fetch_company_facts(identifier, years=years, user_agent=user_agent) for identifier in identifiers]
    return prepare_financials(pd.concat(frames, ignore_index=True), input_source="online_sec")
