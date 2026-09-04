"""
Data validation with Pydantic schemas for Power BI ETL pipelines.
"""

from typing import Type, TypeVar, Generic, List, Dict, Any, Optional
from pydantic import BaseModel, ValidationError
import pandas as pd
import structlog

logger = structlog.get_logger(__name__)

T = TypeVar("T", bound=BaseModel)


class ValidationResult(Generic[T]):
    """Result of validation with valid/invalid separation."""

    def __init__(
        self,
        valid: List[T],
        invalid: List[Dict[str, Any]],
        errors: List[Dict[str, Any]],
        quarantined: List[Dict[str, Any]] = None,
    ):
        self.valid = valid
        self.invalid = invalid
        self.errors = errors
        self.quarantined = quarantined or []

    @property
    def total_records(self) -> int:
        return len(self.valid) + len(self.invalid)

    @property
    def success_rate(self) -> float:
        total = self.total_records
        return len(self.valid) / total if total > 0 else 1.0

    @property
    def quarantine_rate(self) -> float:
        total = self.total_records
        return len(self.quarantined) / total if total > 0 else 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_records": self.total_records,
            "valid_records": len(self.valid),
            "invalid_records": len(self.invalid),
            "quarantined_records": len(self.quarantined),
            "success_rate": round(self.success_rate * 100, 2),
            "quarantine_rate": round(self.quarantine_rate * 100, 2),
            "errors": self.errors[:10],  # First 10 errors
        }


def validate_dataframe(
    df: pd.DataFrame,
    model: Type[T],
    id_column: str = None,
    quarantine_threshold: float = 0.5,  # Quarantine if >50% invalid
) -> ValidationResult[T]:
    """
    Validate DataFrame rows against Pydantic model.

    Args:
        df: Input dataframe
        model: Pydantic model class
        id_column: Column name for record identification
        quarantine_threshold: If invalid rate exceeds this, quarantine all invalid

    Returns:
        ValidationResult with separated valid/invalid records
    """
    valid_records = []
    invalid_records = []
    errors = []
    quarantined = []

    for idx, row in df.iterrows():
        try:
            # Convert row to dict, handling pandas types
            row_dict = {}
            for col, val in row.items():
                if pd.isna(val):
                    row_dict[col] = None
                elif isinstance(val, (pd.Timestamp,)):
                    row_dict[col] = val.to_pydatetime() if not pd.isna(val) else None
                else:
                    row_dict[col] = val

            record = model(**row_dict)
            valid_records.append(record)
        except ValidationError as e:
            invalid_records.append(row.to_dict() if hasattr(row, 'to_dict') else dict(row))
            errors.append({
                "row_index": int(idx),
                "record_id": row.get(id_column) if id_column and hasattr(row, 'get') else None,
                "errors": e.errors(),
            })

    # Quarantine logic
    if errors and (len(errors) / len(df)) > quarantine_threshold:
        # High error rate - quarantine all invalid
        quarantined = invalid_records.copy()
        invalid_records = []
        logger.warning(
            "High validation error rate - quarantining all invalid records",
            error_rate=len(errors) / len(df),
            threshold=quarantine_threshold,
        )

    logger.info(
        "Validation complete",
        total=len(df),
        valid=len(valid_records),
        invalid=len(invalid_records),
        quarantined=len(quarantined),
        success_rate=f"{len(valid_records)/len(df)*100:.1f}%" if len(df) > 0 else "100%",
    )

    return ValidationResult(valid_records, invalid_records, errors, quarantined)


def quarantine_invalid(
    df: pd.DataFrame,
    invalid_indices: List[int],
    quarantine_path: str,
    reason: str = "Validation failed",
) -> pd.DataFrame:
    """
    Move invalid rows to quarantine file and return cleaned dataframe.

    Args:
        df: Original dataframe
        invalid_indices: Row indices to quarantine
        quarantine_path: Path to save quarantine file
        reason: Reason for quarantine

    Returns:
        Cleaned dataframe with invalid rows removed
    """
    import json
    from pathlib import Path

    Path(quarantine_path).parent.mkdir(parents=True, exist_ok=True)

    invalid_df = df.loc[invalid_indices].copy()
    invalid_df["_quarantine_reason"] = reason
    invalid_df["_quarantined_at"] = pd.Timestamp.now()

    # Save as parquet for efficiency
    invalid_df.to_parquet(quarantine_path, index=False)

    logger.info("Quarantined invalid records", count=len(invalid_df), path=quarantine_path)

    return df.drop(index=invalid_indices)


def validate_tender_dataframe(df: pd.DataFrame) -> ValidationResult:
    """Validate tender dataframe using TenderRaw schema."""
    from ..config.schemas import TenderRaw
    return validate_dataframe(df, TenderRaw, id_column="TenderID")


def validate_financial_dataframe(df: pd.DataFrame) -> ValidationResult:
    """Validate financial dataframe using FinancialTransactionRaw schema."""
    from ..config.schemas import FinancialTransactionRaw
    return validate_dataframe(df, FinancialTransactionRaw, id_column="TransactionID")