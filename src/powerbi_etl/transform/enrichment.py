"""
Data enrichment and calculated fields for Power BI ETL pipelines.
Implements key business logic: monthly/quarterly spreads, financial periods, FX rates.
"""

import pandas as pd
import numpy as np
from decimal import Decimal
from datetime import date, datetime
from typing import Dict, List, Optional, Any
import structlog

logger = structlog.get_logger(__name__)


def calculate_tender_spreads(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate monthly and quarterly spreads for tender values.
    
    This is a KEY requirement from PP-010/PP-011:
    "Distribute project values across the period between each project's 
    start and end dates. Calculate monthly and quarterly forecast values 
    without requiring separate forecast columns in Excel."
    
    The spread distributes the tender/reporting value evenly across months
    between ProjectStartDate and ProjectEndDate.
    """
    df = df.copy()
    
    # Ensure date columns are datetime
    date_cols = ["ProjectStartDate", "ProjectEndDate"]
    for col in date_cols:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
    
    # Calculate project duration in months
    def calc_duration_months(row):
        start = row.get("ProjectStartDate")
        end = row.get("ProjectEndDate")
        if pd.isna(start) or pd.isna(end):
            return None
        # Calculate months between dates
        months = (end.year - start.year) * 12 + (end.month - start.month)
        if end.day < start.day:
            months -= 1
        return max(1, months)  # At least 1 month
    
    df["ProjectDurationMonths"] = df.apply(calc_duration_months, axis=1)
    
    # Calculate monthly spread (value / duration months)
    def calc_monthly_spread(row):
        duration = row.get("ProjectDurationMonths")
        value = row.get("ReportingValue") or row.get("TenderValue")
        if duration and duration > 0 and value is not None:
            try:
                return float(value) / duration
            except (TypeError, ValueError, ZeroDivisionError):
                return None
        return None
    
    df["MonthlySpread"] = df.apply(calc_monthly_spread, axis=1)
    
    # Calculate quarterly spread
    def calc_quarterly_spread(row):
        monthly = row.get("MonthlySpread")
        if monthly is not None:
            return monthly * 3
        return None
    
    df["QuarterlySpread"] = df.apply(calc_quarterly_spread, axis=1)
    
    # Calculate weighted monthly spread (using probability-weighted value)
    def calc_weighted_monthly_spread(row):
        duration = row.get("ProjectDurationMonths")
        weighted = row.get("WeightedValue")
        if duration and duration > 0 and weighted is not None:
            try:
                return float(weighted) / duration
            except (TypeError, ValueError, ZeroDivisionError):
                return None
        return None
    
    df["WeightedMonthlySpread"] = df.apply(calc_weighted_monthly_spread, axis=1)
    
    # Flag records with missing dates (PP-011 requirement: "Clearly identify records with missing or TBC dates")
    df["HasMissingDates"] = df["ProjectStartDate"].isna() | df["ProjectEndDate"].isna()
    df["MissingDateFields"] = df.apply(
        lambda r: ", ".join([c for c in ["ProjectStartDate", "ProjectEndDate"] if pd.isna(r.get(c))]),
        axis=1
    )
    
    logger.info(
        "Calculated tender spreads",
        total=len(df),
        with_spread=df["MonthlySpread"].notna().sum(),
        missing_dates=df["HasMissingDates"].sum(),
    )
    
    return df


def calculate_financial_periods(df: pd.DataFrame, date_column: str = "Date", fiscal_year_start_month: int = 1) -> pd.DataFrame:
    """
    Add financial/fiscal period columns to dataframe.
    
    Args:
        df: Input dataframe
        date_column: Column containing the date
        fiscal_year_start_month: Month when fiscal year starts (1=Jan, 4=Apr, 7=Jul, 10=Oct)
    
    Returns:
        Dataframe with added fiscal period columns
    """
    df = df.copy()
    
    if date_column not in df.columns:
        logger.warning("Date column not found", column=date_column)
        return df
    
    dates = pd.to_datetime(df[date_column], errors="coerce")
    
    # Standard calendar periods
    df["CalendarYear"] = dates.dt.year
    df["CalendarQuarter"] = dates.dt.quarter
    df["CalendarMonth"] = dates.dt.month
    df["CalendarMonthName"] = dates.dt.strftime("%b")
    df["CalendarWeek"] = dates.dt.isocalendar().week
    df["YearMonth"] = dates.dt.strftime("%Y-%m")
    df["YearQuarter"] = dates.dt.year.astype(str) + "-Q" + dates.dt.quarter.astype(str)
    
    # Fiscal periods
    if fiscal_year_start_month == 1:
        # Calendar year = Fiscal year
        df["FiscalYear"] = df["CalendarYear"]
        df["FiscalQuarter"] = df["CalendarQuarter"]
        df["FiscalMonth"] = df["CalendarMonth"]
    else:
        # Calculate fiscal year
        month = dates.dt.month
        year = dates.dt.year
        df["FiscalYear"] = np.where(
            month >= fiscal_year_start_month,
            year + 1,
            year
        )
        # Fiscal month (1-12)
        df["FiscalMonth"] = np.where(
            month >= fiscal_year_start_month,
            month - fiscal_year_start_month + 1,
            month + 12 - fiscal_year_start_month + 1
        )
        # Fiscal quarter
        df["FiscalQuarter"] = ((df["FiscalMonth"] - 1) // 3) + 1
    
    df["FiscalPeriod"] = df["FiscalYear"].astype(str) + "-P" + df["FiscalMonth"].astype(str).str.zfill(2)
    df["FiscalQuarterLabel"] = df["FiscalYear"].astype(str) + "-Q" + df["FiscalQuarter"].astype(str)
    
    # Period sorting keys
    df["YearMonthSort"] = df["CalendarYear"] * 100 + df["CalendarMonth"]
    df["FiscalYearMonthSort"] = df["FiscalYear"] * 100 + df["FiscalMonth"]
    
    return df


def enrich_with_fx_rates(
    df: pd.DataFrame,
    fx_rates: Dict[str, Decimal],
    amount_column: str = "AmountLocal",
    currency_column: str = "Currency",
    target_currency: str = "EUR",
) -> pd.DataFrame:
    """
    Enrich dataframe with FX conversion to target currency.
    
    Args:
        df: Input dataframe
        fx_rates: Dict mapping currency code to rate (e.g., {"USD": 0.91, "GBP": 1.17})
        amount_column: Column with amount in local currency
        currency_column: Column with currency code
        target_currency: Target currency code
    
    Returns:
        Dataframe with added converted amount column
    """
    df = df.copy()
    
    if amount_column not in df.columns:
        logger.warning("Amount column not found", column=amount_column)
        return df
    
    def convert_row(row):
        currency = str(row.get(currency_column, "")).upper().strip()
        amount = row.get(amount_column)
        
        if currency == target_currency:
            return float(amount) if amount is not None else None
        
        rate = fx_rates.get(currency)
        if rate is None:
            logger.warning("No FX rate for currency", currency=currency)
            return None
        
        if amount is None:
            return None
        
        try:
            return float(amount) * float(rate)
        except (TypeError, ValueError):
            return None
    
    target_col = f"Amount{target_currency}"
    df[target_col] = df.apply(convert_row, axis=1)
    df["FXRateUsed"] = df[currency_column].map(lambda c: float(fx_rates.get(str(c).upper().strip(), 0)) if str(c).upper().strip() in fx_rates else None)
    
    logger.info("Applied FX conversion", target=target_currency, converted=df[target_col].notna().sum())
    
    return df


def add_calculated_fields(df: pd.DataFrame, source_type: str = "tender") -> pd.DataFrame:
    """
    Add domain-specific calculated fields based on source type.
    
    Args:
        df: Input dataframe
        source_type: "tender", "financial", "dynamics365"
    
    Returns:
        Dataframe with added calculated fields
    """
    df = df.copy()
    
    if source_type == "tender":
        # Tender-specific calculations
        df = calculate_tender_spreads(df)
        
        # Active flag
        active_statuses = ["Won", "Submitted", "In Progress", "On Hold"]
        if "TenderStatus" in df.columns:
            df["IsActive"] = df["TenderStatus"].isin(active_statuses)
        
        # Win/Loss flags
        if "TenderStatus" in df.columns:
            df["IsWon"] = df["TenderStatus"] == "Won"
            df["IsLost"] = df["TenderStatus"].isin(["Lost", "Declined", "Cancelled"])
        
        # Value tiers
        if "ReportingValue" in df.columns:
            def value_tier(val):
                if pd.isna(val):
                    return "Unknown"
                v = float(val)
                if v >= 5_000_000:
                    return "5M+"
                elif v >= 1_000_000:
                    return "1M-5M"
                elif v >= 500_000:
                    return "500K-1M"
                elif v >= 100_000:
                    return "100K-500K"
                else:
                    return "<100K"
            df["ValueTier"] = df["ReportingValue"].apply(value_tier)
    
    elif source_type == "financial":
        # Financial-specific calculations
        df = calculate_financial_periods(df, "Date", fiscal_year_start_month=1)
        
        # Scenario flags
        if "Scenario" in df.columns:
            df["IsActual"] = df["Scenario"] == "Actual"
            df["IsBudget"] = df["Scenario"] == "Budget"
            df["IsForecast"] = df["Scenario"] == "Forecast"
    
    elif source_type == "dynamics365":
        # Dynamics 365 specific
        df = calculate_financial_periods(df, "modifiedon", fiscal_year_start_month=1)
        
        # Entity-specific flags could be added here
    
    return df


def generate_power_query_m_code(
    source_path: str,
    sheet_name: str = "Sheet1",
    steps: List[Dict[str, Any]] = None,
) -> str:
    """
    Generate Power Query M code for the ETL pipeline.
    This can be copied directly into Power BI's Power Query Editor.
    """
    if steps is None:
        steps = [
            {"step": "Source", "code": f'Excel.Workbook(File.Contents("{source_path}"), null, true)'},
            {"step": "Sheet", "code": f'Source{{[Item="{sheet_name}",Kind="Sheet"]}}[Data]'},
            {"step": "Headers", "code": "Table.PromoteHeaders(Sheet, [PromoteAllScalars=true])"},
            {"step": "Types", "code": "Table.TransformColumnTypes(Headers, {{\"TenderID\", type text}, {\"ProjectName\", type text}, {\"ClientName\", type text}, {\"BusinessDivision\", type text}, {\"TenderStatus\", type text}, {\"TenderReceivedDate\", type date}, {\"TenderSubmissionDate\", type date}, {\"ProjectStartDate\", type date}, {\"ProjectEndDate\", type date}, {\"TenderValue\", type number}, {\"ReportingValue\", type number}, {\"ProbabilityPercentage\", type number}, {\"WeightedValue\", type number}, {\"ActionOwner\", type text}})"},
            {"step": "CleanStrings", "code": "Table.TransformColumns(Types, {{\"ClientName\", Text.Trim, type text}, {\"ProjectName\", Text.Trim, type text}, {\"BusinessDivision\", Text.Trim, type text}, {\"TenderStatus\", Text.Trim, type text}, {\"ActionOwner\", Text.Trim, type text}})"},
            {"step": "AddSpreads", "code": 'let AddMonths = (start as date, months as number) => Date.AddMonths(start, months), DurationMonths = (start as date, end as date) => Number.Round((Duration.Days(end - start) / 30.44), 0), MonthlySpread = (value as number, months as number) => if months > 0 then value / months else null in Table.AddColumn(CleanStrings, "MonthlySpread", each MonthlySpread([ReportingValue], DurationMonths([ProjectStartDate], [ProjectEndDate])), type nullable number)'},
        ]
    
    m_code = "let\n"
    for i, step in enumerate(steps):
        var_name = step["step"]
        code = step["code"]
        if i == len(steps) - 1:
            m_code += f"    {var_name} = {code}\n"
        else:
            m_code += f"    {var_name} = {code},\n"
    m_code += f"in\n    {steps[-1]['step']}"
    
    return m_code


def generate_dax_measures() -> Dict[str, str]:
    """
    Generate DAX measure definitions for Power BI model.
    Returns dictionary of measure name -> DAX expression.
    """
    return {
        # Base measures
        "Total Tender Value": "SUM(Tenders[ReportingValue])",
        "Total Weighted Value": "SUM(Tenders[WeightedValue])",
        "Tender Count": "COUNTROWS(Tenders)",
        "Avg Deal Size": "DIVIDE([Total Tender Value], [Tender Count])",
        "Win Rate": "DIVIDE(CALCULATE([Tender Count], Tenders[TenderStatus] = \"Won\"), CALCULATE([Tender Count], Tenders[TenderStatus] IN {\"Won\", \"Lost\", \"Declined\", \"Cancelled\"}))",
        
        # Monthly/Quarterly spreads (KEY for PP-010/PP-011)
        "Monthly Spread Value": "SUM(Tenders[MonthlySpread])",
        "Quarterly Spread Value": "SUM(Tenders[QuarterlySpread])",
        "Weighted Monthly Spread": "SUM(Tenders[WeightedMonthlySpread])",
        
        # Time intelligence (using Calculation Groups in practice)
        "YTD Tender Value": "CALCULATE([Total Tender Value], DATESYTD('Date'[Date]))",
        "PY Tender Value": "CALCULATE([Total Tender Value], SAMEPERIODLASTYEAR('Date'[Date]))",
        "YoY Variance": "[Total Tender Value] - [PY Tender Value]",
        "YoY %": "DIVIDE([YoY Variance], [PY Tender Value])",
        
        # Pipeline metrics
        "Active Pipeline Value": "CALCULATE([Total Weighted Value], Tenders[IsActive] = TRUE())",
        "Won Pipeline Value": "CALCULATE([Total Tender Value], Tenders[IsWon] = TRUE())",
        "Lost Pipeline Value": "CALCULATE([Total Tender Value], Tenders[IsLost] = TRUE())",
        
        # Division analysis
        "Division Win Rate": "DIVIDE(CALCULATE([Tender Count], Tenders[IsWon] = TRUE()), CALCULATE([Tender Count], Tenders[IsWon] = TRUE() || Tenders[IsLost] = TRUE()))",
        
        # Data quality
        "Missing Dates Count": "CALCULATE([Tender Count], Tenders[HasMissingDates] = TRUE())",
        "Data Quality %": "DIVIDE([Tender Count] - [Missing Dates Count], [Tender Count])",
    }