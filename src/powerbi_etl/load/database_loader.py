"""
Database loader for PostgreSQL and other SQL databases.
"""

import pandas as pd
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.engine import Engine
from typing import Dict, List, Optional, Any
from pathlib import Path
import structlog
from .base import BaseLoader, LoadResult

logger = structlog.get_logger(__name__)


class DatabaseLoader(BaseLoader):
    """
    Load dataframes to PostgreSQL/SQL databases.
    Supports upsert (merge) operations and schema management.
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.connection_string = config.get("connection_string", "")
        self.host = config.get("host", "localhost")
        self.port = config.get("port", 5432)
        self.username = config.get("username", "etl_user")
        self.password = config.get("password", "")
        self.database = config.get("database", "powerbi_etl")
        self.schema = config.get("schema", "staging")
        self.table_name = config.get("table_name", "etl_data")
        self.if_exists = config.get("if_exists", "append")  # fail, replace, append
        self.chunk_size = config.get("chunk_size", 10000)
        self.create_schema = config.get("create_schema", True)
        self.primary_key = config.get("primary_key", None)
        self._engine: Optional[Engine] = None

    def _get_connection_string(self) -> str:
        """Build connection string from components."""
        if self.connection_string:
            return self.connection_string
        return f"postgresql://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"

    def _get_engine(self) -> Engine:
        """Get or create SQLAlchemy engine."""
        if self._engine is None:
            self._engine = create_engine(
                self._get_connection_string(),
                pool_size=5,
                max_overflow=10,
                pool_pre_ping=True,
            )
        return self._engine

    def test_connection(self) -> bool:
        """Test database connectivity."""
        try:
            engine = self._get_engine()
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception as e:
            self.logger.error("Database connection test failed", error=str(e))
            return False

    def load(self, dataframe: "pd.DataFrame") -> LoadResult:
        """Load dataframe to database table."""
        try:
            engine = self._get_engine()
            
            # Create schema if needed
            if self.create_schema:
                with engine.connect() as conn:
                    conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {self.schema}"))
                    conn.commit()
            
            # Load data
            records_loaded = dataframe.to_sql(
                name=self.table_name,
                con=engine,
                schema=self.schema,
                if_exists=self.if_exists,
                index=False,
                chunksize=self.chunk_size,
                method="multi",
            )
            
            # Add primary key if specified
            if self.primary_key and self.if_exists in ("replace", "fail"):
                self._add_primary_key(engine)
            
            self.logger.info(
                "Data loaded to database",
                table=f"{self.schema}.{self.table_name}",
                records=records_loaded,
            )
            
            return self._create_result(
                success=True,
                records_loaded=records_loaded,
                metadata={
                    "table": f"{self.schema}.{self.table_name}",
                    "schema": self.schema,
                    "records": records_loaded,
                },
            )
            
        except Exception as e:
            self.logger.error("Database load failed", error=str(e))
            return self._create_result(success=False, errors=[str(e)])

    def _add_primary_key(self, engine: Engine) -> None:
        """Add primary key constraint to table."""
        try:
            with engine.connect() as conn:
                # Check if PK already exists
                inspector = inspect(engine)
                pk_constraint = inspector.get_pk_constraint(self.table_name, schema=self.schema)
                if not pk_constraint["constrained_columns"]:
                    conn.execute(text(
                        f'ALTER TABLE {self.schema}."{self.table_name}" '
                        f'ADD PRIMARY KEY ("{self.primary_key}")'
                    ))
                    conn.commit()
                    self.logger.info("Primary key added", column=self.primary_key)
        except Exception as e:
            self.logger.warning("Could not add primary key", error=str(e))

    def execute_query(self, query: str, params: Dict = None) -> List[Dict]:
        """Execute arbitrary query and return results."""
        try:
            engine = self._get_engine()
            with engine.connect() as conn:
                result = conn.execute(text(query), params or {})
                return [dict(row._mapping) for row in result]
        except Exception as e:
            self.logger.error("Query execution failed", error=str(e))
            return []

    def get_table_info(self) -> Dict[str, Any]:
        """Get table metadata."""
        try:
            engine = self._get_engine()
            inspector = inspect(engine)
            columns = inspector.get_columns(self.table_name, schema=self.schema)
            pk = inspector.get_pk_constraint(self.table_name, schema=self.schema)
            indexes = inspector.get_indexes(self.table_name, schema=self.schema)
            
            return {
                "table": self.table_name,
                "schema": self.schema,
                "columns": columns,
                "primary_key": pk,
                "indexes": indexes,
            }
        except Exception as e:
            self.logger.error("Failed to get table info", error=str(e))
            return {}


class UpsertDatabaseLoader(DatabaseLoader):
    """
    Database loader with upsert (merge) capability.
    Uses ON CONFLICT DO UPDATE for PostgreSQL.
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.conflict_columns = config.get("conflict_columns", [])
        self.update_columns = config.get("update_columns", [])

    def load(self, dataframe: "pd.DataFrame") -> LoadResult:
        """Load with upsert logic."""
        if not self.conflict_columns:
            self.logger.warning("No conflict columns specified, falling back to append")
            return super().load(dataframe)

        try:
            engine = self._get_engine()
            
            if self.create_schema:
                with engine.connect() as conn:
                    conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {self.schema}"))
                    conn.commit()
            
            # Create temp table
            temp_table = f"temp_{self.table_name}_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}"
            
            # Load to temp table
            dataframe.to_sql(
                name=temp_table,
                con=engine,
                schema=self.schema,
                if_exists="replace",
                index=False,
                chunksize=self.chunk_size,
            )
            
            # Build upsert query
            all_columns = list(dataframe.columns)
            update_cols = self.update_columns or [c for c in all_columns if c not in self.conflict_columns]
            
            conflict_cols_str = ", ".join(f'"{c}"' for c in self.conflict_columns)
            update_cols_str = ", ".join(f'"{c}" = EXCLUDED."{c}"' for c in update_cols)
            all_cols_str = ", ".join(f'"{c}"' for c in all_columns)
            
            upsert_query = f'''
                INSERT INTO {self.schema}."{self.table_name}" ({all_cols_str})
                SELECT {all_cols_str} FROM {self.schema}."{temp_table}"
                ON CONFLICT ({conflict_cols_str}) DO UPDATE SET
                {update_cols_str}
            '''
            
            with engine.connect() as conn:
                result = conn.execute(text(upsert_query))
                conn.commit()
                records_affected = result.rowcount
            
            # Drop temp table
            with engine.connect() as conn:
                conn.execute(text(f'DROP TABLE IF EXISTS {self.schema}."{temp_table}"'))
                conn.commit()
            
            self.logger.info("Upsert completed", table=f"{self.schema}.{self.table_name}", records=records_affected)
            
            return self._create_result(
                success=True,
                records_loaded=records_affected,
                metadata={
                    "table": f"{self.schema}.{self.table_name}",
                    "operation": "upsert",
                    "conflict_columns": self.conflict_columns,
                },
            )
            
        except Exception as e:
            self.logger.error("Upsert failed", error=str(e))
            return self._create_result(success=False, errors=[str(e)])