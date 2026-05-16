"""
API Contract Tests
==================
Endpoint'lerin OpenAPI schema'sinin degismemesi icin testler.
Bu testler:
1. Tüm endpoint'lerin /api/v2/ prefix'i ile tanimlanmis olmasini
2. Her endpoint'in bir response_model tanimi olmasini (DELETE 204 haric)
3. Schema yapilarinin bozulmamamasini
4. Yeni endpoint eklenmesini yakalar (snapshot test)

Calistirma:
    cd /mnt/agents/output/app/backend
    pytest tests/contract/test_api_contract.py -v
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

# Proje root
BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BACKEND_DIR))

os.environ.setdefault("DATABASE_URL", "postgresql://localhost:5432/test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key")

from app.main import app

# Snapshot dosyasi
SNAPSHOT_FILE = Path(__file__).parent / "openapi-snapshot.json"


class TestApiVersioning:
    """Tüm endpoint'ler /api/v2/ prefix'i ile tanimlanmali."""

    def test_all_routes_have_v2_prefix(self):
        """Tüm router path'leri /api/v2/ ile baslamali."""
        openapi = app.openapi()
        paths = openapi.get("paths", {})

        non_compliant: list[str] = []
        for path in paths:
            if path.startswith("/api/docs") or path.startswith("/api/redoc"):
                continue
            if path.startswith("/api/openapi"):
                continue
            if not path.startswith("/api/v2/"):
                non_compliant.append(path)

        assert not non_compliant, (
            f"Asagidaki endpoint'ler /api/v2/ prefix'i ile baslamiyor:\n"
            + "\n".join(f"  - {p}" for p in non_compliant)
        )

    def test_no_duplicate_paths(self):
        """Ayni path+method kombinasyonu tekrar etmemeli."""
        openapi = app.openapi()
        paths = openapi.get("paths", {})

        seen: dict[str, list[str]] = {}
        for path, methods in paths.items():
            for method in methods:
                if method == "parameters":
                    continue
                key = f"{method.upper()} {path}"
                seen.setdefault(key, []).append(path)

        duplicates = {k: v for k, v in seen.items() if len(v) > 1}
        assert not duplicates, (
            f"Duplicate endpoint'ler bulundu:\n"
            + "\n".join(f"  - {k}" for k in duplicates)
        )


class TestResponseModels:
    """Endpoint'lerin response_model tanimlari."""

    def test_get_endpoints_have_response_model(self):
        """GET endpoint'leri response_model ile tanimlanmali."""
        openapi = app.openapi()
        paths = openapi.get("paths", {})

        missing: list[str] = []
        for path, methods in paths.items():
            if "get" not in methods:
                continue
            get_op = methods["get"]
            responses = get_op.get("responses", {})
            has_200_schema = any(
                "content" in r or "$ref" in r.get("description", "")
                for code, r in responses.items()
                if code.startswith("2")
            )
            if not has_200_schema and not responses:
                missing.append(f"GET {path}")

        # Health check endpoint'leri muaf
        missing = [m for m in missing if "/health" not in m]

        assert not missing, (
            f"GET endpoint'lerinde response tanimi eksik:\n"
            + "\n".join(f"  - {m}" for m in missing)
        )

    def test_post_endpoints_have_response_model(self):
        """POST endpoint'leri (201/200) response_model ile tanimlanmali."""
        openapi = app.openapi()
        paths = openapi.get("paths", {})

        missing: list[str] = []
        for path, methods in paths.items():
            if "post" not in methods:
                continue
            post_op = methods["post"]
            responses = post_op.get("responses", {})
            has_success = any(
                code.startswith("2") for code in responses
            )
            if not has_success:
                missing.append(f"POST {path}")

        assert not missing, (
            f"POST endpoint'lerinde response tanimi eksik:\n"
            + "\n".join(f"  - {m}" for m in missing)
        )

    def test_delete_endpoints_return_204(self):
        """DELETE endpoint'leri 204 NO_CONTENT donmeli."""
        openapi = app.openapi()
        paths = openapi.get("paths", {})

        non_204: list[str] = []
        for path, methods in paths.items():
            if "delete" not in methods:
                continue
            delete_op = methods["delete"]
            responses = delete_op.get("responses", {})
            if responses and "204" not in responses:
                non_204.append(f"DELETE {path} -> {list(responses.keys())}")

        assert not non_204, (
            f"DELETE endpoint'leri 204 donmuyor:\n"
            + "\n".join(f"  - {m}" for m in non_204)
        )


