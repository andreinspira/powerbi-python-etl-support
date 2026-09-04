"""
Helper utilities for Power BI ETL pipelines.
"""

import pandas as pd
import numpy as np
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import hashlib
import structlog

logger = structlog.get_logger(__name__)


def generate_sample_tender_data(n_records: int = 50, seed: int = 42) -> pd.DataFrame:
    """
    Generate synthetic tender register data matching PP-010/PP-011 requirements.
    
    This creates realistic sample data for:
    - Tender Dashboard (.pbix) portfolio asset
    - Python ETL pipeline demonstration
    - Power BI + Python Support Collaborator role
    """
    import random
    from datetime import date, timedelta
    from decimal import Decimal
    
    random.seed(seed)
    np.random.seed(seed)
    
    divisions = ["Commercial", "Infrastructure", "Energy", "Technology", "Healthcare"]
    statuses = ["Won", "Submitted", "In Progress", "Lost", "Declined", "Cancelled", "On Hold"]
    owners = ["J. Silva", "M. Santos", "A. Costa", "R. Oliveira", "P. Lima", "C. Ferreira", "D. Almeida", "E. Rocha"]
    clients = [
        "Ministry of Transport", "Global Corp Ltd", "Tech Solutions Inc", "Finance Bank SA",
        "City Council", "Health Ministry", "Retail Group", "Port Authority",
        "Telecom Provider", "Rail Company", "Energy Corp", "Construction Ltd"
    ]
    
    data = []
    base_date = date(2025, 1, 1)
    
    for i in range(1, n_records + 1):
        tender_id = f"TND-2025-{i:03d}"
        project_name = f"{random.choice(['Bridge', 'Building', 'Road', 'IT System', 'Dashboard', 'Platform', 'Renovation', 'Expansion'])} Project {i}"
        client = random.choice(clients)
        division = random.choice(divisions)
        status = random.choice(statuses)
        
        # Dates with some missing for data quality demonstration
        has_dates = random.random() > 0.15  # 15% missing dates
        
        if has_dates:
            received = base_date + timedelta(days=random.randint(0, 300))
            submission = received + timedelta(days=random.randint(1, 60))
            start = submission + timedelta(days=random.randint(30, 180))
            end = start + timedelta(days=random.randint(90, 1000))
        else:
            received = submission = start = end = None
        
        # Values
        tender_value = Decimal(str(round(random.uniform(100000, 10000000), 2)))
        probability = Decimal(str(round(random.uniform(0.1, 0.9), 2)))
        weighted = tender_value * probability
        
        # Some records with forecast, some without
        has_forecast = random.random() > 0.3
        
        data.append({
            "TenderID": tender_id,
            "ProjectName": project_name,
            "ClientName": client,
            "BusinessDivision": division,
            "TenderStatus": status,
            "TenderReceivedDate": received,
            "TenderSubmissionDate": submission,
            "ProjectStartDate": start,
            "ProjectEndDate": end,
            "TenderValue": tender_value,
            "ReportingValue": tender_value * Decimal(str(round(random.uniform(0.8, 1.2), 2))),
            "ProbabilityPercentage": probability,
            "WeightedValue": weighted,
            "ActionOwner": random.choice(owners),
            "MonthlyForecast": (weighted / 12) if has_forecast else None,
            "QuarterlyForecast": (weighted / 4) if has_forecast else None,
        })
    
    df = pd.DataFrame(data)
    df["_source_file"] = "Tender_Register_Sample.xlsx"
    df["_generated_at"] = datetime.now()
    
    logger.info("Generated sample tender data", records=n_records)
    return df


