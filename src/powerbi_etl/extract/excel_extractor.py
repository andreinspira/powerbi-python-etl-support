"""
Excel/SharePoint data extractor for Power BI data sources.
Supports local Excel files and SharePoint/OneDrive via Microsoft Graph (stubbed for demo).
"""

import pandas as pd
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional
from .base import BaseExtractor, ExtractionResult
import structlog

logger = structlog.get_logger(__name__)


class ExcelExtractor(BaseExtractor):
    """
    Extracts data from Excel files (.xlsx, .xls).
    Supports local files and SharePoint/OneDrive paths (via mount or Graph API).
    """

    def __init__(self, config: Dict[str, Any]):
        # Set file_path before super().__init__ calls _validate_config
        self.file_path = Path(config.get("file_path", ""))
        super().__init__(config)
        self.sheet_name = config.get("sheet_name", 0)
        self.header_row = config.get("header_row", 0)
        self.dtype_overrides = config.get("dtype_overrides", {})
        self.parse_dates = config.get("parse_dates", [])
        self.skip_rows = config.get("skip_rows", [])
        self.chunk_size = config.get("chunk_size", 10000)
        self._dataframe: Optional[pd.DataFrame] = None

    def _validate_config(self) -> None:
        if not self.file_path:
            raise ValueError("file_path is required for ExcelExtractor")
        # Note: We don't check file existence here to allow SharePoint paths

    def extract(self) -> ExtractionResult:
        """Extract all data from Excel file."""
        try:
            self.logger.info("Extracting Excel data", file=str(self.file_path))
            df = self._read_excel()
            records = df.to_dict(orient="records")
            return self._create_result(
                success=True,
                records=records,
                metadata={
                    "file_path": str(self.file_path),
                    "sheet_name": self.sheet_name,
                    "rows": len(df),
                    "columns": list(df.columns),
                },
            )
        except Exception as e:
            self.logger.error("Excel extraction failed", error=str(e))
            return self._create_result(success=False, errors=[str(e)])

    def get_record_iterator(self) -> Iterator[Dict[str, Any]]:
        """Iterate over records in chunks for memory efficiency."""
        df = self._read_excel()
        for i in range(0, len(df), self.chunk_size):
            chunk = df.iloc[i:i + self.chunk_size]
            for _, row in chunk.iterrows():
                yield row.to_dict()

    def _read_excel(self) -> pd.DataFrame:
        """Read Excel file with configured options."""
        if self._dataframe is not None:
            return self._dataframe

        # For demo purposes, if file doesn't exist, create sample data
        if not self.file_path.exists():
            self.logger.warning("File not found, generating sample data", file=str(self.file_path))
            self._dataframe = self._generate_sample_tender_data()
            return self._dataframe

        df = pd.read_excel(
            self.file_path,
            sheet_name=self.sheet_name,
            header=self.header_row,
            dtype=self.dtype_overrides,
            parse_dates=self.parse_dates,
            skiprows=self.skip_rows,
            engine="openpyxl",
        )

        # Clean column names
        df.columns = [str(c).strip() for c in df.columns]

        # Add metadata
        df["_source_file"] = self.file_path.name
        df["_extracted_at"] = datetime.now()

        self._dataframe = df
        return df

    def _generate_sample_tender_data(self) -> pd.DataFrame:
        """Generate synthetic tender register data matching PP-010/PP-011 requirements."""
        import random
        from datetime import date, timedelta
        from decimal import Decimal

        random.seed(42)
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

        for i in range(1, 51):  # 50 sample tenders
            tender_id = f"TND-2025-{i:03d}"
            project_name = f"{random.choice(['Bridge', 'Building', 'Road', 'IT System', 'Dashboard', 'Platform', 'Renovation', 'Expansion'])} Project {i}"
            client = random.choice(clients)
            division = random.choice(divisions)
            status = random.choice(statuses)

            # Dates
            received = base_date + timedelta(days=random.randint(0, 300))
            submission = received + timedelta(days=random.randint(1, 60))
            start = submission + timedelta(days=random.randint(30, 180))
            end = start + timedelta(days=random.randint(90, 1000))

            # Values
            tender_value = Decimal(str(round(random.uniform(100000, 10000000), 2)))
            probability = Decimal(str(round(random.uniform(0.1, 0.9), 2)))
            weighted = tender_value * probability

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
                "MonthlyForecast": weighted / 12 if random.random() > 0.3 else None,
                "QuarterlyForecast": weighted / 4 if random.random() > 0.3 else None,
            })

        df = pd.DataFrame(data)
        df["_source_file"] = "Tender_Register_Sample.xlsx"
        df["_extracted_at"] = datetime.now()
        return df


