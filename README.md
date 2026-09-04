# Power BI Python ETL Support

[![CI](https://github.com/andreinspira/powerbi-python-etl-support/actions/workflows/ci.yml/badge.svg)](https://github.com/andreinspira/powerbi-python-etl-support/actions/workflows/ci.yml)

Production-grade Python ETL framework for preparing, validating, transforming, and delivering analytics-ready datasets to Power BI.

## Overview

This portfolio project demonstrates end-to-end data engineering capabilities for Power BI environments:

- **Excel/SharePoint data ingestion** with parameterized sources
- **Dynamics 365 / Dataverse OData integration patterns** (stubbed for demo)
- **Data validation** with Pydantic schemas and quarantine pattern
- **Monthly/quarterly spread calculations** for tender and pipeline reporting
- **Power Query M code generation** for direct Power BI use
- **DAX measure definitions** for financial and operational reporting
- **Incremental refresh support** with watermark tracking
- **Structured logging, monitoring, retries, and error handling**
- **Automated tests** executed by GitHub Actions on Python 3.10, 3.11, and 3.12

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐     ┌──────────────┐
│  Extract    │────▶│  Transform   │────▶│   Load      │────▶│  Power BI    │
│             │     │              │     │             │     │  Ready Files │
│ • Excel     │     │ • Clean      │     │ • Excel     │     │  (.xlsx)     │
│ • CSV       │     │ • Validate   │     │ • CSV       │     │              │
│ • OData     │     │ • Enrich     │     │ • Parquet   │     │ • DAX        │
│ • Dynamics  │     │ • Spread     │     │ • PostgreSQL│     │ • M Code     │
│   365       │     │ • Periods    │     │             │     │ • RLS        │
└─────────────┘     └──────────────┘     └─────────────┘     └──────────────┘
```

## Technical Capabilities

| Capability | Implementation |
|------------|----------------|
| **Power BI data preparation** | Structured datasets, calculated fields, Excel/CSV outputs, Power Query and DAX examples |
| **Python ETL engineering** | Modular extract/transform/load framework using pandas, Pydantic, SQLAlchemy and structlog |
| **Dynamics 365 / Dataverse** | OData extractor with OAuth2 client-credentials integration pattern (stubbed for demo) |
| **Data quality & troubleshooting** | Schema validation, quarantine pattern, structured errors and diagnostic logging |
| **Refresh & reliability** | Incremental-processing patterns, watermark tracking, retries and backoff |
| **Tender / pipeline analytics** | Monthly, quarterly and probability-weighted spread calculations |
| **Configuration-driven pipelines** | YAML orchestration with explicit dependencies between ETL stages |
| **Automated verification** | Unit and integration tests executed in CI across Python 3.10–3.12 |

## Quick Start

```bash
# Clone and setup
git clone https://github.com/andreinspira/powerbi-python-etl-support.git
cd powerbi-python-etl-support

# Install dependencies
pip install -e ".[dev]"

# Generate sample data
python -m src.powerbi_etl.pipeline.run_pipeline generate-sample

# Run pipeline in demo mode
python -m src.powerbi_etl.pipeline.run_pipeline tender_pipeline --demo

# Or run with real data (place the source Excel file in data/raw/)
python -m src.powerbi_etl.pipeline.run_pipeline tender_pipeline
```

## Project Structure

```
powerbi-python-etl-support/
├── config/
│   └── tender_pipeline.yaml   # Main tender ETL pipeline
├── data/
│   ├── raw/                   # Input files (gitignored)
│   ├── processed/             # Intermediate data (gitignored)
│   └── output/                # Power BI-ready outputs (gitignored)
├── scripts/
│   └── sanitize_outputs.py    # Portfolio output sanitization
├── src/powerbi_etl/
│   ├── config/                # Settings & Pydantic schemas
│   ├── extract/               # Excel, CSV and OData extractors
│   ├── transform/             # Cleaning, validation, enrichment and spreads
│   ├── load/                  # Excel, CSV and database loaders
│   ├── pipeline/              # Orchestration, registry and monitoring
│   └── utils/                 # Logging, retry and helpers
├── tests/
│   ├── unit/
│   └── integration/
├── .github/workflows/ci.yml   # Automated multi-version tests
├── LICENSE
├── pyproject.toml
└── README.md
```

## Pipeline Configuration

Pipelines are defined in YAML, keeping orchestration separate from implementation code:

```yaml
name: "tender_pipeline"
description: "Extracts tender data from Excel/SharePoint and transforms it for analytics"
schedule: "0 6 * * 1"

source:
  type: "excel"
  file_path: "data/raw/Tender_Register_Sample.xlsx"

transforms:
  - name: "extract_raw"
    type: "extract"
    config:
      extractor: "excel"
      file_path: "data/raw/Tender_Register_Sample.xlsx"

  - name: "calculate_spreads"
    type: "transform"
    config:
      transform: "calculate_spreads"
    depends_on: ["clean_data"]

  - name: "load_excel"
    type: "load"
    config:
      loader: "excel"
      output_path: "data/output/Tender_Dashboard_Source.xlsx"
      column_formats:
        MonthlySpread:
          number_format: "#,##0.00"
    depends_on: ["add_calculated_fields"]
```

## Analytics-Ready Outputs

The pipeline can produce data sources suitable for Power BI consumption:

| Output | Purpose |
|--------|---------|
| `Tender_Dashboard_Source.xlsx` | Formatted Excel source for Power BI |
| `Tender_Dashboard_Source.csv` | Portable CSV alternative |
| Database staging table | Pattern for database-backed refresh workflows |

### Key Calculated Fields

- **MonthlySpread** — `ReportingValue / ProjectDurationMonths`
- **QuarterlySpread** — `MonthlySpread * 3`
- **WeightedMonthlySpread** — `WeightedValue / ProjectDurationMonths`
- **ProjectDurationMonths** — months between project start and end dates
- **HasMissingDates** — data-quality flag for incomplete date ranges
- **IsActive / IsWon / IsLost** — status flags for analytical measures
- **ValueTier** — deal-size categorization

## Power BI Integration

### Power Query M Example

```m
let
    Source = Excel.Workbook(File.Contents("data/output/Tender_Dashboard_Source.xlsx"), null, true),
    Sheet = Source{[Item="fact_Tenders",Kind="Sheet"]}[Data],
    Headers = Table.PromoteHeaders(Sheet, [PromoteAllScalars=true]),
    Types = Table.TransformColumnTypes(Headers, {{"TenderID", type text}, ...}),
    CleanStrings = Table.TransformColumns(Types, {{"ClientName", Text.Trim, type text}, ...}),
    AddSpreads = Table.AddColumn(CleanStrings, "MonthlySpread", each [ReportingValue] / [ProjectDurationMonths])
in
    AddSpreads
```

### DAX Examples

```dax
Total Tender Value = SUM(Tenders[ReportingValue])
Weighted Pipeline = SUM(Tenders[WeightedValue])
Monthly Spread Value = SUM(Tenders[MonthlySpread])
Quarterly Spread Value = SUM(Tenders[QuarterlySpread])

Win Rate = DIVIDE(
    CALCULATE(COUNTROWS(Tenders), Tenders[TenderStatus] = "Won"),
    CALCULATE(COUNTROWS(Tenders), Tenders[TenderStatus] IN {"Won", "Lost", "Declined", "Cancelled"})
)

Active Pipeline = CALCULATE([Weighted Pipeline], Tenders[IsActive] = TRUE())
```

## Testing & Continuous Integration

The repository includes unit and integration tests. GitHub Actions installs the project and executes the automated test suite on **Python 3.10, 3.11 and 3.12** for pushes to `main` and pull requests.

```bash
# Complete automated test suite
pytest tests

# Coverage
pytest --cov=src --cov-report=term-missing

# Type checking
mypy src/

# Linting
ruff check src/ tests/
```

## Portfolio Sanitization

The repository includes a sanitization utility for checking generated portfolio outputs before publication:

```bash
python scripts/sanitize_outputs.py check-sensitive data/portfolio
```

Real credentials and client data are not required for the demonstration. Dynamics 365 / Dataverse connectivity is represented as an integration pattern and can be configured against an authorized environment using appropriate credentials.

## Technology Stack

**Python 3.10+ · pandas · Pydantic · SQLAlchemy · structlog · openpyxl · pytest · GitHub Actions · Power BI · Power Query · DAX · OData / Dataverse patterns**

## License

MIT License — see [LICENSE](LICENSE) for details.

## Author

**André Guilherme da Cunha Magalhães**  
Power BI + Python | Data Engineering & BI  
https://github.com/andreinspira

---

*Portfolio demonstration project. All demonstration data is synthetic; no client-confidential data is included.*
