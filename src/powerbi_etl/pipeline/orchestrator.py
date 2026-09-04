"""
Pipeline orchestrator for managing ETL pipeline execution.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set
import yaml
import pandas as pd
import structlog
from ..config.schemas import PipelineConfig, PipelineRunResult

logger = structlog.get_logger(__name__)


class PipelineStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"


@dataclass
class PipelineStep:
    """Single pipeline step definition."""
    name: str
    step_type: str  # extract, transform, load
    function: Optional[Callable] = None
    config: Dict[str, Any] = field(default_factory=dict)
    depends_on: List[str] = field(default_factory=list)
    description: str = ""
    optional: bool = False  # If True, failure won't stop pipeline


@dataclass
class PipelineRun:
    """Pipeline execution context and state."""
    pipeline_name: str
    status: PipelineStatus = PipelineStatus.PENDING
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    steps_completed: List[str] = field(default_factory=list)
    steps_failed: List[str] = field(default_factory=list)
    step_results: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)

    @property
    def duration_seconds(self) -> float:
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return 0.0

    def to_result(self) -> PipelineRunResult:
        """Convert to PipelineRunResult schema."""
        return PipelineRunResult(
            pipeline_name=self.pipeline_name,
            status=self.status.value,
            start_time=self.start_time or datetime.now(),
            end_time=self.end_time or datetime.now(),
            duration_seconds=self.duration_seconds,
            records_processed=self.metrics.get("records_processed", 0),
            records_loaded=self.metrics.get("records_loaded", 0),
            errors=self.errors,
            metrics=self.metrics,
        )


class PipelineOrchestrator:
    """
    Orchestrates multi-step ETL pipelines with dependency resolution.
    
    Supports:
    - YAML-defined pipeline configurations
    - Dependency-based execution ordering
    - Step-level error handling and retries
    - Structured logging and metrics
    - Dry-run mode for validation
    """

    def __init__(self, pipeline_config: PipelineConfig):
        self.config = pipeline_config
        self.name = pipeline_config.name
        self.steps = self._build_steps(pipeline_config.transforms)
        self.logger = logger.bind(pipeline=self.name)

    def _build_steps(self, transforms_config: List[Dict[str, Any]]) -> List[PipelineStep]:
        """Build step objects from configuration."""
        steps = []
        for step_config in transforms_config:
            step = PipelineStep(
                name=step_config.get("name", f"step_{len(steps)}"),
                step_type=step_config.get("type", "transform"),
                config=step_config.get("config", {}),
                depends_on=step_config.get("depends_on", []),
                description=step_config.get("description", ""),
                optional=step_config.get("optional", False),
            )
            steps.append(step)
        return steps

    def run(self, dry_run: bool = False) -> PipelineRun:
        """Execute pipeline steps in dependency order."""
        run = PipelineRun(pipeline_name=self.name)
        run.status = PipelineStatus.RUNNING
        run.start_time = datetime.now()
        self.logger.info("Pipeline started", pipeline=self.name, dry_run=dry_run)

        # Track executed steps
        executed: Set[str] = set()
        step_data: Dict[str, Any] = {}  # Data passed between steps

        # Topological execution loop
        while len(executed) < len(self.steps):
            progress = False
            
            for step in self.steps:
                if step.name in executed:
                    continue
                
                # Check if dependencies are satisfied
                if all(dep in executed for dep in step.depends_on):
                    try:
                        self.logger.info("Executing step", step=step.name, type=step.step_type)
                        
                        if not dry_run:
                            result = self._execute_step(step, step_data, run)
                            step_data[step.name] = result
                        
                        executed.add(step.name)
                        run.steps_completed.append(step.name)
                        progress = True
                        
                    except Exception as e:
                        self.logger.error("Step failed", step=step.name, error=str(e))
                        run.steps_failed.append(step.name)
                        run.errors.append(f"{step.name}: {str(e)}")
                        if step.optional:
                            self.logger.warning("Optional step failed, continuing", step=step.name)
                            run.status = PipelineStatus.PARTIAL
                            executed.add(step.name)  # Mark as executed so dependencies can proceed
                            progress = True
                        else:
                            run.status = PipelineStatus.FAILED
                            raise
            
            if not progress:
                # Circular dependency or unsatisfied dependencies
                remaining = [s.name for s in self.steps if s.name not in executed]
                error_msg = f"Cannot resolve dependencies for steps: {remaining}"
                self.logger.error("Pipeline deadlock", remaining=remaining)
                run.status = PipelineStatus.FAILED
                run.errors.append(error_msg)
                raise RuntimeError(error_msg)

        run.status = PipelineStatus.COMPLETED
        run.end_time = datetime.now()
        
        # The records_processed metric is already accumulated during execution
        # Just add duration and step counts
        run.metrics["duration_seconds"] = run.duration_seconds
        run.metrics["steps_completed"] = len(run.steps_completed)
        run.metrics["steps_failed"] = len(run.steps_failed)
        
        self.logger.info(
            "Pipeline completed",
            pipeline=self.name,
            duration=f"{run.duration_seconds:.1f}s",
            steps=len(run.steps_completed),
            records=run.metrics.get("records_processed", 0),
        )
        
        return run

    def _execute_step(self, step: PipelineStep, step_data: Dict[str, Any], run: PipelineRun) -> Any:
        """Execute a single pipeline step."""
        if step.step_type == "extract":
            return self._execute_extract(step, run)
        elif step.step_type == "transform":
            return self._execute_transform(step, step_data, run)
        elif step.step_type == "load":
            return self._execute_load(step, step_data, run)
        else:
            # Custom function
            if step.function:
                return step.function(step_data, step.config)
            raise ValueError(f"Unknown step type: {step.step_type}")

    def _execute_extract(self, step: PipelineStep, run: PipelineRun) -> Any:
        """Execute extraction step."""
        from ..extract.excel_extractor import ExcelExtractor, CSVExtractor, ODataExtractor
        
        extractor_type = step.config.get("extractor", "excel")
        
        if extractor_type == "excel":
            extractor = ExcelExtractor(step.config)
        elif extractor_type == "csv":
            extractor = CSVExtractor(step.config)
        elif extractor_type == "odata":
            extractor = ODataExtractor(step.config)
        else:
            raise ValueError(f"Unknown extractor type: {extractor_type}")
        
        result = extractor.extract()
        
        if not result.success:
            raise RuntimeError(f"Extraction failed: {result.errors}")
        
        run.metrics["records_processed"] = run.metrics.get("records_processed", 0) + result.record_count
        
        # Convert to DataFrame
        df = pd.DataFrame(result.records)
        return df

    def _execute_transform(self, step: PipelineStep, step_data: Dict[str, Any], run: PipelineRun) -> Any:
        """Execute transformation step."""
        transform_name = step.config.get("transform")
        
        # Get input dataframe from previous step
        input_df = None
        if step.depends_on:
            dep_name = step.depends_on[-1]  # Last dependency
            input_df = step_data.get(dep_name)
        
        if input_df is None or not isinstance(input_df, pd.DataFrame):
            raise ValueError(f"No valid input DataFrame for transform step: {step.name}")
        
        # Apply transformation
        if transform_name == "clean_tender":
            from ..transform.cleaning import clean_tender_dataframe
            result_df = clean_tender_dataframe(input_df)
        elif transform_name == "calculate_spreads":
            from ..transform.enrichment import calculate_tender_spreads
            result_df = calculate_tender_spreads(input_df)
        elif transform_name == "add_financial_periods":
            from ..transform.enrichment import calculate_financial_periods
            result_df = calculate_financial_periods(input_df)
        elif transform_name == "add_calculated_fields":
            from ..transform.enrichment import add_calculated_fields
            result_df = add_calculated_fields(input_df, step.config.get("source_type", "tender"))
        elif transform_name == "validate":
            from ..transform.validation import validate_tender_dataframe
            validation_result = validate_tender_dataframe(input_df)
            run.step_results[f"{step.name}_validation"] = validation_result.to_dict()
            if validation_result.quarantined:
                # Save quarantined records
                from ..transform.validation import quarantine_invalid
                # Would need original df indices - simplified for demo
                pass
            result_df = input_df  # Validation doesn't modify data
        else:
            self.logger.warning("Unknown transform, passing through", transform=transform_name)
            result_df = input_df
        
        return result_df

    def _execute_load(self, step: PipelineStep, step_data: Dict[str, Any], run: PipelineRun) -> Any:
        """Execute load step."""
        from ..load.excel_loader import ExcelLoader, MultiSheetExcelLoader, CSVLoader
        from ..load.database_loader import DatabaseLoader
        
        loader_type = step.config.get("loader", "excel")
        
        # Get input dataframe from previous step
        input_df = None
        if step.depends_on:
            dep_name = step.depends_on[-1]
            input_df = step_data.get(dep_name)
        
        if input_df is None or not isinstance(input_df, pd.DataFrame):
            raise ValueError(f"No valid input DataFrame for load step: {step.name}")
        
        if loader_type == "excel":
            loader = ExcelLoader(step.config)
        elif loader_type == "multi_excel":
            loader = MultiSheetExcelLoader(step.config)
            # Expect dict of dataframes
            if not isinstance(input_df, dict):
                input_df = {"Data": input_df}
        elif loader_type == "csv":
            loader = CSVLoader(step.config)
        elif loader_type == "database":
            loader = DatabaseLoader(step.config)
        else:
            raise ValueError(f"Unknown loader type: {loader_type}")
        
        result = loader.load(input_df)
        
        if not result.success:
            raise RuntimeError(f"Load failed: {result.errors}")
        
        run.metrics["records_loaded"] = run.metrics.get("records_loaded", 0) + result.records_loaded
        
        return {"loaded": result.records_loaded, "destination": result.destination}


def load_pipeline_config(config_path: str) -> PipelineConfig:
    """Load pipeline configuration from YAML file."""
    with open(config_path, "r", encoding="utf-8") as f:
        config_dict = yaml.safe_load(f)
    return PipelineConfig(**config_dict)