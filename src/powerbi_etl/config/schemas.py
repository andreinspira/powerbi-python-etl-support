"""
Pydantic schemas for data validation in Power BI ETL pipelines.
These schemas match the typical data structures used in Power BI + Dynamics 365 environments.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field, field_validator, ConfigDict
from enum import Enum


class DataSourceType(str, Enum):
    EXCEL = "excel"
    CSV = "csv"
    SHAREPOINT = "sharepoint"
    DYNAMICS365 = "dynamics365"
    ODATA = "odata"
    SQL = "sql"


class ValidationStatus(str, Enum):
    VALID = "valid"
    INVALID = "invalid"
    QUARANTINED = "quarantined"


class TenderRaw(BaseModel):
    """Raw tender data from Excel/SharePoint source (matches PP-011/PP-010 requirements)."""
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    tender_id: str = Field(..., alias="TenderID")
    project_name: str = Field(..., alias="ProjectName")
    client_name: str = Field(..., alias="ClientName")
    business_division: str = Field(..., alias="BusinessDivision")
    tender_status: str = Field(..., alias="TenderStatus")
    tender_received_date: Optional[date] = Field(default=None, alias="TenderReceivedDate")
    tender_submission_date: Optional[date] = Field(default=None, alias="TenderSubmissionDate")
    project_start_date: Optional[date] = Field(default=None, alias="ProjectStartDate")
    project_end_date: Optional[date] = Field(default=None, alias="ProjectEndDate")
    tender_value: Decimal = Field(default=Decimal("0"), alias="TenderValue")
    reporting_value: Decimal = Field(default=Decimal("0"), alias="ReportingValue")
    probability_percentage: Decimal = Field(default=Decimal("0"), alias="ProbabilityPercentage")
    weighted_value: Decimal = Field(default=Decimal("0"), alias="WeightedValue")
    action_owner: str = Field(default="", alias="ActionOwner")
    monthly_forecast: Optional[Decimal] = Field(default=None, alias="MonthlyForecast")
    quarterly_forecast: Optional[Decimal] = Field(default=None, alias="QuarterlyForecast")

    @field_validator("probability_percentage", mode="before")
    @classmethod
    def parse_probability(cls, v):
        if isinstance(v, str):
            v = v.replace("%", "").replace(",", ".").strip()
            try:
                dec = Decimal(v)
                return dec / 100 if dec > 1 else dec
            except Exception:
                return Decimal("0")
        return Decimal(str(v)) if v is not None else Decimal("0")

    @field_validator("tender_value", "reporting_value", "weighted_value", "monthly_forecast", "quarterly_forecast", mode="before")
    @classmethod
    def parse_currency(cls, v):
        if v is None:
            return Decimal("0")
        if isinstance(v, (int, float, Decimal)):
            return Decimal(str(v))
        cleaned = str(v).replace(",", "").replace(" ", "").replace("$", "").replace("€", "").replace("£", "").strip()
        try:
            return Decimal(cleaned)
        except Exception:
            return Decimal("0")


class TenderProcessed(BaseModel):
    """Processed tender data ready for Power BI loading."""
    model_config = ConfigDict(populate_by_name=True)

    tender_key: int
    tender_id: str
    project_name: str
    client_name: str
    business_division: str
    tender_status: str
    tender_received_date: Optional[date]
    tender_submission_date: Optional[date]
    project_start_date: Optional[date]
    project_end_date: Optional[date]
    tender_value: Decimal
    reporting_value: Decimal
    probability: Decimal
    weighted_value: Decimal
    action_owner: str
    monthly_forecast: Optional[Decimal]
    quarterly_forecast: Optional[Decimal]
    project_duration_days: Optional[int] = None
    project_duration_months: Optional[Decimal] = None
    monthly_spread: Optional[Decimal] = None
    quarterly_spread: Optional[Decimal] = None
    is_active: bool = True
    has_missing_dates: bool = False
    source_file: str
    load_timestamp: datetime


class FinancialTransactionRaw(BaseModel):
    """Raw financial transaction from ERP/Accounting system (QuickBooks, Dynamics 365)."""
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    transaction_id: str = Field(..., alias="TransactionID")
    transaction_date: date = Field(..., alias="Date")
    account_code: str = Field(..., alias="AccountCode")
    account_name: str = Field(..., alias="AccountName")
    department: str = Field(default="", alias="Department")
    cost_center: str = Field(default="", alias="CostCenter")
    entity: str = Field(default="", alias="Entity")
    scenario: str = Field(default="Actual", alias="Scenario")
    amount_local: Decimal = Field(default=Decimal("0"), alias="AmountLocal")
    currency: str = Field(default="USD", alias="Currency")
    description: str = Field(default="", alias="Description")


class FinancialTransactionProcessed(BaseModel):
    """Processed financial transaction for Power BI financial model."""
    model_config = ConfigDict(populate_by_name=True)

    transaction_key: int
    date_key: int
    account_key: int
    department_key: int
    cost_center_key: int
    entity_key: int
    scenario_key: int
    amount_local: Decimal
    amount_eur: Decimal
    fx_rate: Decimal


class PowerBIDataModel(BaseModel):
    """Power BI data model metadata for documentation/handover."""
    model_config = ConfigDict(populate_by_name=True)

    name: str
    description: str
    tables: List[Dict[str, Any]]
    relationships: List[Dict[str, Any]]
    measures: List[Dict[str, Any]]
    calculation_groups: List[Dict[str, Any]]
    rls_roles: List[Dict[str, Any]]
    parameters: List[Dict[str, Any]]
    last_refresh: Optional[datetime] = None
    source_system: str


class Dynamics365Entity(BaseModel):
    """Dynamics 365 entity definition for OData extraction."""
    model_config = ConfigDict(populate_by_name=True)

    logical_name: str
    display_name: str
    primary_key: str
    fields: List[Dict[str, Any]]
    relationships: List[Dict[str, Any]]
    odata_set_name: str


class ExcelSourceConfig(BaseModel):
    """Configuration for Excel/SharePoint data source."""
    model_config = ConfigDict(populate_by_name=True)

    file_path: str
    sheet_name: str = "Sheet1"
    header_row: int = 0
    data_range: Optional[str] = None
    dtype_overrides: Dict[str, str] = Field(default_factory=dict)
    parse_dates: List[str] = Field(default_factory=list)
    skip_rows: List[int] = Field(default_factory=list)


class PipelineConfig(BaseModel):
    """ETL Pipeline configuration."""
    model_config = ConfigDict(populate_by_name=True)

    name: str
    description: str
    source: Dict[str, Any]
    transforms: List[Dict[str, Any]]
    destination: Dict[str, Any]
    schedule: Optional[str] = None
    notifications: Optional[Dict[str, Any]] = None


class ValidationResult(BaseModel):
    """Result of data validation."""
    model_config = ConfigDict(populate_by_name=True)

    status: ValidationStatus
    total_records: int
    valid_records: int
    invalid_records: int
    errors: List[Dict[str, Any]] = Field(default_factory=list)
    warnings: List[Dict[str, Any]] = Field(default_factory=list)
    quarantined_records: int = 0


class PipelineRunResult(BaseModel):
    """Result of a pipeline execution."""
    model_config = ConfigDict(populate_by_name=True)

    pipeline_name: str
    status: Literal["success", "failed", "partial"]
    start_time: datetime
    end_time: datetime
    duration_seconds: float
    records_processed: int
    records_loaded: int
    errors: List[str] = Field(default_factory=list)
    metrics: Dict[str, Any] = Field(default_factory=dict)