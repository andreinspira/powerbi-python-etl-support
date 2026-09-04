"""
Pipeline monitoring and alerting for Power BI ETL.
"""

import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
from pathlib import Path
import json
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class PipelineMetric:
    """Single metric measurement."""
    name: str
    value: float
    timestamp: datetime = field(default_factory=datetime.now)
    tags: Dict[str, str] = field(default_factory=dict)
    unit: str = ""


@dataclass
class PipelineAlert:
    """Alert definition and state."""
    name: str
    condition: Callable[[Dict[str, float]], bool]  # Returns True if alert should fire
    severity: str = "warning"  # info, warning, critical
    message: str = ""
    cooldown_seconds: int = 300  # Minimum time between alerts
    last_fired: Optional[datetime] = None


class PipelineMonitor:
    """
    Monitors pipeline execution and emits metrics/alerts.
    Supports structured logging, file-based metrics, and webhook notifications.
    """

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.metrics: List[PipelineMetric] = []
        self.alerts: List[PipelineAlert] = []
        self.metrics_file = Path(self.config.get("metrics_file", "logs/pipeline_metrics.jsonl"))
        self.alerts_file = Path(self.config.get("alerts_file", "logs/pipeline_alerts.jsonl"))
        self.webhook_url = self.config.get("webhook_url")
        self._setup_directories()

    def _setup_directories(self) -> None:
        """Ensure log directories exist."""
        self.metrics_file.parent.mkdir(parents=True, exist_ok=True)
        self.alerts_file.parent.mkdir(parents=True, exist_ok=True)

    def record_metric(
        self,
        name: str,
        value: float,
        tags: Dict[str, str] = None,
        unit: str = "",
    ) -> None:
        """Record a metric measurement."""
        metric = PipelineMetric(
            name=name,
            value=value,
            tags=tags or {},
            unit=unit,
        )
        self.metrics.append(metric)
        self._write_metric(metric)
        logger.debug("Metric recorded", name=name, value=value, tags=tags)

    def record_pipeline_start(self, pipeline_name: str) -> None:
        """Record pipeline start."""
        self.record_metric(
            "pipeline_start",
            1,
            tags={"pipeline": pipeline_name, "status": "started"},
        )

    def record_pipeline_end(
        self,
        pipeline_name: str,
        status: str,
        duration_seconds: float,
        records_processed: int,
        records_loaded: int,
    ) -> None:
        """Record pipeline completion with metrics."""
        self.record_metric(
            "pipeline_end",
            1,
            tags={"pipeline": pipeline_name, "status": status},
        )
        self.record_metric(
            "pipeline_duration_seconds",
            duration_seconds,
            tags={"pipeline": pipeline_name, "status": status},
            unit="seconds",
        )
        self.record_metric(
            "records_processed",
            records_processed,
            tags={"pipeline": pipeline_name},
            unit="records",
        )
        self.record_metric(
            "records_loaded",
            records_loaded,
            tags={"pipeline": pipeline_name},
            unit="records",
        )
        self.record_metric(
            "success_rate",
            records_loaded / records_processed if records_processed > 0 else 0,
            tags={"pipeline": pipeline_name},
            unit="percent",
        )

    def record_step_metric(
        self,
        pipeline_name: str,
        step_name: str,
        status: str,
        duration_seconds: float,
        records_in: int = 0,
        records_out: int = 0,
    ) -> None:
        """Record step-level metrics."""
        self.record_metric(
            "step_duration_seconds",
            duration_seconds,
            tags={"pipeline": pipeline_name, "step": step_name, "status": status},
            unit="seconds",
        )
        self.record_metric(
            "step_throughput",
            records_out / duration_seconds if duration_seconds > 0 else 0,
            tags={"pipeline": pipeline_name, "step": step_name},
            unit="records/sec",
        )

    def check_alerts(self, context: Dict[str, float]) -> List[PipelineAlert]:
        """Check all alerts against current context."""
        fired = []
        for alert in self.alerts:
            # Check cooldown
            if alert.last_fired:
                elapsed = (datetime.now() - alert.last_fired).total_seconds()
                if elapsed < alert.cooldown_seconds:
                    continue

            if alert.condition(context):
                alert.last_fired = datetime.now()
                fired.append(alert)
                self._write_alert(alert, context)
                logger.warning(
                    "Alert fired",
                    alert=alert.name,
                    severity=alert.severity,
                    message=alert.message,
                )

        return fired

    def add_alert(
        self,
        name: str,
        condition: Callable[[Dict[str, float]], bool],
        severity: str = "warning",
        message: str = "",
        cooldown_seconds: int = 300,
    ) -> None:
        """Add an alert definition."""
        alert = PipelineAlert(
            name=name,
            condition=condition,
            severity=severity,
            message=message,
            cooldown_seconds=cooldown_seconds,
        )
        self.alerts.append(alert)
        logger.info("Alert registered", name=name, severity=severity)

    def _write_metric(self, metric: PipelineMetric) -> None:
        """Write metric to JSONL file."""
        try:
            with open(self.metrics_file, "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "name": metric.name,
                    "value": metric.value,
                    "timestamp": metric.timestamp.isoformat(),
                    "tags": metric.tags,
                    "unit": metric.unit,
                }) + "\n")
        except Exception as e:
            logger.error("Failed to write metric", error=str(e))

    def _write_alert(self, alert: PipelineAlert, context: Dict[str, float]) -> None:
        """Write alert to JSONL file."""
        try:
            with open(self.alerts_file, "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "name": alert.name,
                    "severity": alert.severity,
                    "message": alert.message,
                    "timestamp": alert.last_fired.isoformat() if alert.last_fired else None,
                    "context": context,
                }) + "\n")
        except Exception as e:
            logger.error("Failed to write alert", error=str(e))

    def get_metrics_summary(self, pipeline_name: str = None, since_hours: int = 24) -> Dict[str, Any]:
        """Get summary of recent metrics."""
        from datetime import timedelta
        
        cutoff = datetime.now() - timedelta(hours=since_hours)
        filtered = [
            m for m in self.metrics
            if m.timestamp >= cutoff and (pipeline_name is None or m.tags.get("pipeline") == pipeline_name)
        ]
        
        if not filtered:
            return {"count": 0}
        
        # Group by name
        by_name: Dict[str, List[PipelineMetric]] = {}
        for m in filtered:
            by_name.setdefault(m.name, []).append(m)
        
        summary = {}
        for name, metrics in by_name.items():
            values = [m.value for m in metrics]
            summary[name] = {
                "count": len(values),
                "min": min(values),
                "max": max(values),
                "avg": sum(values) / len(values),
                "latest": metrics[-1].value,
                "unit": metrics[0].unit,
            }
        
        return summary


