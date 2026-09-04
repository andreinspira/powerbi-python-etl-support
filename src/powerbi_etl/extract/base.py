"""
Base extractor class for all data sources.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Iterator, List, Optional
from pathlib import Path
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class ExtractionResult:
    """Result of an extraction operation."""
    success: bool
    records: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    extracted_at: datetime = field(default_factory=datetime.now)
    source: str = ""
    record_count: int = 0


class BaseExtractor(ABC):
    """Abstract base class for all extractors."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = logger.bind(extractor=self.__class__.__name__)
        self._validate_config()

    @abstractmethod
    def _validate_config(self) -> None:
        """Validate extractor configuration."""
        pass

    @abstractmethod
    def extract(self) -> ExtractionResult:
        """Extract data from source and return result."""
        pass

    @abstractmethod
    def get_record_iterator(self) -> Iterator[Dict[str, Any]]:
        """Get an iterator over records for memory-efficient processing."""
        pass

    def _create_result(
        self,
        success: bool,
        records: List[Dict[str, Any]] = None,
        errors: List[str] = None,
        warnings: List[str] = None,
        metadata: Dict[str, Any] = None,
    ) -> ExtractionResult:
        """Helper to create extraction result."""
        records = records or []
        return ExtractionResult(
            success=success,
            records=records,
            errors=errors or [],
            warnings=warnings or [],
            metadata=metadata or {},
            source=self.__class__.__name__,
            record_count=len(records),
        )