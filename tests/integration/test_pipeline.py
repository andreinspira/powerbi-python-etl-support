"""
Integration tests for full pipeline execution.
"""

import pytest
import pandas as pd
from pathlib import Path
import tempfile
import shutil

from powerbi_etl.pipeline.orchestrator import PipelineOrchestrator, PipelineRun
from powerbi_etl.config.schemas import PipelineConfig
from powerbi_etl.config.settings import get_settings


class TestPipelineIntegration:
    """Integration tests for full pipeline execution."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for test outputs."""
        temp = Path(tempfile.mkdtemp())
        yield temp
        shutil.rmtree(temp, ignore_errors=True)
    
    @pytest.fixture
    def sample_tender_file(self, temp_dir):
        """Generate sample tender Excel file."""
        from powerbi_etl.utils.helpers import generate_sample_tender_data
        
        df = generate_sample_tender_data(20)
        file_path = temp_dir / "Tender_Register_Test.xlsx"
        df.to_excel(file_path, index=False)
        return file_path
    
    def test_tender_pipeline_full_run(self, temp_dir, sample_tender_file):
        """Test complete tender pipeline execution."""
        # Create pipeline config for test
        config_dict = {
            "name": "test_tender_pipeline",
            "description": "Test tender pipeline",
            "source": {
                "type": "excel",
                "file_path": str(sample_tender_file),
                "sheet_name": 0,
            },
            "transforms": [
                {
                    "name": "extract_raw",
                    "type": "extract",
                    "config": {
                        "extractor": "excel",
                        "file_path": str(sample_tender_file),
                        "sheet_name": 0,
                    },
                },
                {
                    "name": "validate_schema",
                    "type": "transform",
                    "config": {"transform": "validate"},
                    "depends_on": ["extract_raw"],
                },
                {
                    "name": "clean_data",
                    "type": "transform",
                    "config": {"transform": "clean_tender"},
                    "depends_on": ["validate_schema"],
                },
                {
                    "name": "calculate_spreads",
                    "type": "transform",
                    "config": {"transform": "calculate_spreads"},
                    "depends_on": ["clean_data"],
                },
                {
                    "name": "add_calculated_fields",
                    "type": "transform",
                    "config": {"transform": "add_calculated_fields", "source_type": "tender"},
                    "depends_on": ["calculate_spreads"],
                },
                {
                    "name": "load_excel",
                    "type": "load",
                    "config": {
                        "loader": "excel",
                        "output_path": str(temp_dir / "output" / "Test_Output.xlsx"),
                        "sheet_name": "fact_Tenders",
                    },
                    "depends_on": ["add_calculated_fields"],
                },
            ],
            "destination": {
                "type": "excel",
                "path": str(temp_dir / "output" / "Test_Output.xlsx"),
            },
        }
        
        config = PipelineConfig(**config_dict)
        orchestrator = PipelineOrchestrator(config)
        run = PipelineRun(pipeline_name=config.name)
        
        # Run pipeline
        result = orchestrator.run()
        
        # Assertions
        assert result.status.value == "completed"
        assert len(result.steps_completed) == 6
        assert len(result.steps_failed) == 0
        assert result.metrics.get("records_processed", 0) > 0
        assert result.metrics.get("records_loaded", 0) > 0
        
        # Verify output file exists
        output_path = temp_dir / "output" / "Test_Output.xlsx"
        assert output_path.exists()
        
        # Verify output content
        output_df = pd.read_excel(output_path, sheet_name="fact_Tenders")
        assert len(output_df) > 0
        
        # Check key calculated columns exist
        expected_columns = [
            "MonthlySpread", "QuarterlySpread", "WeightedMonthlySpread",
            "ProjectDurationMonths", "HasMissingDates", "IsActive", "IsWon", "ValueTier"
        ]
        for col in expected_columns:
            assert col in output_df.columns, f"Missing column: {col}"
    
    def test_pipeline_with_missing_dates(self, temp_dir):
        """Test pipeline handles missing dates correctly."""
        from powerbi_etl.utils.helpers import generate_sample_tender_data
        
        # Create data with missing dates
        df = generate_sample_tender_data(10)
        df.loc[0, "ProjectStartDate"] = None
        df.loc[1, "ProjectEndDate"] = None
        
        file_path = temp_dir / "Tender_Missing_Dates.xlsx"
        df.to_excel(file_path, index=False)
        
        config_dict = {
            "name": "test_missing_dates",
            "description": "Test missing dates handling",
            "source": {"type": "excel", "file_path": str(file_path), "sheet_name": 0},
            "transforms": [
                {"name": "extract_raw", "type": "extract", "config": {"extractor": "excel", "file_path": str(file_path)}},
                {"name": "clean_data", "type": "transform", "config": {"transform": "clean_tender"}, "depends_on": ["extract_raw"]},
                {"name": "calculate_spreads", "type": "transform", "config": {"transform": "calculate_spreads"}, "depends_on": ["clean_data"]},
                {"name": "load_excel", "type": "load", "config": {
                    "loader": "excel",
                    "output_path": str(temp_dir / "output" / "Missing_Dates_Test.xlsx"),
                    "sheet_name": "fact_Tenders",
                }, "depends_on": ["calculate_spreads"]},
            ],
            "destination": {"type": "excel", "path": str(temp_dir / "output" / "Missing_Dates_Test.xlsx")},
        }
        
        config = PipelineConfig(**config_dict)
        orchestrator = PipelineOrchestrator(config)
        run = PipelineRun(pipeline_name=config.name)
        result = orchestrator.run()
        
        assert result.status.value == "completed"
        
        # Verify HasMissingDates flag
        output_df = pd.read_excel(temp_dir / "output" / "Missing_Dates_Test.xlsx")
        assert output_df["HasMissingDates"].sum() >= 2


class TestCLI:
    """Test CLI commands."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for test outputs."""
        temp = Path(tempfile.mkdtemp())
        yield temp
        shutil.rmtree(temp, ignore_errors=True)

    def test_generate_sample_command(self, temp_dir):
        """Test sample data generation via CLI."""
        from typer.testing import CliRunner
        from powerbi_etl.pipeline.run_pipeline import app
        
        runner = CliRunner()
        result = runner.invoke(app, ["generate-sample", "--output", str(temp_dir), "--tender-records", "5"])
        
        assert result.exit_code == 0
        assert (temp_dir / "Tender_Register_Sample.xlsx").exists()
        assert (temp_dir / "Financial_Transactions_Sample.csv").exists()
        
        # Verify content
        tender_df = pd.read_excel(temp_dir / "Tender_Register_Sample.xlsx")
        assert len(tender_df) == 5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])