# Default alerts for Power BI ETL pipelines
def setup_default_alerts(monitor: PipelineMonitor) -> None:
    """Configure default alerts for ETL pipelines."""
    
    # Pipeline duration too long
    monitor.add_alert(
        name="pipeline_duration_high",
        condition=lambda ctx: ctx.get("pipeline_duration_seconds", 0) > 1800,  # 30 minutes
        severity="warning",
        message="Pipeline duration exceeded 30 minutes",
        cooldown_seconds=3600,
    )
    
    # Low success rate
    monitor.add_alert(
        name="success_rate_low",
        condition=lambda ctx: ctx.get("success_rate", 1) < 0.95,
        severity="critical",
        message="Pipeline success rate below 95%",
        cooldown_seconds=1800,
    )
    
    # No records processed
    monitor.add_alert(
        name="no_records_processed",
        condition=lambda ctx: ctx.get("records_processed", 1) == 0,
        severity="warning",
        message="Pipeline processed zero records",
        cooldown_seconds=3600,
    )
    
    # Step throughput too low
    monitor.add_alert(
        name="step_throughput_low",
        condition=lambda ctx: ctx.get("step_throughput", float("inf")) < 100,
        severity="info",
        message="Step throughput below 100 records/sec",
        cooldown_seconds=1800,
    )