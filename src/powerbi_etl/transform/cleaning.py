"""
Data cleaning utilities for Power BI ETL pipelines.
"""

import pandas as pd
import numpy as np
from decimal import Decimal, InvalidOperation
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
import structlog

logger = structlog.get_logger(__name__)


def clean_string(value: Any) -> str:
    """Clean string values - trim whitespace, handle None."""
    if pd.isna(value) or value is None:
        return ""
    return str(value).strip()


def clean_numeric(value: Any) -> Optional[Decimal]:
    """Clean and convert to Decimal."""
    from decimal import Decimal
    if pd.isna(value) or value is None:
        return None
    if isinstance(value, (int, float, Decimal)):
        return Decimal(str(value))

    # Clean string numbers
    cleaned = str(value).replace(",", "").replace(" ", "").replace("$", "").replace("€", "").replace("£", "")
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        logger.warning("Could not convert to numeric", value=value)
        return None


def clean_date(value: Any, formats: List[str] = None) -> Optional[pd.Timestamp]:
    """Parse date with multiple format attempts."""
    if pd.isna(value) or value is None:
        return None
    if isinstance(value, (pd.Timestamp, datetime)):
        return pd.Timestamp(value)

    formats = formats or [
        "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%Y/%m/%d",
        "%d-%m-%Y", "%b %d, %Y", "%d %b %Y", "%Y%m%d",
    ]

    for fmt in formats:
        try:
            return pd.to_datetime(str(value), format=fmt)
        except ValueError:
            continue

    # Try pandas inference
    try:
        return pd.Timestamp(value)
    except Exception:
        logger.warning("Could not parse date", value=value)
        return None


def standardize_tender_status(status: str) -> str:
    """Standardize tender status values."""
    if not status:
        return "Unknown"

    status_map = {
        "lead": "Lead",
        "qualification": "Qualification",
        "qualified": "Qualification",
        "proposal": "Proposal",
        "proposed": "Proposal",
        "negotiation": "Negotiation",
        "negotiating": "Negotiation",
        "submitted": "Submitted",
        "won": "Won",
        "closed won": "Won",
        "awarded": "Won",
        "lost": "Lost",
        "closed lost": "Lost",
        "declined": "Declined",
        "cancelled": "Cancelled",
        "on hold": "On Hold",
        "in progress": "In Progress",
        "active": "In Progress",
    }
    normalized = status.lower().strip()
    return status_map.get(normalized, status.title())


def remove_duplicates(df: pd.DataFrame, subset: List[str], keep: str = "first") -> pd.DataFrame:
    """Remove duplicate rows based on subset of columns."""
    initial_len = len(df)
    df = df.drop_duplicates(subset=subset, keep=keep)
    removed = initial_len - len(df)
    if removed:
        logger.info("Removed duplicates", count=removed, subset=subset)
    return df


def handle_missing_values(df: pd.DataFrame, strategy: Dict[str, Any]) -> pd.DataFrame:
    """Handle missing values per column strategy."""
    for col, action in strategy.items():
        if col not in df.columns:
            continue
        if action == "drop":
            df = df.dropna(subset=[col])
        elif action == "zero":
            df[col] = df[col].fillna(0)
        elif action == "mean":
            df[col] = df[col].fillna(df[col].mean())
        elif action == "median":
            df[col] = df[col].fillna(df[col].median())
        elif action == "forward":
            df[col] = df[col].ffill()
        elif action == "backward":
            df[col] = df[col].bfill()
        elif isinstance(action, (str, int, float)):
            df[col] = df[col].fillna(action)
        elif callable(action):
            df[col] = df[col].apply(lambda x: action() if pd.isna(x) else x)
    return df


def enforce_schema(df: pd.DataFrame, schema: Dict[str, str]) -> pd.DataFrame:
    """Enforce data types per schema definition."""
    for col, dtype in schema.items():
        if col not in df.columns:
            continue
        try:
            if dtype in ("string", "str"):
                df[col] = df[col].astype(str)
            elif dtype in ("int", "int64", "Int64"):
                df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
            elif dtype in ("float", "float64"):
                df[col] = pd.to_numeric(df[col], errors="coerce")
            elif dtype == "decimal":
                df[col] = df[col].apply(clean_numeric)
            elif dtype in ("date", "datetime"):
                df[col] = df[col].apply(clean_date)
            elif dtype == "bool":
                df[col] = df[col].astype(bool)
        except Exception as e:
            logger.warning("Schema enforcement failed", column=col, dtype=dtype, error=str(e))
    return df


def clean_tender_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Apply standard cleaning to tender register dataframe."""
    # Make a copy to avoid modifying original
    df = df.copy()

    # Clean string columns
    string_columns = ["TenderID", "ProjectName", "ClientName", "BusinessDivision", "TenderStatus", "ActionOwner"]
    for col in string_columns:
        if col in df.columns:
            df[col] = df[col].apply(clean_string)

    # Standardize status
    if "TenderStatus" in df.columns:
        df["TenderStatus"] = df["TenderStatus"].apply(standardize_tender_status)

    # Clean numeric columns
    numeric_columns = ["TenderValue", "ReportingValue", "ProbabilityPercentage", "WeightedValue", "MonthlyForecast", "QuarterlyForecast"]
    for col in numeric_columns:
        if col in df.columns:
            df[col] = df[col].apply(clean_numeric)

    # Clean date columns
    date_columns = ["TenderReceivedDate", "TenderSubmissionDate", "ProjectStartDate", "ProjectEndDate"]
    for col in date_columns:
        if col in df.columns:
            df[col] = df[col].apply(clean_date)

    # Handle missing values
    missing_strategy = {
        "TenderValue": "zero",
        "ReportingValue": "zero",
        "ProbabilityPercentage": "zero",
        "WeightedValue": "zero",
        "MonthlyForecast": None,  # Keep as NaN
        "QuarterlyForecast": None,
        "TenderStatus": "Unknown",
    }
    df = handle_missing_values(df, missing_strategy)

    return df