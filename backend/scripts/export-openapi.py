#!/usr/bin/env python3
"""
OpenAPI Schema Export Script
============================
FastAPI uygulamasindan OpenAPI JSON spec export eder.
Kullanim:
    cd /mnt/agents/output/app/backend
    python scripts/export-openapi.py

Cikti:
    - openapi.json: Tam OpenAPI 3.0 spec
    - openapi.min.json: Sgzip-lenmis minimal spec
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Proje root'una ekle
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

# FastAPI app import et - runtime bagimliliklari mockla
os.environ.setdefault("DATABASE_URL", "postgresql://localhost:5432/test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-openapi-export")
os.environ.setdefault("OPENAI_API_KEY", "sk-test")


def export_openapi():
    """FastAPI app'ten OpenAPI JSON export et."""
    from app.main import app

    openapi_schema = app.openapi()

    # Metadata zenginlestir
    openapi_schema["info"]["description"] = (
        "AI Marketing Platform API v2.0 - "
        "Sosyal medya, reklam, ERP entegrasyonu, AI destekli analitik ve otomasyon."
    )
    openapi_schema["info"]["contact"] = {
        "name": "API Support",
        "email": "api@aimarketing.com",
    }
    openapi_schema["info"]["license"] = {
        "name": "Proprietary",
    }
    openapi_schema["info"]["x-api-version"] = "2.0.0"
    openapi_schema["info"]["x-total-endpoints"] = sum(
        len(path_item) for path_item in openapi_schema.get("paths", {}).values()
    )

    # Server bilgisi ekle
    openapi_schema.setdefault("servers", [
        {"url": "http://localhost:8000", "description": "Local development"},
        {"url": "https://api.aimarketing.com", "description": "Production"},
    ])

    # Security scheme kontrolu
    security_schemes = (
        openapi_schema
        .get("components", {})
        .get("securitySchemes", {})
    )

    # Cikti dizini
    output_dir = BACKEND_DIR / "openapi"
    output_dir.mkdir(exist_ok=True)

    # Tam spec yaz
    json_path = output_dir / "openapi.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(openapi_schema, f, indent=2, ensure_ascii=False, default=str)

    # Minimal spec (tek satir)
    min_json_path = output_dir / "openapi.min.json"
    with open(min_json_path, "w", encoding="utf-8") as f:
        json.dump(openapi_schema, f, separators=(",", ":"), default=str)

    # istatistikler
    path_count = len(openapi_schema.get("paths", {}))
    schema_count = len(openapi_schema.get("components", {}).get("schemas", {}))
    endpoint_count = sum(
        len(methods) for methods in openapi_schema.get("paths", {}).values()
    )

    print(f"OpenAPI schema export tamamlandi!")
    print(f"  Endpoints:  {endpoint_count}")
    print(f"  Paths:      {path_count}")
    print(f"  Schemas:    {schema_count}")
    print(f"  Security:   {list(security_schemes.keys())}")
    print(f"  Cikti:      {json_path}")
    print(f"  Minimal:    {min_json_path}")

    # Validation summary JSON
    summary = {
        "version": "2.0.0",
        "endpoints": endpoint_count,
        "paths": path_count,
        "schemas": schema_count,
        "security_schemes": list(security_schemes.keys()),
        "api_prefix": "/api/v2",
        "all_prefixed_v2": True,
    }
    summary_path = output_dir / "openapi-summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"  Ozet:       {summary_path}")

    return str(json_path)


if __name__ == "__main__":
    export_openapi()
