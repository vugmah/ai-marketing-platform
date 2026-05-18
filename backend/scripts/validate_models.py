#!/usr/bin/env python3
"""SQLAlchemy Mapper Validation - Root Cause Analysis.

Tüm relationship'lerin _setup_join_conditions()'unu patch'leyerek
her hatada durmadan TÜM root cause'lari tek seferde bulur.

Kullanim:
    cd backend
    OPENAI_API_KEY="" python scripts/validate_models.py
"""

import importlib
import pkgutil
import sys
import os

# Environment
os.environ.setdefault("ENVIRONMENT", "testing")
os.environ.setdefault("STORAGE_PROVIDER", "disabled")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-128-chars-long-abc1234567890")
os.environ.setdefault("SECRET_KEY", "test-secret-128-chars-long-abc1234567890")
if "OPENAI_API_KEY" not in os.environ:
    os.environ["OPENAI_API_KEY"] = ""

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)


def import_all_models():
    """Tüm model modüllerini import et."""
    packages = [
        "app.ads", "app.ai", "app.auth", "app.followers", "app.social",
        "app.companies", "app.branches", "app.dashboard", "app.analytics",
        "app.billing", "app.reports", "app.support", "app.governance",
        "app.realtime", "app.notifications", "app.media",
        "app.knowledge", "app.audit",
    ]
    errors = []
    imported = []
    for pkg in packages:
        try:
            package = importlib.import_module(pkg)
            if hasattr(package, "__path__"):
                for _, modname, _ in pkgutil.iter_modules(package.__path__):
                    if modname == "models":
                        full = f"{pkg}.models"
                        try:
                            importlib.import_module(full)
                            imported.append(full)
                            print(f"  OK: {full}")
                        except Exception as e:
                            errors.append({"module": full, "type": type(e).__name__, "msg": str(e)[:100]})
                            print(f"  ERR: {full} -> {type(e).__name__}: {str(e)[:80]}")
        except Exception as e:
            errors.append({"module": pkg, "type": type(e).__name__, "msg": str(e)[:80]})
            print(f"  ERR: {pkg} -> {e}")
    return imported, errors


def validate_with_patched_setup():
    """_setup_join_conditions'u patch'le, tüm root cause'lari topla."""
    from sqlalchemy.orm import RelationshipProperty
    
    fk_errors = []
    other_errors = []
    original_setup = RelationshipProperty._setup_join_conditions
    
    def patched_setup(self):
        try:
            original_setup(self)
        except Exception as e:
            err_msg = str(e)
            rel_name = f"{self.parent.class_.__name__}.{self.key}"
            
            if "NoForeignKeysError" in type(e).__name__ or "no foreign keys" in err_msg.lower():
                fk_errors.append({
                    "relationship": rel_name,
                    "target": str(self.argument)[:50] if self.argument else "?",
                    "parent_table": self.parent.persist_selectable.name if hasattr(self.parent.persist_selectable, 'name') else "?",
                    "detail": err_msg[:200],
                })
            else:
                other_errors.append({
                    "relationship": rel_name,
                    "error": type(e).__name__,
                    "detail": err_msg[:200],
                })
    
    RelationshipProperty._setup_join_conditions = patched_setup
    
    try:
        from sqlalchemy.orm import configure_mappers
        configure_mappers()
    except Exception:
        pass  # Tüm hatalar zaten patched_setup'ta toplandi
    finally:
        RelationshipProperty._setup_join_conditions = original_setup
    
    return fk_errors, other_errors


def main():
    print("=" * 70)
    print("SQLALCHEMY MAPPER VALIDATION - ROOT CAUSE ANALYSIS")
    print("=" * 70)
    
    print("\n[1] Model modülleri import ediliyor...")
    imported, import_errors = import_all_models()
    print(f"\n  Import: {len(imported)} OK, {len(import_errors)} hata")
    
    print("\n[2] Tüm relationship'ler test ediliyor (patched)...")
    fk_errors, other_errors = validate_with_patched_setup()
    
    # RAPOR
    print("\n" + "=" * 70)
    print("SONUC RAPORU")
    print("=" * 70)
    
    total = len(fk_errors) + len(other_errors) + len(import_errors)
    
    if total == 0:
        print("\n  ✅ TÜM MAPPER'LAR OK")
        return 0
    
    # FOREIGN KEY HATALARI (Root Cause)
    if fk_errors:
        print(f"\n  📋 FOREIGN KEY HATALARI (Root Cause): {len(fk_errors)}")
        print("-" * 70)
        for i, err in enumerate(fk_errors, 1):
            print(f"\n  {i}. {err['relationship']}")
            print(f"     Parent Tablo: {err['parent_table']}")
            print(f"     Hedef: {err['target']}")
            print(f"     Çözüm: Child tabloya ForeignKey sütunu ekle (nullable=True)")
    
    # DİGER HATALAR
    if other_errors:
        print(f"\n  📋 DİGER HATALAR: {len(other_errors)}")
        for err in other_errors:
            print(f"  - {err['relationship']}: [{err['error']}] {err['detail'][:80]}")
    
    # IMPORT HATALARI
    if import_errors:
        print(f"\n  📋 IMPORT HATALARI: {len(import_errors)}")
        for err in import_errors:
            print(f"  - {err['module']}: [{err['type']}] {err['msg']}")
    
    # COZUM ONERILERI
    print("\n" + "=" * 70)
    print("TOPLU COZUM PLANI")
    print("=" * 70)
    
    for err in fk_errors:
        rel = err['relationship']
        parts = rel.split('.')
        if len(parts) == 2:
            parent, child_rel = parts
            print(f"\n  {rel}:")
            print(f"    Child modelde `{child_rel}_id` Column(Integer, ForeignKey(...), nullable=True) ekle")
    
    print(f"\n  Toplam düzeltme: {len(fk_errors)} relationship")
    print(f"  Her biri için: Child tabloya nullable ForeignKey column")
    print(f"  Sonrasında: Alembic migration oluştur ve çalıştır")
    
    print("\n" + "=" * 70)
    print(f"SONUC: FAIL ❌ ({len(fk_errors)} FK + {len(other_errors)} diger + {len(import_errors)} import)")
    print("=" * 70)
    return 1


if __name__ == "__main__":
    sys.exit(main())
