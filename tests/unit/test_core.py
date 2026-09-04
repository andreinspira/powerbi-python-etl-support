"""
Unit tests for Power BI ETL components.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
import tempfile

# Test imports
from powerbi_etl.config.schemas import (
    TenderRaw, TenderProcessed, FinancialTransactionRaw, ValidationStatus
)
from powerbi_etl.transform.cleaning import (
    clean_string, clean_numeric, clean_date, standardize_tender_status,
    remove_duplicates, handle_missing_values, enforce_schema, clean_tender_dataframe
)
from powerbi_etl.transform.validation import validate_dataframe, ValidationResult
from powerbi_etl.transform.enrichment import (
    calculate_tender_spreads, calculate_financial_periods, enrich_with_fx_rates, add_calculated_fields
)
from powerbi_etl.utils.helpers import (
    generate_sample_tender_data, create_sample_financial_data, hash_dataframe, compare_dataframes
)


class TestSchemas:
    """Test Pydantic schemas."""
    
    def test_tender_raw_valid(self):
        """Test valid tender raw data."""
        data = {
            "TenderID": "TND-001",
            "ProjectName": "Test Project",
            "ClientName": "Test Client",
            "BusinessDivision": "Commercial",
            "TenderStatus": "Won",
            "TenderReceivedDate": date(2025, 1, 15),
            "TenderSubmissionDate": date(2025, 2, 1),
            "ProjectStartDate": date(2025, 3, 1),
            "ProjectEndDate": date(2026, 3, 1),
            "TenderValue": "1000000",
            "ReportingValue": "950000",
            "ProbabilityPercentage": "0.8",
            "WeightedValue": "800000",
            "ActionOwner": "J. Silva",
        }
        tender = TenderRaw(**data)
        assert tender.tender_id == "TND-001"
        assert tender.probability_percentage == Decimal("0.8")
    
    def test_tender_raw_probability_parsing(self):
        """Test probability percentage parsing from various formats."""
        test_cases = [
            ("80%", Decimal("0.8")),
            ("0.8", Decimal("0.8")),
            ("50", Decimal("0.5")),
            ("0.25", Decimal("0.25")),
        ]
        for input_val, expected in test_cases:
            data = {
                "TenderID": "TND-001",
                "ProjectName": "Test",
                "ClientName": "Client",
                "BusinessDivision": "Div",
                "TenderStatus": "Won",
                "ProbabilityPercentage": input_val,
            }
            tender = TenderRaw(**data)
            assert tender.probability_percentage == expected, f"Failed for {input_val}"
    
    def test_tender_raw_currency_parsing(self):
        """Test currency value parsing."""
        test_cases = [
            ("1,000,000", Decimal("1000000")),
            ("$1,000,000", Decimal("1000000")),
            ("€ 950,000.50", Decimal("950000.50")),
            (1000000, Decimal("1000000")),
            (Decimal("500000"), Decimal("500000")),
        ]
        for input_val, expected in test_cases:
            data = {
                "TenderID": "TND-001",
                "ProjectName": "Test",
                "ClientName": "Client",
                "BusinessDivision": "Div",
                "TenderStatus": "Won",
                "TenderValue": input_val,
            }
            tender = TenderRaw(**data)
            assert tender.tender_value == expected, f"Failed for {input_val}"


class TestCleaning:
    """Test data cleaning utilities."""
    
    def test_clean_string(self):
        assert clean_string("  hello  ") == "hello"
        assert clean_string(None) == ""
        assert clean_string(pd.NA) == ""
        assert clean_string(123) == "123"
    
    def test_clean_numeric(self):
        from decimal import Decimal
        assert clean_numeric("1,000,000") == Decimal("1000000")
        assert clean_numeric("$1,000.50") == Decimal("1000.50")
        assert clean_numeric("€ 500") == Decimal("500")
        assert clean_numeric(None) is None
        assert clean_numeric(pd.NA) is None
    
    def test_clean_date(self):
        assert clean_date("2025-01-15") == pd.Timestamp("2025-01-15")
        assert clean_date("15/01/2025") == pd.Timestamp("2025-01-15")
        assert clean_date("01/15/2025") == pd.Timestamp("2025-01-15")
        assert clean_date(None) is None
    
    def test_standardize_tender_status(self):
        assert standardize_tender_status("won") == "Won"
        assert standardize_tender_status("CLOSED WON") == "Won"
        assert standardize_tender_status("proposal") == "Proposal"
        assert standardize_tender_status("negotiating") == "Negotiation"
        assert standardize_tender_status("unknown") == "Unknown"
    
    def test_remove_duplicates(self):
        df = pd.DataFrame({"id": [1, 2, 2, 3], "value": ["a", "b", "b", "c"]})
        result = remove_duplicates(df, subset=["id", "value"])
        assert len(result) == 3
    
    def test_handle_missing_values(self):
        df = pd.DataFrame({"a": [1, None, 3], "b": [None, "x", "y"]})
        result = handle_missing_values(df, {"a": 0, "b": "missing"})
        assert result["a"].iloc[1] == 0
        assert result["b"].iloc[0] == "missing"
    
    def test_enforce_schema(self):
        df = pd.DataFrame({"a": ["1", "2", "3"], "b": ["1.5", "2.5", "3.5"], "c": ["x", "y", "z"]})
        result = enforce_schema(df, {"a": "int", "b": "float", "c": "string"})
        # enforce_schema uses nullable Int64 for integers
        assert str(result["a"].dtype) == "Int64"
        assert result["b"].dtype == "float64"
    
    def test_clean_tender_dataframe(self):
        """Test full tender dataframe cleaning."""
        raw_data = {
            "TenderID": [" TND-001 ", "TND-002"],
            "ProjectName": [" Project A ", "Project B"],
            "ClientName": ["Client X", "Client Y"],
            "BusinessDivision": ["Commercial", "Infrastructure"],
            "TenderStatus": ["won", "submitted"],
            "TenderReceivedDate": ["2025-01-15", "2025-02-01"],
            "ProjectStartDate": ["2025-03-01", "2025-04-01"],
            "ProjectEndDate": ["2026-03-01", "2026-04-01"],
            "TenderValue": ["1,000,000", "2,000,000"],
            "ProbabilityPercentage": ["80%", "50%"],
        }
        df = pd.DataFrame(raw_data)
        cleaned = clean_tender_dataframe(df)
        
        assert cleaned["TenderID"].iloc[0] == "TND-001"
        assert cleaned["TenderStatus"].iloc[0] == "Won"
        assert cleaned["TenderStatus"].iloc[1] == "Submitted"
        assert cleaned["TenderValue"].iloc[0] == Decimal("1000000")


class TestValidation:
    """Test data validation with Pydantic."""
    
    def test_validate_dataframe_valid(self):
        df = pd.DataFrame([{
            "TenderID": "TND-001",
            "ProjectName": "Test",
            "ClientName": "Client",
            "BusinessDivision": "Div",
            "TenderStatus": "Won",
            "TenderReceivedDate": date(2025, 1, 15),
            "ProjectStartDate": date(2025, 3, 1),
            "ProjectEndDate": date(2026, 3, 1),
            "TenderValue": Decimal("1000000"),
            "ProbabilityPercentage": Decimal("0.8"),
        }])
        result = validate_dataframe(df, TenderRaw, id_column="TenderID")
        assert result.success_rate == 1.0
        assert len(result.valid) == 1
    
    def test_validate_dataframe_invalid(self):
        df = pd.DataFrame([{
            "TenderID": "TND-001",
            "ProjectName": "Test",
            # Missing required fields
        }])
        result = validate_dataframe(df, TenderRaw, id_column="TenderID")
        # With quarantine threshold at 0.5, single invalid record gets quarantined
        assert result.success_rate == 1.0  # Quarantined records don't count as invalid
        assert len(result.quarantined) == 1
        assert len(result.invalid) == 0


class TestEnrichment:
    """Test data enrichment and calculated fields."""
    
    def test_calculate_tender_spreads(self):
        df = pd.DataFrame([{
            "TenderID": "TND-001",
            "ProjectStartDate": date(2025, 3, 1),
            "ProjectEndDate": date(2026, 3, 1),  # 12 months
            "ReportingValue": Decimal("1200000"),
            "WeightedValue": Decimal("960000"),
        }])
        result = calculate_tender_spreads(df)
        
        assert result["ProjectDurationMonths"].iloc[0] == 12
        assert result["MonthlySpread"].iloc[0] == 100000.0  # 1.2M / 12
        assert result["QuarterlySpread"].iloc[0] == 300000.0  # Monthly * 3
        assert result["WeightedMonthlySpread"].iloc[0] == 80000.0  # 960K / 12
    
    def test_calculate_tender_spreads_missing_dates(self):
        df = pd.DataFrame([{
            "TenderID": "TND-001",
            "ProjectStartDate": None,
            "ProjectEndDate": date(2026, 3, 1),
            "ReportingValue": Decimal("1200000"),
        }])
        result = calculate_tender_spreads(df)
        
        assert result["HasMissingDates"].iloc[0] == True
        assert "ProjectStartDate" in result["MissingDateFields"].iloc[0]
    
    def test_calculate_financial_periods(self):
        df = pd.DataFrame({"Date": [date(2025, 1, 15), date(2025, 4, 15), date(2025, 7, 15)]})
        result = calculate_financial_periods(df, "Date", fiscal_year_start_month=1)
        
        assert "CalendarYear" in result.columns
        assert "FiscalYear" in result.columns
        assert "FiscalQuarter" in result.columns
        assert result["CalendarYear"].iloc[0] == 2025
        assert result["CalendarQuarter"].iloc[0] == 1
    
    def test_calculate_financial_periods_fiscal_april(self):
        df = pd.DataFrame({"Date": [date(2025, 1, 15), date(2025, 4, 15), date(2025, 7, 15)]})
        result = calculate_financial_periods(df, "Date", fiscal_year_start_month=4)
        
        # Jan 15, 2025 -> Fiscal Year 2025 (since fiscal starts Apr 2024)
        assert result["FiscalYear"].iloc[0] == 2025
        # Apr 15, 2025 -> Fiscal Year 2026
        assert result["FiscalYear"].iloc[1] == 2026
    
    def test_enrich_with_fx_rates(self):
        df = pd.DataFrame({
            "AmountLocal": [1000, 2000, 3000],
            "Currency": ["USD", "EUR", "GBP"],
        })
        fx_rates = {"USD": Decimal("0.91"), "EUR": Decimal("1.0"), "GBP": Decimal("1.17")}
        result = enrich_with_fx_rates(df, fx_rates, "AmountLocal", "Currency", "EUR")
        
        assert result["AmountEUR"].iloc[0] == 910.0  # 1000 * 0.91
        assert result["AmountEUR"].iloc[1] == 2000.0  # 2000 * 1.0
        assert result["AmountEUR"].iloc[2] == 3510.0  # 3000 * 1.17
    
    def test_add_calculated_fields_tender(self):
        df = pd.DataFrame([{
            "TenderID": "TND-001",
            "TenderStatus": "Won",
            "ReportingValue": Decimal("5000000"),
            "ProjectStartDate": date(2025, 3, 1),
            "ProjectEndDate": date(2026, 3, 1),
        }])
        result = add_calculated_fields(df, "tender")
        
        assert result["IsActive"].iloc[0] == True
        assert result["IsWon"].iloc[0] == True
        assert result["IsLost"].iloc[0] == False
        assert result["ValueTier"].iloc[0] == "5M+"


class TestHelpers:
    """Test helper utilities."""
    
    def test_generate_sample_tender_data(self):
        df = generate_sample_tender_data(10)
        assert len(df) == 10
        assert "TenderID" in df.columns
        assert "MonthlySpread" not in df.columns  # Not calculated yet
    
    def test_create_sample_financial_data(self):
        df = create_sample_financial_data(50)
        assert len(df) == 50
        assert "TransactionID" in df.columns
        assert "AmountLocal" in df.columns
    
    def test_hash_dataframe(self):
        df1 = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
        df2 = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
        df3 = pd.DataFrame({"a": [1, 2], "b": [3, 5]})
        
        assert hash_dataframe(df1) == hash_dataframe(df2)
        assert hash_dataframe(df1) != hash_dataframe(df3)
    
    def test_compare_dataframes(self):
        df1 = pd.DataFrame({"id": [1, 2], "value": [10, 20]})
        df2 = pd.DataFrame({"id": [1, 2], "value": [10, 20]})
        df3 = pd.DataFrame({"id": [1, 2], "value": [10, 30]})
        
        result = compare_dataframes(df1, df2, key_columns=["id"])
        assert result["shape_match"] is True
        assert result["rows_in_both"] == 2
        assert len(result["value_differences"]) == 0
        
        result = compare_dataframes(df1, df3, key_columns=["id"])
        assert len(result["value_differences"]) == 1
        assert result["value_differences"][0]["column"] == "value"
        assert result["value_differences"][0]["differences"] == 1


class TestExtractors:
    """Test data extractors with sample data."""
    
    def test_excel_extractor_sample_data(self):
        from powerbi_etl.extract.excel_extractor import ExcelExtractor
        
        config = {"file_path": "nonexistent.xlsx"}
        extractor = ExcelExtractor(config)
        
        # Should generate sample data when file doesn't exist
        result = extractor.extract()
        assert result.success is True
        assert result.record_count > 0
        assert "TenderID" in result.records[0]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])