class TestSchemaConsistency:
    """Schema yapisinin tutarliligi."""

    def test_openapi_has_components_schemas(self):
        """OpenAPI spec'te components.schemas bolumu olmali."""
        openapi = app.openapi()
        assert "components" in openapi
        assert "schemas" in openapi["components"]
        assert len(openapi["components"]["schemas"]) > 0

    def test_schema_names_are_valid(self):
        """Schema isimleri gecerli olmali (bosluk, ozel karakter icermemeli)."""
        openapi = app.openapi()
        schemas = openapi.get("components", {}).get("schemas", {})

        import re
        invalid: list[str] = []
        for name in schemas:
            if not re.match(r'^[A-Za-z][A-Za-z0-9_]*$', name):
                invalid.append(name)

        assert not invalid, (
            f"Gecersiz schema isimleri:\n"
            + "\n".join(f"  - {n}" for n in invalid)
        )

    def test_all_schemas_have_type(self):
        """Her schema 'type' veya 'properties' icermeli."""
        openapi = app.openapi()
        schemas = openapi.get("components", {}).get("schemas", {})

        incomplete: list[str] = []
        for name, schema in schemas.items():
            if "type" not in schema and "properties" not in schema and "enum" not in schema and "allOf" not in schema:
                incomplete.append(name)

        assert not incomplete, (
            f"Tip/ozellik tanimi eksik schema'lar:\n"
            + "\n".join(f"  - {n}" for n in incomplete)
        )

    def test_no_circular_schema_refs(self):
        """Dairesel $ref olmamali."""
        openapi = app.openapi()
        schemas = openapi.get("components", {}).get("schemas", {})

        def check_refs(schema_name: str, visited: set[str]) -> list[str]:
            errors: list[str] = []
            if schema_name in visited:
                return [f"Circular ref: {' -> '.join(visited)} -> {schema_name}"]
            visited = visited | {schema_name}
            schema = schemas.get(schema_name, {})

            if "$ref" in schema:
                ref = schema["$ref"].split("/")[-1]
                errors.extend(check_refs(ref, visited))
            if "properties" in schema:
                for prop in schema["properties"].values():
                    if "$ref" in prop:
                        ref = prop["$ref"].split("/")[-1]
                        errors.extend(check_refs(ref, visited))
                    if "items" in prop and "$ref" in prop["items"]:
                        ref = prop["items"]["$ref"].split("/")[-1]
                        errors.extend(check_refs(ref, visited))
            if "allOf" in schema:
                for item in schema["allOf"]:
                    if "$ref" in item:
                        ref = item["$ref"].split("/")[-1]
                        errors.extend(check_refs(ref, visited))
            if "items" in schema and "$ref" in schema["items"]:
                ref = schema["items"]["$ref"].split("/")[-1]
                errors.extend(check_refs(ref, visited))

            return errors

        all_errors: list[str] = []
        for name in schemas:
            all_errors.extend(check_refs(name, set()))

        assert not all_errors, (
            f"Dairesel schema referanslari:\n"
            + "\n".join(f"  - {e}" for e in all_errors)
        )


