"""
CLI entry point for running Power BI ETL pipelines.
"""

import typer
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
import structlog
from powerbi_etl.pipeline.orchestrator import PipelineOrchestrator, PipelineRun, load_pipeline_config
from powerbi_etl.pipeline.registry import PipelineRegistry
from powerbi_etl.config.settings import get_settings

app = typer.Typer(
    name="powerbi-etl",
    help="Power BI Python ETL Pipeline Runner - Portfolio demonstration for Power BI + Python Support Collaborator role",
    add_completion=False,
)
console = Console()

# Configure structlog
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)


@app.command()
def run(
    pipeline: str = typer.Argument(..., help="Pipeline name or config file path"),
    config_dir: str = typer.Option("config", "--config-dir", "-c", help="Configuration directory"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Validate config without running"),
    demo: bool = typer.Option(False, "--demo", help="Run with generated sample data"),
):
    """Run a pipeline."""
    config_path = Path(pipeline)
    if not config_path.exists():
        config_path = Path(config_dir) / f"{pipeline}.yaml"
    
    if not config_path.exists():
        console.print(f"[red]Pipeline config not found: {config_path}[/red]")
        raise typer.Exit(1)
    
    console.print(f"[green]Loading pipeline:[/green] {config_path}")
    config = load_pipeline_config(str(config_path))
    
    if dry_run:
        console.print("[yellow]Dry run - validating config only[/yellow]")
        _print_config(config)
        return
    
    if demo:
        console.print("[cyan]Demo mode - using generated sample data[/cyan]")
        _inject_demo_config(config)
    
    orchestrator = PipelineOrchestrator(config)
    run_context = PipelineRun(pipeline_name=config.name)
    
    try:
        result = orchestrator.run()
        _print_result(result)
    except Exception as e:
        console.print(f"[red]Pipeline failed:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def list(
    config_dir: str = typer.Option("config", "--config-dir", "-c", help="Configuration directory"),
):
    """List available pipeline configurations."""
    registry = PipelineRegistry(config_dir)
    pipelines = registry.list_details()
    
    if not pipelines:
        console.print("[yellow]No pipelines found[/yellow]")
        return
    
    table = Table(title="Available Pipelines")
    table.add_column("Name", style="cyan")
    table.add_column("Description")
    table.add_column("Schedule")
    table.add_column("Source")
    table.add_column("Steps", justify="right")
    
    for p in pipelines:
        table.add_row(
            p["name"],
            p["description"][:60] + "..." if len(p["description"]) > 60 else p["description"],
            p["schedule"] or "Manual",
            p["source_type"] or "N/A",
            str(p["steps"]),
        )
    
    console.print(table)


@app.command()
def validate(
    pipeline: str = typer.Argument(..., help="Pipeline name or config file path"),
    config_dir: str = typer.Option("config", "--config-dir", "-c", help="Configuration directory"),
):
    """Validate pipeline configuration."""
    config_path = Path(config_dir) / f"{pipeline}.yaml"
    if not config_path.exists():
        config_path = Path(pipeline)
    
    config = load_pipeline_config(str(config_path))
    _print_config(config)
    console.print("[green]Configuration valid[/green]")


@app.command()
def generate_sample(
    output_dir: str = typer.Option("data/raw", "--output", "-o", help="Output directory"),
    tender_records: int = typer.Option(50, "--tender-records", help="Number of tender records"),
    financial_records: int = typer.Option(200, "--financial-records", help="Number of financial records"),
):
    """Generate sample data files for testing."""
    from powerbi_etl.utils.helpers import generate_sample_tender_data, create_sample_financial_data
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    console.print("[cyan]Generating sample data...[/cyan]")
    
    # Tender data
    tender_df = generate_sample_tender_data(tender_records)
    tender_path = output_path / "Tender_Register_Sample.xlsx"
    tender_df.to_excel(tender_path, index=False)
    console.print(f"[green]Generated:[/green] {tender_path} ({len(tender_df)} records)")
    
    # Financial data
    financial_df = create_sample_financial_data(financial_records)
    financial_path = output_path / "Financial_Transactions_Sample.csv"
    financial_df.to_csv(financial_path, index=False)
    console.print(f"[green]Generated:[/green] {financial_path} ({len(financial_df)} records)")
    
    console.print("[green]Sample data generation complete![/green]")


@app.command()
def demo():
    """Run full demo: generate data + run pipeline."""
    console.print(Panel.fit(
        "[bold cyan]Power BI Python ETL - Demo Run[/bold cyan]\n"
        "This will generate sample data and run the tender pipeline.",
        title="Demo Mode",
    ))
    
    # Generate sample data
    from powerbi_etl.utils.helpers import generate_sample_tender_data, create_sample_financial_data
    
    output_path = Path("data/raw")
    output_path.mkdir(parents=True, exist_ok=True)
    
    console.print("[cyan]Generating sample data...[/cyan]")
    tender_df = generate_sample_tender_data(50)
    tender_df.to_excel(output_path / "Tender_Register_Sample.xlsx", index=False)
    
    financial_df = create_sample_financial_data(200)
    financial_df.to_csv(output_path / "Financial_Transactions_Sample.csv", index=False)
    
    # Run pipeline
    config_path = Path("config/tender_pipeline.yaml")
    if not config_path.exists():
        console.print("[red]Pipeline config not found. Run from project root.[/red]")
        raise typer.Exit(1)
    
    config = load_pipeline_config(str(config_path))
    orchestrator = PipelineOrchestrator(config)
    run_context = PipelineRun(pipeline_name=config.name)
    
    try:
        result = orchestrator.run()
        _print_result(result)
        console.print("[green]Demo completed successfully![/green]")
    except Exception as e:
        console.print(f"[red]Demo failed:[/red] {e}")
        raise typer.Exit(1)


def _print_config(config):
    """Print pipeline configuration."""
    console.print(f"\n[bold]Pipeline:[/bold] {config.name}")
    console.print(f"[bold]Description:[/bold] {config.description}")
    console.print(f"[bold]Schedule:[/bold] {config.schedule or 'Manual'}")
    console.print("\n[bold]Steps:[/bold]")
    for step in config.transforms:
        deps = f" (depends on: {', '.join(step.get('depends_on', []))})" if step.get('depends_on') else ""
        console.print(f"  • {step['name']} ({step.get('type', 'unknown')}){deps}")


def _print_result(result: PipelineRun):
    """Print pipeline execution result."""
    status_color = "green" if result.status.value == "completed" else "red"
    
    console.print(f"\n[bold]Pipeline:[/bold] {result.pipeline_name}")
    console.print(f"[bold]Status:[/bold] [{status_color}]{result.status.value}[/{status_color}]")
    console.print(f"[bold]Duration:[/bold] {result.duration_seconds:.1f}s")
    console.print(f"[bold]Steps Completed:[/bold] {len(result.steps_completed)}")
    console.print(f"[bold]Steps Failed:[/bold] {len(result.steps_failed)}")
    console.print(f"[bold]Records Processed:[/bold] {result.metrics.get('records_processed', 0)}")
    console.print(f"[bold]Records Loaded:[/bold] {result.metrics.get('records_loaded', 0)}")
    
    if result.errors:
        console.print("\n[red]Errors:[/red]")
        for error in result.errors:
            console.print(f"  • {error}")


def _inject_demo_config(config):
    """Inject demo-specific configuration."""
    # Modify source to use sample files
    config.source = {
        "type": "excel",
        "file_path": "data/raw/Tender_Register_Sample.xlsx",
        "sheet_name": 0,
    }
    
    # Ensure output goes to demo location
    for transform in config.transforms:
        if transform.get("config", {}).get("loader") == "excel":
            transform["config"]["output_path"] = "data/output/tender_dashboard_source_demo.xlsx"


if __name__ == "__main__":
    app()