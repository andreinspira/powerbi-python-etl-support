"""
Pipeline registry for managing multiple pipeline configurations.
"""

from typing import Dict, List, Optional, Any
from pathlib import Path
import yaml
import structlog
from ..config.schemas import PipelineConfig

logger = structlog.get_logger(__name__)


class PipelineRegistry:
    """
    Registry for managing multiple pipeline configurations.
    Supports discovery, validation, and execution of registered pipelines.
    """

    def __init__(self, config_dir: str = "config"):
        self.config_dir = Path(config_dir)
        self._pipelines: Dict[str, PipelineConfig] = {}
        self._load_all()

    def _load_all(self) -> None:
        """Load all pipeline configurations from config directory."""
        if not self.config_dir.exists():
            self.logger.warning("Config directory not found", path=str(self.config_dir))
            return

        for config_file in self.config_dir.glob("*.yaml"):
            try:
                with open(config_file, "r", encoding="utf-8") as f:
                    config_dict = yaml.safe_load(f)
                pipeline = PipelineConfig(**config_dict)
                self._pipelines[pipeline.name] = pipeline
                self.logger.info("Registered pipeline", name=pipeline.name, file=config_file.name)
            except Exception as e:
                self.logger.error("Failed to load pipeline config", file=config_file.name, error=str(e))

    def get(self, name: str) -> Optional[PipelineConfig]:
        """Get pipeline configuration by name."""
        return self._pipelines.get(name)

    def list(self) -> List[str]:
        """List all registered pipeline names."""
        return list(self._pipelines.keys())

    def list_details(self) -> List[Dict[str, Any]]:
        """List all pipelines with details."""
        return [
            {
                "name": p.name,
                "description": p.description,
                "schedule": p.schedule,
                "source_type": p.source.get("type") if p.source else None,
                "steps": len(p.transforms),
            }
            for p in self._pipelines.values()
        ]

    def register(self, pipeline: PipelineConfig) -> None:
        """Register a new pipeline configuration."""
        self._pipelines[pipeline.name] = pipeline
        self.logger.info("Pipeline registered", name=pipeline.name)

    def unregister(self, name: str) -> bool:
        """Unregister a pipeline."""
        if name in self._pipelines:
            del self._pipelines[name]
            self.logger.info("Pipeline unregistered", name=name)
            return True
        return False

    def validate_all(self) -> Dict[str, List[str]]:
        """Validate all registered pipelines."""
        errors = {}
        for name, pipeline in self._pipelines.items():
            pipeline_errors = []
            # Basic validation
            if not pipeline.source:
                pipeline_errors.append("Missing source configuration")
            if not pipeline.transforms:
                pipeline_errors.append("No transform steps defined")
            if not pipeline.destination:
                pipeline_errors.append("Missing destination configuration")
            
            # Check for circular dependencies in transforms
            step_names = [t.get("name") for t in pipeline.transforms if t.get("name")]
            for transform in pipeline.transforms:
                for dep in transform.get("depends_on", []):
                    if dep not in step_names:
                        pipeline_errors.append(f"Step '{transform.get('name')}' depends on unknown step '{dep}'")
            
            if pipeline_errors:
                errors[name] = pipeline_errors

        return errors