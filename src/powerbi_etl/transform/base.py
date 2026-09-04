"""
Base transformer class for data transformations.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
import pandas as pd
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class TransformationResult:
    """Result of a transformation operation."""
    success: bool
    dataframe: Optional[pd.DataFrame] = None
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)
    transformed_at: datetime = field(default_factory=datetime.now)


class BaseTransformer(ABC):
    """Abstract base class for all transformers."""

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.logger = logger.bind(transformer=self.__class__.__name__)

    @abstractmethod
    def transform(self, dataframe: pd.DataFrame) -> TransformationResult:
        """Transform the input dataframe."""
        pass

    def _create_result(
        self,
        success: bool,
        dataframe: Optional[pd.DataFrame] = None,
        errors: List[str] = None,
        warnings: List[str] = None,
        metrics: Dict[str, Any] = None,
    ) -> TransformationResult:
        """Helper to create transformation result."""
        return TransformationResult(
            success=success,
            dataframe=dataframe,
            errors=errors or [],
            warnings=warnings or [],
            metrics=metrics or {},
        )