def create_sample_financial_data(n_records: int = 200, seed: int = 42) -> pd.DataFrame:
    """
    Generate synthetic financial transaction data for Power BI financial model.
    """
    import random
    from datetime import date, timedelta
    from decimal import Decimal
    
    random.seed(seed)
    np.random.seed(seed)
    
    accounts = [
        ("4000", "Revenue - Services", "Revenue", "P&L"),
        ("4010", "Revenue - Products", "Revenue", "P&L"),
        ("5000", "Cost of Services", "COGS", "P&L"),
        ("5010", "Cost of Products", "COGS", "P&L"),
        ("6000", "Salaries & Wages", "OpEx", "P&L"),
        ("6010", "Benefits & Taxes", "OpEx", "P&L"),
        ("6100", "Rent & Utilities", "OpEx", "P&L"),
        ("6200", "Marketing & Advertising", "OpEx", "P&L"),
        ("6300", "Travel & Entertainment", "OpEx", "P&L"),
        ("6400", "IT & Software", "OpEx", "P&L"),
        ("1000", "Cash & Equivalents", "Asset", "Balance Sheet"),
        ("1100", "Accounts Receivable", "Asset", "Balance Sheet"),
        ("2000", "Accounts Payable", "Liability", "Balance Sheet"),
        ("3000", "Retained Earnings", "Equity", "Balance Sheet"),
    ]
    
    departments = ["Sales", "Marketing", "Engineering", "G&A", "Operations"]
    cost_centers = [f"CC-{d[:3].upper()}-{i:03d}" for d in departments for i in range(1, 4)]
    entities = ["BR001", "US001", "UK001"]
    scenarios = ["Actual", "Budget", "Forecast"]
    currencies = ["USD", "EUR", "BRL", "GBP"]
    
    data = []
    base_date = date(2025, 1, 1)
    
    for i in range(n_records):
        acc_code, acc_name, acc_type, stmt_section = random.choice(accounts)
        dept = random.choice(departments)
        cc = random.choice([c for c in cost_centers if c.startswith(f"CC-{dept[:3].upper()}")])
        entity = random.choice(entities)
        scenario = random.choice(scenarios)
        currency = random.choice(currencies)
        
        # Amount varies by account type
        if acc_type == "Revenue":
            amount = Decimal(str(round(random.uniform(10000, 500000), 2)))
        elif acc_type == "COGS":
            amount = Decimal(str(round(random.uniform(5000, 200000), 2)))
        elif acc_type == "OpEx":
            amount = Decimal(str(round(random.uniform(1000, 100000), 2)))
        else:
            amount = Decimal(str(round(random.uniform(10000, 1000000), 2)))
        
        # Random date in 2025
        trans_date = base_date + timedelta(days=random.randint(0, 364))
        
        data.append({
            "TransactionID": f"TXN-2025-{i+1:06d}",
            "Date": trans_date,
            "AccountCode": acc_code,
            "AccountName": acc_name,
            "AccountType": acc_type,
            "StatementSection": stmt_section,
            "Department": dept,
            "CostCenter": cc,
            "Entity": entity,
            "Scenario": scenario,
            "AmountLocal": amount,
            "Currency": currency,
            "Description": f"{scenario} - {acc_name} - {dept}",
        })
    
    df = pd.DataFrame(data)
    df["_source_file"] = "Financial_Transactions_Sample.csv"
    df["_generated_at"] = datetime.now()
    
    logger.info("Generated sample financial data", records=n_records)
    return df


def save_dataframe_safely(
    df: pd.DataFrame,
    path: Path,
    formats: List[str] = None,
    **kwargs
) -> Dict[str, Path]:
    """
    Save dataframe to multiple formats atomically.
    Writes to temporary files first, then renames.
    """
    formats = formats or ["parquet"]
    saved = {}
    
    for fmt in formats:
        temp_path = path.with_suffix(f".{fmt}.tmp")
        final_path = path.with_suffix(f".{fmt}")
        
        temp_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            if fmt == "parquet":
                df.to_parquet(temp_path, index=False, **kwargs)
            elif fmt == "csv":
                df.to_csv(temp_path, index=False, **kwargs)
            elif fmt == "excel":
                df.to_excel(temp_path, index=False, **kwargs)
            elif fmt == "json":
                df.to_json(temp_path, orient="records", date_format="iso", **kwargs)
            else:
                logger.warning("Unsupported format", format=fmt)
                continue
            
            # Atomic rename
            temp_path.replace(final_path)
            saved[fmt] = final_path
            logger.debug("DataFrame saved", format=fmt, path=str(final_path))
            
        except Exception as e:
            logger.error("Failed to save DataFrame", format=fmt, error=str(e))
            if temp_path.exists():
                temp_path.unlink(missing_ok=True)
            raise
    
    return saved


