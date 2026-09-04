"""
Base loader class for data destinations.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class LoadResult:
    """Result of a load operation."""
    success: bool
    records_loaded: int = 0
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    loaded_at: datetime = field(default_factory=datetime.now)
    destination: str = ""


class BaseLoader(ABC):
    """Abstract base class for all loaders."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = logger.bind(loader=self.__class__.__name__)

    @abstractmethod
    def load(self, dataframe: "pd.DataFrame") -> LoadResult:
        """Load dataframe to destination."""
        pass

    @abstractmethod
    def test_connection(self) -> bool:
        """Test connection to destination."""
        pass

    def _create_result(
        self,
        success: bool,
        records_loaded: int = 0,
        errors: List[str] = None,
        warnings: List[str] = None,
        metadata: Dict[str, Any] = None,
    ) -> LoadResult:
        """Helper to create load result."""
        return LoadResult(
            success=success,
            records_loaded=records_loaded,
            errors=errors or [],
            warnings=warnings or [],
            metadata=metadata or {},
            destination=self.__class__.__name__,
        )