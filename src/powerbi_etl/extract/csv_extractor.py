"""
CSV data extractor for Power BI data sources.
"""

import pandas as pd
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Union
import structlog

from .base import BaseExtractor, ExtractionResult

logger = structlog.get_logger(__name__)


class CSVExtractor(BaseExtractor):
    """Extract data from CSV files."""
    
    def __init__(
        self,
        file_path: Union[str, Path],
        encoding: str = "utf-8",
        delimiter: str = ",",
        **kwargs
    ):
        super().__init__(**kwargs)
        self.file_path = Path(file_path)
        self.encoding = encoding
        self.delimiter = delimiter
        self.kwargs = kwargs
    
    def validate_source(self) -> bool:
        """Validate that CSV file exists and is readable."""
        try:
            if not self.file_path.exists():
                logger.error("CSV file not found", path=str(self.file_path))
                return False
            
            # Try reading first few rows
            pd.read_csv(self.file_path, encoding=self.encoding, delimiter=self.delimiter, nrows=5)
            return True
        except Exception as e:
            logger.error("CSV validation failed", path=str(self.file_path), error=str(e))
            return False
    
    def extract(self) -> ExtractionResult:
        """Extract data from CSV file."""
        try:
            if not self.validate_source():
                return ExtractionResult(
                    success=False,
                    data=None,
                    rows_extracted=0,
                    metadata={"source": str(self.file_path)},
                    errors=["Source validation failed"]
                )
            
            df = pd.read_csv(self.file_path, encoding=self.encoding, delimiter=self.delimiter, **self.kwargs)
            
            return ExtractionResult(
                success=True,
                data=df,
                rows_extracted=len(df),
                metadata={
                    "source": str(self.file_path),
                    "encoding": self.encoding,
                    "delimiter": self.delimiter,
                    "columns": list(df.columns),
                    "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
                },
                errors=[]
            )
        except Exception as e:
            logger.error("CSV extraction failed", path=str(self.file_path), error=str(e))
            return ExtractionResult(
                success=False,
                data=None,
                rows_extracted=0,
                metadata={"source": str(self.file_path)},
                errors=[str(e)]
            )
    
    def get_metadata(self) -> Dict[str, Any]:
        """Get metadata about the CSV source."""
        return {
            "source_type": "csv",
            "file_path": str(self.file_path),
            "encoding": self.encoding,
            "delimiter": self.delimiter,
        }


# For compatibility
def extract_csv(
    file_path: Union[str, Path],
    encoding: str = "utf-8",
    delimiter: str = ",",
    **kwargs
) -> pd.DataFrame:
    """Simple function to extract CSV data."""
    extractor = CSVExtractor(file_path, encoding, delimiter, **kwargs)
    result = extractor.extract()
    if result.success:
        return result.data
    else:
        raise ValueError(f"CSV extraction failed: {result.errors}")