def load_dataframe_safely(path: Path, **kwargs) -> pd.DataFrame:
    """
    Load dataframe from file with automatic format detection.
    """
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    
    suffix = path.suffix.lower()
    
    try:
        if suffix == ".parquet":
            return pd.read_parquet(path, **kwargs)
        elif suffix == ".csv":
            return pd.read_csv(path, **kwargs)
        elif suffix in [".xlsx", ".xls"]:
            return pd.read_excel(path, **kwargs)
        elif suffix == ".json":
            return pd.read_json(path, **kwargs)
        else:
            raise ValueError(f"Unsupported file format: {suffix}")
    except Exception as e:
        logger.error("Failed to load DataFrame", path=str(path), error=str(e))
        raise


def hash_dataframe(df: pd.DataFrame, columns: List[str] = None) -> str:
    """
    Compute SHA256 hash of dataframe for change detection.
    """
    if columns:
        df = df[columns]
    
    # Create deterministic string representation
    content = df.to_json(orient="records", date_format="iso", force_ascii=True)
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def compare_dataframes(
    df1: pd.DataFrame,
    df2: pd.DataFrame,
    key_columns: List[str] = None,
    tolerance: float = 1e-10,
) -> Dict[str, Any]:
    """
    Compare two dataframes and return differences.
    
    Returns dict with:
    - shape_match: bool
    - columns_match: bool
    - rows_added: int
    - rows_removed: int
    - rows_changed: int
    - value_differences: list of dicts
    """
    result = {
        "shape_match": df1.shape == df2.shape,
        "columns_match": list(df1.columns) == list(df2.columns),
        "df1_shape": df1.shape,
        "df2_shape": df2.shape,
    }
    
    if key_columns:
        # Compare by key
        merged = df1.merge(df2, on=key_columns, how="outer", indicator=True, suffixes=("_1", "_2"))
        result["rows_only_in_1"] = len(merged[merged["_merge"] == "left_only"])
        result["rows_only_in_2"] = len(merged[merged["_merge"] == "right_only"])
        result["rows_in_both"] = len(merged[merged["_merge"] == "both"])
        
        # Value differences for common rows
        both = merged[merged["_merge"] == "both"]
        if len(both) > 0:
            diff_cols = []
            for col in df1.columns:
                if col in key_columns:
                    continue
                col1 = f"{col}_1"
                col2 = f"{col}_2"
                if col1 in both.columns and col2 in both.columns:
                    diffs = both[
                        (~both[col1].isna() | ~both[col2].isna()) &
                        (
                            (both[col1].isna() != both[col2].isna()) |
                            ((both[col1] - both[col2]).abs() > tolerance)
                        )
                    ]
                    if len(diffs) > 0:
                        diff_cols.append({
                            "column": col,
                            "differences": len(diffs),
                            "sample": diffs[[key_columns[0], col1, col2]].head(5).to_dict("records") if key_columns else diffs[[col1, col2]].head(5).to_dict("records"),
                        })
            result["value_differences"] = diff_cols
    else:
        # Simple comparison
        try:
            equal = df1.equals(df2)
            result["data_equal"] = equal
            if not equal:
                result["note"] = "DataFrames differ (use key_columns for detailed diff)"
        except Exception as e:
            result["comparison_error"] = str(e)
    
    return result