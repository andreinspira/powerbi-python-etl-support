#!/usr/bin/env python3
"""
Sanitize output files for portfolio publication.
Removes any credentials, personal data, or sensitive information.
"""

import typer
from pathlib import Path
import pandas as pd
import re
import shutil

app = typer.Typer(help="Sanitize outputs for portfolio publication")


def sanitize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Remove or replace sensitive columns/values."""
    df = df.copy()
    
    # Columns to remove entirely
    sensitive_columns = [
        "_source_file", "_extracted_at", "_generated_at", "_quarantine_reason", "_quarantined_at",
        "client_id", "client_secret", "tenant_id", "password", "api_key", "access_token",
        "email", "phone", "address", "ssn", "cpf", "cnpj",
    ]
    
    for col in sensitive_columns:
        if col in df.columns:
            df = df.drop(columns=[col])
    
    # Patterns to redact in string columns
    sensitive_patterns = [
        (r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", "[EMAIL REDACTED]"),
        (r"(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}", "[PHONE REDACTED]"),
        (r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b", "[CPF REDACTED]"),  # Brazilian CPF
        (r"\b\d{2}\.?\d{3}\.?\d{3}/\d{4}-?\d{2}\b", "[CNPJ REDACTED]"),  # Brazilian CNPJ
        (r"sk-[a-zA-Z0-9]{48}", "[API KEY REDACTED]"),
        (r"Bearer\s+[a-zA-Z0-9._-]+", "[TOKEN REDACTED]"),
    ]
    
    for col in df.select_dtypes(include=["object"]).columns:
        for pattern, replacement in sensitive_patterns:
            df[col] = df[col].astype(str).str.replace(pattern, replacement, regex=True)
    
    return df


def sanitize_excel_file(input_path: Path, output_path: Path) -> None:
    """Sanitize Excel file - all sheets."""
    import openpyxl
    
    wb = openpyxl.load_workbook(input_path)
    
    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        
        # Check headers for sensitive columns
        headers = [cell.value for cell in ws[1]]
        sensitive_indices = []
        
        for idx, header in enumerate(headers, 1):
            if header and any(s in str(header).lower() for s in ["password", "secret", "token", "key", "email", "phone", "cpf", "cnpj"]):
                sensitive_indices.append(idx)
        
        # Remove sensitive columns
        for idx in sorted(sensitive_indices, reverse=True):
            ws.delete_cols(idx)
        
        # Sanitize cell values
        for row in ws.iter_rows(min_row=2):
            for cell in row:
                if cell.value and isinstance(cell.value, str):
                    for pattern, replacement in [
                        (r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", "[EMAIL REDACTED]"),
                        (r"(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}", "[PHONE REDACTED]"),
                    ]:
                        cell.value = re.sub(pattern, replacement, cell.value)
    
    wb.save(output_path)


def sanitize_config_file(input_path: Path, output_path: Path) -> None:
    """Sanitize YAML/JSON config files."""
    import yaml
    import json
    
    content = input_path.read_text()
    
    # Redact sensitive patterns
    patterns = [
        (r"(password|secret|token|key|api_key|client_secret)\s*:\s*\S+", r"\1: [REDACTED]"),
        (r"(password|secret|token|key|api_key|client_secret)\s*=\s*\S+", r"\1=[REDACTED]"),
        (r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", "[EMAIL REDACTED]"),
    ]
    
    for pattern, replacement in patterns:
        content = re.sub(pattern, replacement, content, flags=re.IGNORECASE)
    
    output_path.write_text(content)


@app.command()
def sanitize_outputs(
    input_dir: str = typer.Option("data/output", "--input", "-i", help="Input directory"),
    output_dir: str = typer.Option("data/portfolio", "--output", "-o", help="Output directory"),
):
    """Sanitize all output files for portfolio publication."""
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    console.print(f"[cyan]Sanitizing outputs from {input_path} to {output_path}[/cyan]")
    
    for file_path in input_path.rglob("*"):
        if file_path.is_file():
            rel_path = file_path.relative_to(input_path)
            out_file = output_path / rel_path
            out_file.parent.mkdir(parents=True, exist_ok=True)
            
            suffix = file_path.suffix.lower()
            
            if suffix in [".xlsx", ".xls"]:
                sanitize_excel_file(file_path, out_file)
                console.print(f"  [green]Sanitized Excel:[/green] {rel_path}")
            elif suffix in [".yaml", ".yml", ".json"]:
                sanitize_config_file(file_path, out_file)
                console.print(f"  [green]Sanitized Config:[/green] {rel_path}")
            elif suffix in [".csv", ".parquet", ".txt"]:
                df = pd.read_parquet(file_path) if suffix == ".parquet" else pd.read_csv(file_path)
                sanitized = sanitize_dataframe(df)
                if suffix == ".parquet":
                    sanitized.to_parquet(out_file, index=False)
                elif suffix == ".csv":
                    sanitized.to_csv(out_file, index=False)
                else:
                    shutil.copy2(file_path, out_file)
                console.print(f"  [green]Sanitized Data:[/green] {rel_path}")
            else:
                shutil.copy2(file_path, out_file)
                console.print(f"  [blue]Copied:[/blue] {rel_path}")
    
    console.print("[green]Sanitization complete![/green]")


@app.command()
def check_sensitive(
    path: str = typer.Argument(..., help="File or directory to check"),
):
    """Check for potential sensitive data in files."""
    check_path = Path(path)
    
    patterns = [
        (r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", "Email"),
        (r"(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}", "Phone"),
        (r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b", "CPF"),
        (r"\b\d{2}\.?\d{3}\.?\d{3}/\d{4}-?\d{2}\b", "CNPJ"),
        (r"sk-[a-zA-Z0-9]{48}", "OpenAI API Key"),
        (r"(password|secret|token|key|api_key|client_secret)\s*[:=]\s*\S+", "Credential"),
    ]
    
    files_to_check = [check_path] if check_path.is_file() else list(check_path.rglob("*"))
    
    found_any = False
    
    for file_path in files_to_check:
        if not file_path.is_file():
            continue
        
        try:
            content = file_path.read_text(errors="ignore")
            
            for pattern, label in patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                if matches:
                    console.print(f"[yellow]⚠ {file_path}[/yellow]: Found {label} - {len(matches)} match(es)")
                    found_any = True
        except Exception:
            pass
    
    if not found_any:
        console.print("[green]No sensitive patterns detected.[/green]")


if __name__ == "__main__":
    from rich.console import Console
    console = Console()
    app()