# Power BI Python ETL Support

Production-grade ETL pipelines for Power BI data preparation — portfolio demonstration for **Power BI + Python Support Collaborator** role (Upwork PP-010).

## Overview

This repository demonstrates end-to-end ETL capabilities specifically tailored for Power BI environments:

- **Excel/SharePoint data ingestion** with parameterized sources
- **Dynamics 365 OData integration patterns** (stubbed for demo)
- **Data validation** with Pydantic schemas and quarantine pattern
- **Monthly/quarterly spread calculations** — key requirement for tender/pipeline dashboards
- **Power Query M code generation** for direct Power BI use
- **DAX measure definitions** for financial and operational reporting
- **Incremental refresh support** with watermark tracking
- **Structured logging, monitoring, and alerting**

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

## Key Features for PP-010

| Requirement | Implementation |
|-------------|----------------|
| **Power BI data modeling / data sources** | Star schema with conformed dimensions, parameterized Excel/SharePoint sources |
| **Solid Python skills** | Full ETL framework with pandas, Pydantic, SQLAlchemy, structlog |
| **Dynamics 365 integration** | OData extractor with OAuth2 pattern (stubbed for demo) |
| **EU-based / GMT+3 hours** | Code developed and tested in compatible timezone |
| **Troubleshooting existing reports** | Validation framework with quarantine, detailed error reporting |
| **Refresh/connection issues** | Incremental refresh patterns, watermark tracking |
| **Monthly/quarterly spreads** | `calculate_tender_spreads()` — distributes project values across fiscal periods |

## Quick Start

```bash
# Clone and setup
git clone https://github.com/andreinspira/powerbi-python-etl-support.git
cd powerbi-python-etl-support

# Install dependencies
pip install -e ".[dev]"

# Generate sample data
python -m src.powerbi_etl.pipeline.run_pipeline generate-sample

# Run pipeline (demo mode with sample data)
python -m src.powerbi_etl.pipeline.run_pipeline tender_pipeline --demo

# Or run with real data (place Excel file in data/raw/)
python -m src.powerbi_etl.pipeline.run_pipeline tender_pipeline
```

## Project Structure

```
powerbi-python-etl-support/
├── config/                    # Pipeline YAML configurations
│   └── tender_pipeline.yaml   # Main tender ETL pipeline
├── data/
│   ├── raw/                   # Input files (gitignored)
│   ├── processed/             # Intermediate Parquet (gitignored)
│   └── output/                # Power BI ready Excel/CSV (gitignored)
├── scripts/
│   └── sanitize_outputs.py    # Remove credentials before publication
├── src/powerbi_etl/
│   ├── config/                # Settings & Pydantic schemas
│   ├── extract/               # Excel, CSV, OData, Dynamics 365
│   ├── transform/             # Clean, validate, enrich, spreads
│   ├── load/                  # Excel, CSV, Parquet, PostgreSQL
│   ├── pipeline/              # Orchestrator, registry, monitoring
│   └── utils/                 # Logging, retry, helpers
├── tests/
│   ├── unit/
│   └── integration/
├── .github/workflows/ci.yml   # Automated test workflow
├── LICENSE
├── pyproject.toml
└── README.md
```

## Pipeline Configuration

Pipelines are defined in YAML:

```yaml
name: "tender_pipeline"
description: "Extracts tender data from Excel/SharePoint, transforms for Power BI"
schedule: "0 6 * * 1"  # Weekly Monday 6 AM

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
      transform: "calculate_spreads"  # KEY for PP-010/PP-011
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

## Generated Outputs

The pipeline produces Power BI-ready files:

| Output | Description |
|--------|-------------|
| `Tender_Dashboard_Source.xlsx` | Formatted Excel with fact table + metadata sheet |
| `Tender_Dashboard_Source.csv` | CSV alternative |
| `fact_tenders` (PostgreSQL) | Staging table for incremental refresh |

### Key Calculated Fields

- **MonthlySpread** — `ReportingValue / ProjectDurationMonths`
- **QuarterlySpread** — `MonthlySpread * 3`
- **WeightedMonthlySpread** — `WeightedValue / ProjectDurationMonths`
- **ProjectDurationMonths** — Months between Start/End dates
- **HasMissingDates** — Flags records with missing dates (PP-011 requirement)
- **IsActive/IsWon/IsLost** — Status flags for DAX measures
- **ValueTier** — Deal size categorization

## Power BI Integration

### Power Query M Code
```m
// Generated by generate_power_query_m_code()
// Paste into Power BI Power Query Editor
let
    Source = Excel.Workbook(File.Contents("data/output/Tender_Dashboard_Source.xlsx"), null, true),
    Sheet = Source{[Item="fact_Tenders",Kind="Sheet"]}[Data],
    Headers = Table.PromoteHeaders(Sheet, [PromoteAllScalars=true]),
    Types = Table.TransformColumnTypes(Headers, {{"TenderID", type text}, ...}),
    CleanStrings = Table.TransformColumns(Types, {{"ClientName", Text.Trim, type text}, ...}),
    AddSpreads = Table.AddColumn(CleanStrings, "MonthlySpread", each [ReportingValue] / [ProjectDurationMonths]),
in
    AddSpreads
```

### DAX Measures
```dax
// Key measures for tender/pipeline dashboards
Total Tender Value = SUM(Tenders[ReportingValue])
Weighted Pipeline = SUM(Tenders[WeightedValue])
Monthly Spread Value = SUM(Tenders[MonthlySpread])
Quarterly Spread Value = SUM(Tenders[QuarterlySpread])
Win Rate = DIVIDE(
    CALCULATE(COUNTROWS(Tenders), Tenders[TenderStatus] = "Won"),
    CALCULATE(COUNTROWS(Tenders), Tenders[TenderStatus] IN {"Won", "Lost", "Declined", "Cancelled"})
)
Active Pipeline = CALCULATE([Weighted Pipeline], Tenders[IsActive] = TRUE())
YoY % = DIVIDE([Total Tender Value] - CALCULATE([Total Tender Value], SAMEPERIODLASTYEAR('Date'[Date])), CALCULATE([Total Tender Value], SAMEPERIODLASTYEAR('Date'[Date])))
```

## Testing

```bash
# Run unit tests
pytest tests/unit -v

# Run integration tests
pytest tests/integration -v

# Run with coverage
pytest --cov=src --cov-report=term-missing

# Type checking
mypy src/

# Linting
ruff check src/ tests/
black src/ tests/
```

## CI

GitHub Actions workflow (`.github/workflows/ci.yml`) installs the project with development dependencies and runs the automated unit and integration test suite on pushes to `main` and on pull requests.

## Portfolio Sanitization

Before publishing to GitHub:

```bash
# Sanitize outputs (removes credentials, emails, personal data)
python scripts/sanitize_outputs.py sanitize-outputs -i data/output -o data/portfolio

# Check for sensitive data
python scripts/sanitize_outputs.py check-sensitive data/portfolio
```

## Requirements

- Python 3.10+
- pandas 2.1+
- pydantic 2.5+
- structlog 24.1+
- openpyxl 3.1+
- sqlalchemy 2.0+
- Optional: PostgreSQL for database loader

## License

MIT License — see [LICENSE](LICENSE) for details.

## Author

**André Guilherme da Cunha Magalhães**  
Power BI + Python Specialist | Data Engineering & BI  
📧 oficial.andre@hotmail.com  
🔗 https://github.com/andreinspira

---

*This is a DEMONSTRATION / PORTFOLIO PROJECT — not work performed for a real client. All data is synthetic.*