class TestEndpointStructure:
    """Endpoint yapisinin kalite kontrolu."""

    def test_all_endpoints_have_operation_id(self):
        """Her endpoint benzersiz operationId'ye sahip olmali."""
        openapi = app.openapi()
        paths = openapi.get("paths", {})

        missing: list[str] = []
        seen_ids: dict[str, str] = {}
        duplicates: list[str] = []

        for path, methods in paths.items():
            for method, operation in methods.items():
                if method == "parameters":
                    continue
                op_id = operation.get("operationId", "")
                if not op_id:
                    missing.append(f"{method.upper()} {path}")
                elif op_id in seen_ids:
                    duplicates.append(
                        f"{op_id}: {seen_ids[op_id]} ve {method.upper()} {path}"
                    )
                else:
                    seen_ids[op_id] = f"{method.upper()} {path}"

        assert not missing, (
            f"operationId eksik endpoint'ler:\n"
            + "\n".join(f"  - {m}" for m in missing)
        )
        assert not duplicates, (
            f"Tekrar eden operationId'ler:\n"
            + "\n".join(f"  - {d}" for d in duplicates)
        )

    def test_all_endpoints_have_summary(self):
        """Her endpoint ozet (summary) icermeli."""
        openapi = app.openapi()
        paths = openapi.get("paths", {})

        missing: list[str] = []
        for path, methods in paths.items():
            for method, operation in methods.items():
                if method == "parameters":
                    continue
                if not operation.get("summary", "").strip():
                    missing.append(f"{method.upper()} {path}")

        assert not missing, (
            f"Summary eksik endpoint'ler:\n"
            + "\n".join(f"  - {m}" for m in missing)
        )

    def test_http_methods_are_valid(self):
        """Sadece gecerli HTTP method'lar kullanilmali."""
        valid_methods = {"get", "post", "put", "patch", "delete", "head", "options", "parameters"}
        openapi = app.openapi()
        paths = openapi.get("paths", {})

        invalid: list[str] = []
        for path, methods in paths.items():
            for method in methods:
                if method.lower() not in valid_methods:
                    invalid.append(f"{method.upper()} {path}")

        assert not invalid, (
            f"Gecersiz HTTP method:\n"
            + "\n".join(f"  - {m}" for m in invalid)
        )

    def test_endpoint_count_within_bounds(self):
        """Endpoint sayisi makul sinirlar icinde olmali."""
        openapi = app.openapi()
        paths = openapi.get("paths", {})

        total = sum(
            1 for methods in paths.values() for m in methods if m != "parameters"
        )
        assert total >= 10, f"Cok az endpoint: {total} (min 10)"
        assert total <= 500, f"Cok fazla endpoint: {total} (max 500)"


class TestSnapshot:
    """OpenAPI snapshot testleri - schema degisikliklerini yakala."""

    @pytest.mark.skipif(
        not SNAPSHOT_FILE.exists(),
        reason="Snapshot dosyasi yok, olusturmak icin --snapshot flag'i kullanin",
    )
    def test_openapi_schema_matches_snapshot(self):
        """Mevcut OpenAPI schema snapshot ile eslesmeli."""
        openapi = app.openapi()
        current_paths = set(openapi.get("paths", {}).keys())

        with open(SNAPSHOT_FILE, "r", encoding="utf-8") as f:
            snapshot = json.load(f)
        snapshot_paths = set(snapshot.get("paths", {}).keys())

        # Yeni eklenen endpoint'ler
        added = current_paths - snapshot_paths
        # Silinen endpoint'ler
        removed = snapshot_paths - current_paths

        if added:
            pytest.fail(f"Yeni endpoint'ler eklendi:\n" + "\n".join(f"  + {p}" for p in added))
        if removed:
            pytest.fail(f"Endpoint'ler silindi:\n" + "\n".join(f"  - {p}" for p in removed))

    @pytest.mark.skipif(
        not SNAPSHOT_FILE.exists(),
        reason="Snapshot dosyasi yok",
    )
    def test_schema_count_matches_snapshot(self):
        """Schema sayisi snapshot ile eslesmeli."""
        openapi = app.openapi()
        current_schemas = set(openapi.get("components", {}).get("schemas", {}).keys())

        with open(SNAPSHOT_FILE, "r", encoding="utf-8") as f:
            snapshot = json.load(f)
        snapshot_schemas = set(
            snapshot.get("components", {}).get("schemas", {}).keys()
        )

        added = current_schemas - snapshot_schemas
        removed = snapshot_schemas - current_schemas

        if added:
            pytest.fail(f"Yeni schema'lar:\n" + "\n".join(f"  + {s}" for s in added))
        if removed:
            pytest.fail(f"Silinen schema'lar:\n" + "\n".join(f"  - {s}" for s in removed))


def generate_snapshot():
    """Snapshot dosyasi olustur."""
    openapi = app.openapi()
    with open(SNAPSHOT_FILE, "w", encoding="utf-8") as f:
        json.dump(openapi, f, indent=2, default=str, ensure_ascii=False)
    print(f"Snapshot olusturuldu: {SNAPSHOT_FILE}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="API Contract Tests")
    parser.add_argument("--snapshot", action="store_true", help="Snapshot olustur")
    args = parser.parse_args()

    if args.snapshot:
        generate_snapshot()
    else:
        pytest.main([__file__, "-v"])
