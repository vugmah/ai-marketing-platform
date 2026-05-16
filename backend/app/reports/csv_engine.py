"""
CSV export engine using pandas.

Generates clean CSV files with optional headers, custom delimiters,
encoding options, and BOM for Excel compatibility.
"""

import os
from datetime import datetime
from io import BytesIO, StringIO
from typing import Any, Dict, List, Optional

import pandas as pd

from app.reports.constants import DEFAULT_TEMPLATE_CONFIG


class CSVReportEngine:
    """
    CSV report generator using pandas.

    Supports custom delimiters, encoding, BOM for Excel,
and DataFrame-based data transformation.
    """

    def __init__(self, template_config: Optional[Dict[str, Any]] = None):
        self.config = {**DEFAULT_TEMPLATE_CONFIG, **(template_config or {})}

    def generate(
        self,
        output_path: str,
        title: str,
        headers: List[str],
        rows: List[List[Any]],
        delimiter: str = ",",
        include_header: bool = True,
        encoding: str = "utf-8-sig",
        index: bool = False,
    ) -> str:
        """
        Generate a CSV file from tabular data.

        Args:
            output_path: File path for output.
            title: Report title (stored as metadata comment).
            headers: Column names.
            rows: Data rows.
            delimiter: Field delimiter (default: comma).
            include_header: Whether to include column headers.
            encoding: File encoding (utf-8-sig for Excel BOM).
            index: Include row index.

        Returns:
            output_path on success.
        """
        df = pd.DataFrame(rows, columns=headers if include_header else None)

        df.to_csv(
            output_path,
            index=index,
            header=include_header,
            sep=delimiter,
            encoding=encoding,
        )

        return output_path

    def generate_from_dicts(
        self,
        output_path: str,
        records: List[Dict[str, Any]],
        delimiter: str = ",",
        encoding: str = "utf-8-sig",
        index: bool = False,
    ) -> str:
        """
        Generate CSV from list of dictionaries.

        Args:
            output_path: File path for output.
            records: List of dict records.
            delimiter: Field delimiter.
            encoding: File encoding.
            index: Include row index.

        Returns:
            output_path on success.
        """
        df = pd.DataFrame.from_records(records)
        df.to_csv(
            output_path,
            index=index,
            sep=delimiter,
            encoding=encoding,
        )
        return output_path

    def generate_from_buffer(
        self,
        title: str = "Report",
        headers: Optional[List[str]] = None,
        rows: Optional[List[List[Any]]] = None,
        records: Optional[List[Dict[str, Any]]] = None,
        delimiter: str = ",",
        include_header: bool = True,
        encoding: str = "utf-8-sig",
        index: bool = False,
    ) -> BytesIO:
        """
        Generate CSV into a BytesIO buffer.

        Args:
            title: Report title.
            headers: Column names (for row-based data).
            rows: Data rows.
            records: Alternative dict-based data.
            delimiter: Field delimiter.
            include_header: Include column headers.
            encoding: File encoding.
            index: Include row index.

        Returns:
            BytesIO buffer containing CSV data.
        """
        buffer = BytesIO()

        if records is not None:
            df = pd.DataFrame.from_records(records)
        elif headers is not None and rows is not None:
            df = pd.DataFrame(rows, columns=headers if include_header else None)
        else:
            df = pd.DataFrame()

        # Write to StringIO first, then encode
        string_buffer = StringIO()
        df.to_csv(
            string_buffer,
            index=index,
            header=include_header,
            sep=delimiter,
        )
        buffer.write(string_buffer.getvalue().encode(encoding))
        buffer.seek(0)
        return buffer

    def generate_multi_sheet_csv(
        self,
        output_path: str,
        sheets: List[Dict[str, Any]],
        delimiter: str = ",",
        encoding: str = "utf-8-sig",
    ) -> str:
        """
        Generate a combined CSV with multiple sections (sheets as separators).

        Args:
            output_path: File path for output.
            sheets: List of sheet definitions [{"name": str, "headers": [...], "rows": [...]}].
            delimiter: Field delimiter.
            encoding: File encoding.

        Returns:
            output_path on success.
        """
        with open(output_path, "w", encoding=encoding, newline="") as f:
            for i, sheet in enumerate(sheets):
                # Section separator
                if i > 0:
                    f.write(f"\n{'=' * 40}\n")

                # Sheet name as section header
                f.write(f"# {sheet.get('name', f'Sheet {i+1}')}\n")

                df = pd.DataFrame(
                    sheet.get("rows", []),
                    columns=sheet.get("headers", []),
                )
                df.to_csv(f, index=False, sep=delimiter)

        return output_path