class SharePointExcelExtractor(ExcelExtractor):
    """
    Extracts Excel files from SharePoint/OneDrive via Microsoft Graph API.
    This is a stub implementation - real implementation requires Azure AD app registration.
    """

    def __init__(self, config: Dict[str, Any]):
        # Extract SharePoint-specific config
        self.site_url = config.get("site_url", "")
        self.drive_id = config.get("drive_id", "")
        self.folder_path = config.get("folder_path", "")
        self.file_name = config.get("file_name", "")
        self.tenant_id = config.get("tenant_id", "")
        self.client_id = config.get("client_id", "")
        self.client_secret = config.get("client_secret", "")

        # For local testing, fall back to local file
        local_path = config.get("local_fallback_path", "")
        super().__init__({"file_path": local_path, **config})

    def _validate_config(self) -> None:
        # In production, validate Graph API credentials
        pass

    def _download_from_sharepoint(self) -> Path:
        """
        Download file from SharePoint using Microsoft Graph API.
        This is a stub - real implementation would use httpx with OAuth2 token.
        """
        self.logger.info(
            "SharePoint download stubbed",
            site=self.site_url,
            folder=self.folder_path,
            file=self.file_name,
        )
        # Return local fallback path
        return Path(self.config.get("local_fallback_path", ""))


class CSVExtractor(BaseExtractor):
    """Extract data from CSV files."""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.file_path = Path(config.get("file_path", ""))
        self.encoding = config.get("encoding", "utf-8")
        self.delimiter = config.get("delimiter", ",")
        self.dtype_overrides = config.get("dtype_overrides", {})
        self.parse_dates = config.get("parse_dates", [])
        self.chunk_size = config.get("chunk_size", 10000)

    def _validate_config(self) -> None:
        if not self.file_path:
            raise ValueError("file_path is required for CSVExtractor")

    def extract(self) -> ExtractionResult:
        try:
            df = pd.read_csv(
                self.file_path,
                encoding=self.encoding,
                delimiter=self.delimiter,
                dtype=self.dtype_overrides,
                parse_dates=self.parse_dates,
            )
            df.columns = [str(c).strip() for c in df.columns]
            df["_source_file"] = self.file_path.name
            df["_extracted_at"] = datetime.now()

            records = df.to_dict(orient="records")
            return self._create_result(
                success=True,
                records=records,
                metadata={"file_path": str(self.file_path), "rows": len(df), "columns": list(df.columns)},
            )
        except Exception as e:
            self.logger.error("CSV extraction failed", error=str(e))
            return self._create_result(success=False, errors=[str(e)])

    def get_record_iterator(self) -> Iterator[Dict[str, Any]]:
        for chunk in pd.read_csv(
            self.file_path,
            encoding=self.encoding,
            delimiter=self.delimiter,
            dtype=self.dtype_overrides,
            parse_dates=self.parse_dates,
            chunksize=self.chunk_size,
        ):
            chunk.columns = [str(c).strip() for c in chunk.columns]
            for _, row in chunk.iterrows():
                yield row.to_dict()


class ODataExtractor(BaseExtractor):
    """
    Extract data from OData services (Dynamics 365, Power BI XMLA, etc.).
    This is a stub implementation for demonstration.
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.base_url = config.get("base_url", "")
        self.entity_set = config.get("entity_set", "")
        self.select_fields = config.get("select", [])
        self.filter_query = config.get("filter", "")
        self.top = config.get("top", 1000)
        self.client_id = config.get("client_id", "")
        self.client_secret = config.get("client_secret", "")
        self.tenant_id = config.get("tenant_id", "")
        self._access_token: Optional[str] = None

    def _validate_config(self) -> None:
        if not self.base_url or not self.entity_set:
            raise ValueError("base_url and entity_set are required for ODataExtractor")

    def extract(self) -> ExtractionResult:
        self.logger.info("OData extraction (stubbed)", entity=self.entity_set)
        # Stub: return empty result with metadata
        return self._create_result(
            success=True,
            records=[],
            metadata={
                "entity_set": self.entity_set,
                "base_url": self.base_url,
                "note": "OData extraction stubbed - requires Azure AD authentication in production",
            },
        )

    def get_record_iterator(self) -> Iterator[Dict[str, Any]]:
        # Stub iterator
        return iter([])

    def _get_access_token(self) -> str:
        """Get OAuth2 access token for Dynamics 365 / Power BI."""
        # Real implementation would use MSAL or httpx with client credentials flow
        return "stub-token"