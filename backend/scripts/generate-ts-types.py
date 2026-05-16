#!/usr/bin/env python3
"""
TypeScript Type Generator
=========================
OpenAPI schema'dan frontend TypeScript tipleri uretir.

Kullanim:
    cd /mnt/agents/output/app/backend
    python scripts/export-openapi.py  # once OpenAPI JSON uret
    python scripts/generate-ts-types.py  # sonra TypeScript tipleri uret

Cikti:
    - frontend/src/types/api.types.ts (tam tipler)
    - frontend/src/types/api.constants.ts (enum ve sabitler)
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any

BACKEND_DIR = Path(__file__).resolve().parent.parent
FRONTEND_TYPES_DIR = BACKEND_DIR.parent / "frontend" / "src" / "types"

# OpenAPI type -> TypeScript type mapping
TYPE_MAP: dict[str, str] = {
    "string": "string",
    "integer": "number",
    "number": "number",
    "boolean": "boolean",
    "array": "Array<unknown>",
    "object": "Record<string, unknown>",
    "null": "null",
}

FORMAT_MAP: dict[str, str] = {
    "date-time": "string /* ISO datetime */",
    "date": "string /* ISO date */",
    "uuid": "string /* UUID */",
    "email": "string /* email */",
    "uri": "string /* URL */",
    "password": "string /* hashed */",
}


def to_camel_case(snake_str: str) -> str:
    """snake_case -> camelCase donusumu."""
    components = snake_str.split("_")
    return components[0] + "".join(x.capitalize() for x in components[1:])


def sanitize_name(name: str) -> str:
    """TypeScript icin gecerli tip adi uret."""
    name = re.sub(r'[^a-zA-Z0-9_]', '_', name)
    if name[0].isdigit():
        name = f"_{name}"
    return name


def openapi_type_to_ts(
    prop: dict[str, Any],
    schema_name: str = "",
    required: bool = False,
) -> str:
    """OpenAPI property tanimini TypeScript tipine cevir."""
    nullable_marker = "" if required else "?"

    if "$ref" in prop:
        ref = prop["$ref"].split("/")[-1]
        base = ref
        if prop.get("nullable"):
            base = f"{base} | null"
        return base

    prop_type = prop.get("type", "unknown")
    prop_format = prop.get("format", "")

    if prop_format and prop_format in FORMAT_MAP:
        ts_type = FORMAT_MAP[prop_format]
    elif prop_type in TYPE_MAP:
        ts_type = TYPE_MAP[prop_type]
    else:
        ts_type = "unknown"

    # Array eleman tipi
    if prop_type == "array" and "items" in prop:
        items = prop["items"]
        if "$ref" in items:
            item_type = items["$ref"].split("/")[-1]
        elif "type" in items:
            item_type = TYPE_MAP.get(items["type"], "unknown")
            if items.get("format") in FORMAT_MAP:
                item_type = FORMAT_MAP[items["format"]]
        else:
            item_type = "unknown"
        ts_type = f"Array<{item_type}>"

    # Additional properties (dict/map)
    if prop_type == "object" and "additionalProperties" in prop:
        add_props = prop["additionalProperties"]
        if "$ref" in add_props:
            val_type = add_props["$ref"].split("/")[-1]
        elif "type" in add_props:
            val_type = TYPE_MAP.get(add_props["type"], "unknown")
        else:
            val_type = "unknown"
        ts_type = f"Record<string, {val_type}>"

    # Enum
    if "enum" in prop:
        enum_values = [json.dumps(v) for v in prop["enum"]]
        ts_type = " | ".join(enum_values)

    # AnyOf / OneOf
    if "anyOf" in prop or "oneOf" in prop:
        variants = prop.get("anyOf") or prop.get("oneOf") or []
        ts_parts = []
        for variant in variants:
            if "$ref" in variant:
                ts_parts.append(variant["$ref"].split("/")[-1])
            elif "type" in variant:
                ts_parts.append(TYPE_MAP.get(variant["type"], "unknown"))
        if ts_parts:
            ts_type = " | ".join(ts_parts)

    if prop.get("nullable") and not ts_type.endswith("| null"):
        ts_type = f"{ts_type} | null"

    return ts_type


def generate_ts_interface(
    name: str,
    schema: dict[str, Any],
    indent: int = 0,
) -> str:
    """OpenAPI schema objesinden TypeScript interface uret."""
    lines: list[str] = []
    indent_str = "  " * indent

    schema_type = schema.get("type", "object")

    if schema_type == "object":
        lines.append(f"{indent_str}export interface {name} {{")

        properties = schema.get("properties", {})
        required = set(schema.get("required", []))

        for prop_name in sorted(properties.keys()):
            prop = properties[prop_name]
            is_required = prop_name in required
            ts_prop_type = openapi_type_to_ts(prop, name, is_required)
            optional = "" if is_required else "?"
            description = prop.get("description", "")
            desc_comment = f" // {description}" if description else ""
            lines.append(
                f"{indent_str}  {prop_name}{optional}: {ts_prop_type};{desc_comment}"
            )

        # additionalProperties
        if "additionalProperties" in schema and not properties:
            add_props = schema["additionalProperties"]
            if isinstance(add_props, dict):
                val_type = openapi_type_to_ts(add_props, name, True)
                lines.append(f"{indent_str}  [key: string]: {val_type};")
            else:
                lines.append(f"{indent_str}  [key: string]: unknown;")

        lines.append(f"{indent_str}}}")

    elif schema_type == "string" and "enum" in schema:
        enum_name = name
        enum_values = [json.dumps(v) for v in schema["enum"]]
        lines.append(f"{indent_str}export type {enum_name} = " + " | ".join(enum_values) + ";")

    return "\n".join(lines)


def generate_endpoint_types(openapi: dict[str, Any]) -> str:
    """Endpoint tanimlarindan TypeScript API client tipleri uret."""
    lines: list[str] = []
    lines.append("")
    lines.append("// ============================================")
    lines.append("// API Endpoint Type Definitions")
    lines.append("// ============================================")
    lines.append("")

    # HTTP method tipleri
    lines.append("export type HttpMethod = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';")
    lines.append("")

    # Endpoint gruplari
    paths = openapi.get("paths", {})
    endpoint_groups: dict[str, list[dict]] = {}

    for path, methods in sorted(paths.items()):
        for method, operation in methods.items():
            if method == "parameters":
                continue
            # Tag'e gore grupla
            tags = operation.get("tags", ["Uncategorized"])
            group = tags[0] if tags else "Uncategorized"
            endpoint_groups.setdefault(group, []).append({
                "path": path,
                "method": method.upper(),
                "operationId": operation.get("operationId", ""),
                "summary": operation.get("summary", ""),
                "requestBody": operation.get("requestBody"),
                "responses": operation.get("responses", {}),
            })

    # Her grup icin endpoint tipleri
    lines.append("export interface ApiEndpoints {")
    for group, endpoints in sorted(endpoint_groups.items()):
        group_key = to_camel_case(group.lower().replace(" ", "_").replace("&", "and"))
        lines.append(f"  '{group_key}': {{")
        for ep in endpoints:
            path_key = ep["path"].replace("{", "By").replace("}", "").replace("/", "_")
            path_key = re.sub(r'_+', '_', path_key).strip('_')
            path_key = to_camel_case(path_key)
            method = ep["method"]
            lines.append(f"    '{method} {ep['path']}': {{")
            lines.append(f"      method: '{method}';")
            lines.append(f"      path: '{ep['path']}';")
            if ep["summary"]:
                lines.append(f"      summary: '{ep['summary'].replace(chr(39), chr(92)+chr(39))}';")
            lines.append(f"    }};")
        lines.append(f"  }};")
    lines.append("}")
    lines.append("")

    return "\n".join(lines)


def generate_types(openapi_path: str | None = None) -> list[str]:
    """Ana uretim fonksiyonu."""
    if openapi_path is None:
        openapi_path = str(BACKEND_DIR / "openapi" / "openapi.json")

    with open(openapi_path, "r", encoding="utf-8") as f:
        openapi = json.load(f)

    FRONTEND_TYPES_DIR.mkdir(parents=True, exist_ok=True)

    # ============================================
    # 1. Schema tipleri
    # ============================================
    schema_lines: list[str] = []
    schema_lines.append("// ============================================")
    schema_lines.append("// AI Marketing Platform - Auto-generated TypeScript Types")
    schema_lines.append("// Source: OpenAPI 3.0 Schema")
    schema_lines.append("// Generated: Do NOT edit manually")
    schema_lines.append("// ============================================")
    schema_lines.append("")
    schema_lines.append("// ============================================")
    schema_lines.append("// Primitive Type Aliases")
    schema_lines.append("// ============================================")
    schema_lines.append("")
    schema_lines.append("export type UUID = string;")
    schema_lines.append("export type ISODateTime = string;")
    schema_lines.append("export type ISODate = string;")
    schema_lines.append("export type Email = string;")
    schema_lines.append("export type URLString = string;")
    schema_lines.append("")

    schemas = openapi.get("components", {}).get("schemas", {})

    # Enum'lari ayir
    enums: list[tuple[str, dict]] = []
    interfaces: list[tuple[str, dict]] = []
    others: list[tuple[str, dict]] = []

    for name, schema_def in sorted(schemas.items()):
        s_type = schema_def.get("type", "object")
        if s_type == "string" and "enum" in schema_def:
            enums.append((name, schema_def))
        elif s_type == "object" and "properties" in schema_def:
            interfaces.append((name, schema_def))
        else:
            others.append((name, schema_def))

    # Enum'lar
    if enums:
        schema_lines.append("// ============================================")
        schema_lines.append("// Enums")
        schema_lines.append("// ============================================")
        schema_lines.append("")
        for name, schema_def in enums:
            ts = generate_ts_interface(name, schema_def)
            schema_lines.append(ts)
            schema_lines.append("")

    # Interfaceler
    if interfaces:
        schema_lines.append("// ============================================")
        schema_lines.append("// Request / Response Interfaces")
        schema_lines.append("// ============================================")
        schema_lines.append("")
        for name, schema_def in interfaces:
            ts = generate_ts_interface(name, schema_def)
            schema_lines.append(ts)
            schema_lines.append("")

    # Diger tipler
    if others:
        schema_lines.append("// ============================================")
        schema_lines.append("// Other Types")
        schema_lines.append("// ============================================")
        schema_lines.append("")
        for name, schema_def in others:
            s_type = schema_def.get("type", "unknown")
            if s_type == "array" and "items" in schema_def:
                items = schema_def["items"]
                if "$ref" in items:
                    item_type = items["$ref"].split("/")[-1]
                elif "type" in items:
                    item_type = TYPE_MAP.get(items["type"], "unknown")
                else:
                    item_type = "unknown"
                schema_lines.append(f"export type {name} = Array<{item_type}>;")
            else:
                ts_type = TYPE_MAP.get(s_type, "unknown")
                schema_lines.append(f"export type {name} = {ts_type};")
            schema_lines.append("")

    # Endpoint tipleri
    schema_lines.append(generate_endpoint_types(openapi))

    # API Client type
    schema_lines.append("// ============================================")
    schema_lines.append("// API Client Types")
    schema_lines.append("// ============================================")
    schema_lines.append("")
    schema_lines.append("export interface ApiClientConfig {")
    schema_lines.append("  baseURL: string;")
    schema_lines.append("  timeout?: number;")
    schema_lines.append("  headers?: Record<string, string>;")
    schema_lines.append("  withCredentials?: boolean;")
    schema_lines.append("}")
    schema_lines.append("")
    schema_lines.append("export interface ApiResponse<T = unknown> {")
    schema_lines.append("  data: T;")
    schema_lines.append("  status: number;")
    schema_lines.append("  statusText: string;")
    schema_lines.append("  headers: Record<string, string>;")
    schema_lines.append("}")
    schema_lines.append("")
    schema_lines.append("export interface ApiError {")
    schema_lines.append("  detail: string;")
    schema_lines.append("  status_code: number;")
    schema_lines.append("  type?: string;")
    schema_lines.append("}")
    schema_lines.append("")
    schema_lines.append("export type ApiResult<T> =")
    schema_lines.append("  | { success: true; data: T; response: ApiResponse<T> }")
    schema_lines.append("  | { success: false; error: ApiError; response?: ApiResponse<unknown> };")
    schema_lines.append("")

    # Path parameter helper
    schema_lines.append("// ============================================")
    schema_lines.append("// Path Parameter Helpers")
    schema_lines.append("// ============================================")
    schema_lines.append("")
    schema_lines.append("export type PathParams<T extends string> =")
    schema_lines.append("  T extends `${string}{${infer Param}}${infer Rest}`")
    schema_lines.append("    ? { [K in Param]: string } & PathParams<Rest>")
    schema_lines.append("    : {};")
    schema_lines.append("")

    # Write to file
    types_file = FRONTEND_TYPES_DIR / "api.types.ts"
    with open(types_file, "w", encoding="utf-8") as f:
        f.write("\n".join(schema_lines))

    # ============================================
    # 2. Constants (HTTP status, error codes)
    # ============================================
    constants_lines: list[str] = []
    constants_lines.append("// ============================================")
    constants_lines.append("// API Constants")
    constants_lines.append("// ============================================")
    constants_lines.append("")

    # HTTP Status Codes
    constants_lines.append("export const HttpStatus = {")
    constants_lines.append("  OK: 200,")
    constants_lines.append("  CREATED: 201,")
    constants_lines.append("  ACCEPTED: 202,")
    constants_lines.append("  NO_CONTENT: 204,")
    constants_lines.append("  BAD_REQUEST: 400,")
    constants_lines.append("  UNAUTHORIZED: 401,")
    constants_lines.append("  FORBIDDEN: 403,")
    constants_lines.append("  NOT_FOUND: 404,")
    constants_lines.append("  CONFLICT: 409,")
    constants_lines.append("  UNPROCESSABLE: 422,")
    constants_lines.append("  TOO_MANY_REQUESTS: 429,")
    constants_lines.append("  INTERNAL_ERROR: 500,")
    constants_lines.append("  SERVICE_UNAVAILABLE: 503,")
    constants_lines.append("} as const;")
    constants_lines.append("")
    constants_lines.append("export type HttpStatusCode = typeof HttpStatus[keyof typeof HttpStatus];")
    constants_lines.append("")

    # API Version
    constants_lines.append("export const API_VERSION = 'v2';")
    constants_lines.append("export const API_BASE_PATH = '/api/v2';")
    constants_lines.append("")

    # Module paths
    constants_lines.append("export const ApiPaths = {")
    constants_lines.append("  auth: '/api/v2/auth',")
    constants_lines.append("  companies: '/api/v2/companies',")
    constants_lines.append("  branches: '/api/v2/branches',")
    constants_lines.append("  dashboard: '/api/v2/dashboard',")
    constants_lines.append("  analytics: '/api/v2/analytics',")
    constants_lines.append("  notifications: '/api/v2/notifications',")
    constants_lines.append("  erp: '/api/v2/erp',")
    constants_lines.append("  ai: '/api/v2/ai',")
    constants_lines.append("  social: '/api/v2/social',")
    constants_lines.append("  media: '/api/v2/media',")
    constants_lines.append("  events: '/api/v2/events',")
    constants_lines.append("  billing: '/api/v2/billing',")
    constants_lines.append("  audit: '/api/v2/audit',")
    constants_lines.append("  health: '/api/v2/health',")
    constants_lines.append("  ads: '/api/v2/ads',")
    constants_lines.append("  support: '/api/v2/support',")
    constants_lines.append("} as const;")
    constants_lines.append("")
    constants_lines.append("export type ApiModule = keyof typeof ApiPaths;")
    constants_lines.append("")

    # Error types
    constants_lines.append("export const ErrorTypes = {")
    constants_lines.append("  VALIDATION: 'validation_error',")
    constants_lines.append("  AUTHENTICATION: 'authentication_error',")
    constants_lines.append("  AUTHORIZATION: 'authorization_error',")
    constants_lines.append("  NOT_FOUND: 'not_found',")
    constants_lines.append("  CONFLICT: 'conflict',")
    constants_lines.append("  RATE_LIMIT: 'rate_limit',")
    constants_lines.append("  INTERNAL: 'internal_error',")
    constants_lines.append("} as const;")
    constants_lines.append("")

    # Pagination defaults
    constants_lines.append("export const PaginationDefaults = {")
    constants_lines.append("  page: 1,")
    constants_lines.append("  pageSize: 20,")
    constants_lines.append("  maxPageSize: 100,")
    constants_lines.append("} as const;")
    constants_lines.append("")

    constants_file = FRONTEND_TYPES_DIR / "api.constants.ts"
    with open(constants_file, "w", encoding="utf-8") as f:
        f.write("\n".join(constants_lines))

    print(f"TypeScript tipleri uretildi:")
    print(f"  Types:      {types_file}")
    print(f"  Constants:  {constants_file}")
    print(f"  Schemas:    {len(schemas)}")

    return [str(types_file), str(constants_file)]


if __name__ == "__main__":
    generate_types()
