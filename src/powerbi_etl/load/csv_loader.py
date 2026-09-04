"""
CSV loader for Power BI data sources.
Outputs formatted CSV files ready for Power BI consumption.
"""

import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional, Any
from .base import BaseLoader, LoadResult
import structlog

logger = structlog.get_logger(__name__)


class CSVLoader(BaseLoader):
    """Load data to CSV files optimized for Power BI consumption."""
    
    def __init__(
        self,
        output_path: Union[str, Path],
        encoding: str = "utf-8",
        delimiter: str = ",",
        include_index: bool = False,
        **kwargs
    ):
        self.output_path = Path(output_path)
        self.encoding = encoding
        self.delimiter = delimiter
        self.include_index = include_index
        self.kwargs = kwargs
        self.logger = logger.bind(loader="CSVLoader")
    
    def load(self, data: pd.DataFrame) -> LoadResult:
        """Load DataFrame to CSV file."""
        try:
            self.logger.info("Loading data to CSV", path=str(self.output_path), rows=len(data))
            
            # Ensure output directory exists
            self.output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write CSV
            data.to_csv(
                self.output_path,
                encoding=self.encoding,
                sep=self.delimiter,
                index=self.include_index,
                **self.kwargs
            )
            
            return LoadResult(
                success=True,
                records_loaded=len(data),
                metadata={
                    "output_path": str(self.output_path),
                    "encoding": self.encoding,
                    "delimiter": self.delimiter,
                    "file_size_bytes": self.output_path.stat().st_size,
                },
                warnings=[]
            )
        except Exception as e:
            self.logger.error("CSV load failed", path=str(self.output_path), error=str(e))
            return LoadResult(
                success=False,
                records_loaded=0,
                metadata={"output_path": str(self.output_path)},
                warnings=[str(e)]
            )
    
    def load_incremental(self, data: pd.DataFrame, key_columns: List[str]) -> LoadResult:
        """Load data incrementally (append if file exists)."""
        try:
            if self.output_path.exists():
                # Read existing data
                existing = pd.read_csv(self.output_path, encoding=self.encoding, sep=self.delimiter)
                # Merge on key columns, keeping new data
                merged = existing.merge(data, on=key_columns, how="outer", indicator=True, suffixes=("_old", "_new"))
                # This is a simplified approach - in production you'd want proper upsert logic
                combined = pd.concat([existing, data]).drop_duplicates(subset=key_columns, keep="last")
                return self.load(combined)
            else:
                return self.load(data)
        except Exception as e:
            self.logger.error("Incremental CSV load failed", error=str(e))
            return LoadResult(success=False, records_loaded=0, metadata={}, warnings=[str(e)])
    
    def get_metadata(self) -> Dict[str, Any]:
        """Get loader metadata."""
        return {
            "loader_type": "csv",
            "output_path": str(self.output_path),
            "encoding": self.encoding,
            "delimiter": self.delimiter,
        }


def load_csv(
    data: pd.DataFrame,
    output_path: Union[str, Path],
    encoding: str = "utf-8",
    delimiter: str = ",",
    **kwargs
) -> bool:
    """Simple function to load DataFrame to CSV."""
    loader = CSVLoader(output_path, encoding, delimiter, **kwargs)
    result = loader.load(data)
    return result.success