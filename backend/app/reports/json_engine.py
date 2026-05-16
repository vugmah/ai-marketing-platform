"""
JSON export engine.

Generates structured JSON output with optional pretty-printing,
metadata wrapping, and streaming support for large datasets.
"""

import json
import os
from datetime import datetime
from io import BytesIO
from typing import Any, Dict, List, Optional

from app.reports.constants import DEFAULT_TEMPLATE_CONFIG


class JSONReportEngine:
    """
    JSON report generator with metadata wrapping and formatting.

    Supports pretty-printing, metadata enrichment, streaming,
    and both row-based and record-based output structures.
    """

    def __init__(self, template_config: Optional[Dict[str, Any]] = None):
        self.config = {**DEFAULT_TEMPLATE_CONFIG, **(template_config or {})}

    def generate(
        self,
        output_path: str,
        title: str,
        headers: Optional[List[str]] = None,
        rows: Optional[List[List[Any]]] = None,
        records: Optional[List[Dict[str, Any]]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        indent: int = 2,
        include_metadata: bool = True,
    ) -> str:
        """
        Generate a JSON report file.

        Args:
            output_path: File path for output.
            title: Report title.
            headers: Column headers (for array-of-arrays format).
            rows: Data as array of arrays.
            records: Data as array of objects (alternative to headers+rows).
            metadata: Additional metadata dict.
            indent: Pretty-print indentation.
            include_metadata: Wrap output with metadata envelope.

        Returns:
            output_path on success.
        """
        data = self._build_payload(
            title=title,
            headers=headers,
            rows=rows,
            records=records,
            metadata=metadata,
            include_metadata=include_metadata,
        )

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=indent, default=str)

        return output_path

    def generate_from_buffer(
        self,
        title: str = "Report",
        headers: Optional[List[str]] = None,
        rows: Optional[List[List[Any]]] = None,
        records: Optional[List[Dict[str, Any]]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        indent: int = 2,
        include_metadata: bool = True,
    ) -> BytesIO:
        """
        Generate JSON into a BytesIO buffer.

        Returns:
            BytesIO buffer containing JSON data.
        """
        buffer = BytesIO()

        data = self._build_payload(
            title=title,
            headers=headers,
            rows=rows,
            records=records,
            metadata=metadata,
            include_metadata=include_metadata,
        )

        json_str = json.dumps(data, ensure_ascii=False, indent=indent, default=str)
        buffer.write(json_str.encode("utf-8"))
        buffer.seek(0)
        return buffer

    def generate_ndjson(
        self,
        output_path: str,
        records: List[Dict[str, Any]],
    ) -> str:
        """
        Generate Newline-Delimited JSON (NDJSON/JSONL).

        Each line is a separate JSON object - ideal for streaming.

        Args:
            output_path: File path for output.
            records: List of dict records.

        Returns:
            output_path on success.
        """
        with open(output_path, "w", encoding="utf-8") as f:
            for record in records:
                f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")

        return output_path

    def generate_ndjson_from_buffer(
        self,
        records: List[Dict[str, Any]],
    ) -> BytesIO:
        """Generate NDJSON into a BytesIO buffer."""
        buffer = BytesIO()
        for record in records:
            line = json.dumps(record, ensure_ascii=False, default=str) + "\n"
            buffer.write(line.encode("utf-8"))
        buffer.seek(0)
        return buffer

    def _build_payload(
        self,
        title: str,
        headers: Optional[List[str]] = None,
        rows: Optional[List[List[Any]]] = None,
        records: Optional[List[Dict[str, Any]]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        include_metadata: bool = True,
    ) -> Dict[str, Any]:
        """Build the JSON payload structure."""

        # Build data section
        if records is not None:
            data = records
            data_format = "records"
        elif headers is not None and rows is not None:
            data = {
                "headers": headers,
                "rows": rows,
            }
            data_format = "array"
        else:
            data = []
            data_format = "records"

        if not include_metadata:
            return data if isinstance(data, list) else data

        payload: Dict[str, Any] = {
            "meta": {
                "title": title,
                "generated_at": datetime.utcnow().isoformat() + "Z",
                "format": data_format,
                "version": "1.0",
            },
            "data": data,
        }

        if metadata:
            payload["meta"].update(metadata)

        return payload
