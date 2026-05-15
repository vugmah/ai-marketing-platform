"""
ERP Integration migration: create 10 ERP sync tables.

Revision ID: 002
Revises: 001
Create Date: 2025-02-15 00:00:00.000000

Creates ENUM types and tables for ERP integration:
- erp_connections: connection configs per company/branch
- erp_sync_jobs: sync job tracking
- erp_sync_logs: granular sync log entries
- erp_field_mappings: ERP-to-internal field mapping rules
- erp_products: synchronized product catalog
- erp_inventory: inventory/stock levels
- erp_sales_orders: sales order data
- erp_customers: customer/master data
- erp_invoices: invoice documents
- erp_payments: payment transactions
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


# ---------------------------------------------------------------------------
# Helper: shared ENUM values
# ---------------------------------------------------------------------------

ERP_PROVIDER_VALUES = [
    "custom", "odoo", "sap", "netsuite", "dynamics",
    "logo", "mikro", "parasut", "1c",
]


def _create_enum(name: str, values: list[str]) -> sa.Enum:
    """Create a PostgreSQL ENUM type."""
    e = sa.Enum(*values, name=name)
    e.create(op.get_bind(), checkfirst=True)
    return e


def _drop_enum(name: str) -> None:
    """Drop a PostgreSQL ENUM type."""
    sa.Enum(name=name).drop(op.get_bind(), checkfirst=True)


# ---------------------------------------------------------------------------
# upgrade
# ---------------------------------------------------------------------------

def upgrade() -> None:
    """Create ERP integration ENUMs, tables, indexes, and constraints."""

    # -- 1. ENUM types ------------------------------------------------------
    erpprovidertype = _create_enum("erpprovidertype", ERP_PROVIDER_VALUES)
    syncstatus = _create_enum("syncstatus", ["success", "failed", "pending", "never"])
    syncjobtype = _create_enum("syncjobtype", ["manual", "scheduled", "webhook", "incremental", "full"])
    syncjobentitytype = _create_enum("syncjobentitytype", [
        "products", "inventory", "sales_orders", "customers",
        "invoices", "payments", "all",
    ])
    syncjobstatus = _create_enum("syncjobstatus", ["queued", "running", "completed", "failed", "cancelled"])
    loglevel = _create_enum("loglevel", ["info", "warning", "error", "debug"])

    # -- 2. erp_connections -------------------------------------------------
    op.create_table(
        "erp_connections",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("branch_id", sa.Integer(), nullable=True),
        sa.Column(
            "provider_type",
            sa.Enum(*ERP_PROVIDER_VALUES, name="erpprovidertype"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("base_url", sa.String(length=500), nullable=True),
        sa.Column("api_key", sa.String(length=500), nullable=True),
        sa.Column("api_secret", sa.String(length=500), nullable=True),
        sa.Column("oauth_token", sa.Text(), nullable=True),
        sa.Column("oauth_refresh_token", sa.Text(), nullable=True),
        sa.Column("oauth_expires_at", sa.DateTime(), nullable=True),
        sa.Column("sync_enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("auto_sync_interval_minutes", sa.Integer(), server_default="60", nullable=False),
        sa.Column("last_sync_at", sa.DateTime(), nullable=True),
        sa.Column(
            "last_sync_status",
            sa.Enum("success", "failed", "pending", "never", name="syncstatus"),
            server_default="never",
            nullable=False,
        ),
        sa.Column("webhook_secret", sa.String(length=255), nullable=True),
        sa.Column("webhook_url", sa.String(length=500), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        # PK
        sa.PrimaryKeyConstraint("id", name=op.f("pk_erp_connections")),
        # FKs
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["public.companies.id"],
            name=op.f("fk_erp_connections_company_id"),
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["branch_id"],
            ["public.branches.id"],
            name=op.f("fk_erp_connections_branch_id"),
            ondelete="SET NULL",
            onupdate="CASCADE",
        ),
        schema="public",
        comment="ERP/external system connection configurations",
    )
    op.create_index(op.f("ix_erp_connections_id"), "erp_connections", ["id"], unique=False, schema="public")
    op.create_index(op.f("ix_erp_connections_company_id"), "erp_connections", ["company_id"], unique=False, schema="public")
    op.create_index(op.f("ix_erp_connections_branch_id"), "erp_connections", ["branch_id"], unique=False, schema="public")
    op.create_index(op.f("ix_erp_connections_provider_type"), "erp_connections", ["provider_type"], unique=False, schema="public")
    op.create_index(op.f("ix_erp_connections_created_at"), "erp_connections", ["created_at"], unique=False, schema="public")

    # -- 3. erp_sync_jobs ---------------------------------------------------
    op.create_table(
        "erp_sync_jobs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("branch_id", sa.Integer(), nullable=True),
        sa.Column("connection_id", sa.Integer(), nullable=False),
        sa.Column(
            "job_type",
            sa.Enum("manual", "scheduled", "webhook", "incremental", "full", name="syncjobtype"),
            nullable=False,
        ),
        sa.Column(
            "entity_type",
            sa.Enum("products", "inventory", "sales_orders", "customers", "invoices", "payments", "all", name="syncjobentitytype"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum("queued", "running", "completed", "failed", "cancelled", name="syncjobstatus"),
            server_default="queued",
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("records_total", sa.Integer(), server_default="0", nullable=False),
        sa.Column("records_processed", sa.Integer(), server_default="0", nullable=False),
        sa.Column("records_failed", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("max_retries", sa.Integer(), server_default="3", nullable=False),
        sa.Column("next_page_token", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        # PK
        sa.PrimaryKeyConstraint("id", name=op.f("pk_erp_sync_jobs")),
        # FKs
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["public.companies.id"],
            name=op.f("fk_erp_sync_jobs_company_id"),
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["branch_id"],
            ["public.branches.id"],
            name=op.f("fk_erp_sync_jobs_branch_id"),
            ondelete="SET NULL",
            onupdate="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["connection_id"],
            ["public.erp_connections.id"],
            name=op.f("fk_erp_sync_jobs_connection_id"),
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        schema="public",
        comment="ERP synchronization job tracking",
    )
    op.create_index(op.f("ix_erp_sync_jobs_id"), "erp_sync_jobs", ["id"], unique=False, schema="public")
    op.create_index(op.f("ix_erp_sync_jobs_company_id"), "erp_sync_jobs", ["company_id"], unique=False, schema="public")
    op.create_index(op.f("ix_erp_sync_jobs_branch_id"), "erp_sync_jobs", ["branch_id"], unique=False, schema="public")
    op.create_index(op.f("ix_erp_sync_jobs_connection_id"), "erp_sync_jobs", ["connection_id"], unique=False, schema="public")
    op.create_index(op.f("ix_erp_sync_jobs_status"), "erp_sync_jobs", ["status"], unique=False, schema="public")
    op.create_index(op.f("ix_erp_sync_jobs_created_at"), "erp_sync_jobs", ["created_at"], unique=False, schema="public")

    # -- 4. erp_sync_logs ---------------------------------------------------
    op.create_table(
        "erp_sync_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=True),
        sa.Column("connection_id", sa.Integer(), nullable=False),
        sa.Column(
            "log_level",
            sa.Enum("info", "warning", "error", "debug", name="loglevel"),
            server_default="info",
            nullable=False,
        ),
        sa.Column("entity_type", sa.String(length=50), nullable=False),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=False),
        sa.Column("internal_id", sa.Integer(), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        # PK
        sa.PrimaryKeyConstraint("id", name=op.f("pk_erp_sync_logs")),
        # FKs
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["public.companies.id"],
            name=op.f("fk_erp_sync_logs_company_id"),
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["public.erp_sync_jobs.id"],
            name=op.f("fk_erp_sync_logs_job_id"),
            ondelete="SET NULL",
            onupdate="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["connection_id"],
            ["public.erp_connections.id"],
            name=op.f("fk_erp_sync_logs_connection_id"),
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        schema="public",
        comment="Granular ERP synchronization log entries",
    )
    op.create_index(op.f("ix_erp_sync_logs_id"), "erp_sync_logs", ["id"], unique=False, schema="public")
    op.create_index(op.f("ix_erp_sync_logs_company_id"), "erp_sync_logs", ["company_id"], unique=False, schema="public")
    op.create_index(op.f("ix_erp_sync_logs_job_id"), "erp_sync_logs", ["job_id"], unique=False, schema="public")
    op.create_index(op.f("ix_erp_sync_logs_connection_id"), "erp_sync_logs", ["connection_id"], unique=False, schema="public")
    op.create_index(op.f("ix_erp_sync_logs_external_id"), "erp_sync_logs", ["external_id"], unique=False, schema="public")
    op.create_index(op.f("ix_erp_sync_logs_created_at"), "erp_sync_logs", ["created_at"], unique=False, schema="public")

    # -- 5. erp_field_mappings ----------------------------------------------
    op.create_table(
        "erp_field_mappings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("connection_id", sa.Integer(), nullable=False),
        sa.Column(
            "provider_type",
            sa.Enum(*ERP_PROVIDER_VALUES, name="erpprovidertype"),
            nullable=False,
        ),
        sa.Column("entity_type", sa.String(length=50), nullable=False),
        sa.Column("erp_field", sa.String(length=255), nullable=False),
        sa.Column("internal_field", sa.String(length=255), nullable=False),
        sa.Column("transformation", sa.String(length=255), nullable=True),
        sa.Column("is_required", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("default_value", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        # PK
        sa.PrimaryKeyConstraint("id", name=op.f("pk_erp_field_mappings")),
        # FKs
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["public.companies.id"],
            name=op.f("fk_erp_field_mappings_company_id"),
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["connection_id"],
            ["public.erp_connections.id"],
            name=op.f("fk_erp_field_mappings_connection_id"),
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        schema="public",
        comment="ERP-to-internal field mapping and transformation rules",
    )
    op.create_index(op.f("ix_erp_field_mappings_id"), "erp_field_mappings", ["id"], unique=False, schema="public")
    op.create_index(op.f("ix_erp_field_mappings_company_id"), "erp_field_mappings", ["company_id"], unique=False, schema="public")
    op.create_index(op.f("ix_erp_field_mappings_connection_id"), "erp_field_mappings", ["connection_id"], unique=False, schema="public")
    op.create_index(op.f("ix_erp_field_mappings_provider_type"), "erp_field_mappings", ["provider_type"], unique=False, schema="public")
    op.create_index(op.f("ix_erp_field_mappings_entity_type"), "erp_field_mappings", ["entity_type"], unique=False, schema="public")
    op.create_index(op.f("ix_erp_field_mappings_created_at"), "erp_field_mappings", ["created_at"], unique=False, schema="public")

    # -- 6. erp_products ----------------------------------------------------
    op.create_table(
        "erp_products",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("branch_id", sa.Integer(), nullable=True),
        sa.Column("connection_id", sa.Integer(), nullable=False),
        sa.Column(
            "provider_type",
            sa.Enum(*ERP_PROVIDER_VALUES, name="erpprovidertype"),
            nullable=False,
        ),
        sa.Column("external_id", sa.String(length=255), nullable=False),
        sa.Column("external_code", sa.String(length=255), nullable=True),
        sa.Column("name", sa.String(length=500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(length=255), nullable=True),
        sa.Column("unit_price", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("currency", sa.String(length=3), server_default="AZN", nullable=False),
        sa.Column("cost_price", sa.Float(), nullable=True),
        sa.Column("tax_rate", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("barcode", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("raw_data", sa.JSON(), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        # PK
        sa.PrimaryKeyConstraint("id", name=op.f("pk_erp_products")),
        # FKs
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["public.companies.id"],
            name=op.f("fk_erp_products_company_id"),
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["branch_id"],
            ["public.branches.id"],
            name=op.f("fk_erp_products_branch_id"),
            ondelete="SET NULL",
            onupdate="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["connection_id"],
            ["public.erp_connections.id"],
            name=op.f("fk_erp_products_connection_id"),
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        schema="public",
        comment="Products synchronized from ERP systems",
    )
    op.create_index(op.f("ix_erp_products_id"), "erp_products", ["id"], unique=False, schema="public")
    op.create_index(op.f("ix_erp_products_company_id"), "erp_products", ["company_id"], unique=False, schema="public")
    op.create_index(op.f("ix_erp_products_branch_id"), "erp_products", ["branch_id"], unique=False, schema="public")
    op.create_index(op.f("ix_erp_products_connection_id"), "erp_products", ["connection_id"], unique=False, schema="public")
    op.create_index(op.f("ix_erp_products_provider_type"), "erp_products", ["provider_type"], unique=False, schema="public")
    op.create_index(op.f("ix_erp_products_external_id"), "erp_products", ["external_id"], unique=False, schema="public")
    op.create_index(op.f("ix_erp_products_external_code"), "erp_products", ["external_code"], unique=False, schema="public")
    op.create_index(op.f("ix_erp_products_barcode"), "erp_products", ["barcode"], unique=False, schema="public")
    op.create_index(op.f("ix_erp_products_created_at"), "erp_products", ["created_at"], unique=False, schema="public")

    # -- 7. erp_inventory ---------------------------------------------------
    op.create_table(
        "erp_inventory",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("branch_id", sa.Integer(), nullable=True),
        sa.Column("connection_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=True),
        sa.Column(
            "provider_type",
            sa.Enum(*ERP_PROVIDER_VALUES, name="erpprovidertype"),
            nullable=False,
        ),
        sa.Column("external_id", sa.String(length=255), nullable=False),
        sa.Column("external_warehouse_code", sa.String(length=255), nullable=True),
        sa.Column("quantity_available", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("quantity_reserved", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("quantity_incoming", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("reorder_level", sa.Float(), nullable=True),
        sa.Column("reorder_quantity", sa.Float(), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        # PK
        sa.PrimaryKeyConstraint("id", name=op.f("pk_erp_inventory")),
        # FKs
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["public.companies.id"],
            name=op.f("fk_erp_inventory_company_id"),
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["branch_id"],
            ["public.branches.id"],
            name=op.f("fk_erp_inventory_branch_id"),
            ondelete="SET NULL",
            onupdate="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["connection_id"],
            ["public.erp_connections.id"],
            name=op.f("fk_erp_inventory_connection_id"),
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["public.erp_products.id"],
            name=op.f("fk_erp_inventory_product_id"),
            ondelete="SET NULL",
            onupdate="CASCADE",
        ),
        schema="public",
        comment="Inventory levels synchronized from ERP systems",
    )
    op.create_index(op.f("ix_erp_inventory_id"), "erp_inventory", ["id"], unique=False, schema="public")
    op.create_index(op.f("ix_erp_inventory_company_id"), "erp_inventory", ["company_id"], unique=False, schema="public")
    op.create_index(op.f("ix_erp_inventory_branch_id"), "erp_inventory", ["branch_id"], unique=False, schema="public")
    op.create_index(op.f("ix_erp_inventory_connection_id"), "erp_inventory", ["connection_id"], unique=False, schema="public")
    op.create_index(op.f("ix_erp_inventory_product_id"), "erp_inventory", ["product_id"], unique=False, schema="public")
    op.create_index(op.f("ix_erp_inventory_provider_type"), "erp_inventory", ["provider_type"], unique=False, schema="public")
    op.create_index(op.f("ix_erp_inventory_external_id"), "erp_inventory", ["external_id"], unique=False, schema="public")
    op.create_index(op.f("ix_erp_inventory_created_at"), "erp_inventory", ["created_at"], unique=False, schema="public")

    # -- 8. erp_sales_orders ------------------------------------------------
    op.create_table(
        "erp_sales_orders",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("branch_id", sa.Integer(), nullable=True),
        sa.Column("connection_id", sa.Integer(), nullable=False),
        sa.Column(
            "provider_type",
            sa.Enum(*ERP_PROVIDER_VALUES, name="erpprovidertype"),
            nullable=False,
        ),
        sa.Column("external_id", sa.String(length=255), nullable=False),
        sa.Column("external_order_number", sa.String(length=255), nullable=True),
        sa.Column("customer_external_id", sa.String(length=255), nullable=True),
        sa.Column("customer_name", sa.String(length=255), nullable=True),
        sa.Column("order_date", sa.DateTime(), nullable=False),
        sa.Column("delivery_date", sa.DateTime(), nullable=True),
        sa.Column("total_amount", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("tax_amount", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("discount_amount", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("currency", sa.String(length=3), server_default="AZN", nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("payment_status", sa.String(length=50), nullable=False),
        sa.Column("raw_data", sa.JSON(), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        # PK
        sa.PrimaryKeyConstraint("id", name=op.f("pk_erp_sales_orders")),
        # FKs
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["public.companies.id"],
            name=op.f("fk_erp_sales_orders_company_id"),
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["branch_id"],
            ["public.branches.id"],
            name=op.f("fk_erp_sales_orders_branch_id"),
            ondelete="SET NULL",
            onupdate="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["connection_id"],
            ["public.erp_connections.id"],
            name=op.f("fk_erp_sales_orders_connection_id"),
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        schema="public",
        comment="Sales orders synchronized from ERP systems",
    )
    op.create_index(op.f("ix_erp_sales_orders_id"), "erp_sales_orders", ["id"], unique=False, schema="public")
    op.create_index(op.f("ix_erp_sales_orders_company_id"), "erp_sales_orders", ["company_id"], unique=False, schema="public")
    op.create_index(op.f("ix_erp_sales_orders_branch_id"), "erp_sales_orders", ["branch_id"], unique=False, schema="public")
    op.create_index(op.f("ix_erp_sales_orders_connection_id"), "erp_sales_orders", ["connection_id"], unique=False, schema="public")
    op.create_index(op.f("ix_erp_sales_orders_provider_type"), "erp_sales_orders", ["provider_type"], unique=False, schema="public")
    op.create_index(op.f("ix_erp_sales_orders_external_id"), "erp_sales_orders", ["external_id"], unique=False, schema="public")
    op.create_index(op.f("ix_erp_sales_orders_external_order_number"), "erp_sales_orders", ["external_order_number"], unique=False, schema="public")
    op.create_index(op.f("ix_erp_sales_orders_customer_external_id"), "erp_sales_orders", ["customer_external_id"], unique=False, schema="public")
    op.create_index(op.f("ix_erp_sales_orders_status"), "erp_sales_orders", ["status"], unique=False, schema="public")
    op.create_index(op.f("ix_erp_sales_orders_created_at"), "erp_sales_orders", ["created_at"], unique=False, schema="public")

    # -- 9. erp_customers ---------------------------------------------------
    op.create_table(
        "erp_customers",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("branch_id", sa.Integer(), nullable=True),
        sa.Column("connection_id", sa.Integer(), nullable=False),
        sa.Column(
            "provider_type",
            sa.Enum(*ERP_PROVIDER_VALUES, name="erpprovidertype"),
            nullable=False,
        ),
        sa.Column("external_id", sa.String(length=255), nullable=False),
        sa.Column("external_code", sa.String(length=255), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("tax_number", sa.String(length=50), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("city", sa.String(length=100), nullable=True),
        sa.Column("country", sa.String(length=100), server_default="Azerbaijan", nullable=False),
        sa.Column("customer_type", sa.String(length=50), nullable=False),
        sa.Column("credit_limit", sa.Float(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("raw_data", sa.JSON(), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        # PK
        sa.PrimaryKeyConstraint("id", name=op.f("pk_erp_customers")),
        # FKs
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["public.companies.id"],
            name=op.f("fk_erp_customers_company_id"),
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["branch_id"],
            ["public.branches.id"],
            name=op.f("fk_erp_customers_branch_id"),
            ondelete="SET NULL",
            onupdate="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["connection_id"],
            ["public.erp_connections.id"],
            name=op.f("fk_erp_customers_connection_id"),
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        schema="public",
        comment="Customers synchronized from ERP systems",
    )
    op.create_index(op.f("ix_erp_customers_id"), "erp_customers", ["id"], unique=False, schema="public")
    op.create_index(op.f("ix_erp_customers_company_id"), "erp_customers", ["company_id"], unique=False, schema="public")
    op.create_index(op.f("ix_erp_customers_branch_id"), "erp_customers", ["branch_id"], unique=False, schema="public")
    op.create_index(op.f("ix_erp_customers_connection_id"), "erp_customers", ["connection_id"], unique=False, schema="public")
    op.create_index(op.f("ix_erp_customers_provider_type"), "erp_customers", ["provider_type"], unique=False, schema="public")
    op.create_index(op.f("ix_erp_customers_external_id"), "erp_customers", ["external_id"], unique=False, schema="public")
    op.create_index(op.f("ix_erp_customers_created_at"), "erp_customers", ["created_at"], unique=False, schema="public")

    # -- 10. erp_invoices ---------------------------------------------------
    op.create_table(
        "erp_invoices",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("branch_id", sa.Integer(), nullable=True),
        sa.Column("connection_id", sa.Integer(), nullable=False),
        sa.Column("sales_order_id", sa.Integer(), nullable=True),
        sa.Column(
            "provider_type",
            sa.Enum(*ERP_PROVIDER_VALUES, name="erpprovidertype"),
            nullable=False,
        ),
        sa.Column("external_id", sa.String(length=255), nullable=False),
        sa.Column("external_invoice_number", sa.String(length=255), nullable=True),
        sa.Column("customer_external_id", sa.String(length=255), nullable=True),
        sa.Column("customer_name", sa.String(length=255), nullable=True),
        sa.Column("invoice_date", sa.DateTime(), nullable=False),
        sa.Column("due_date", sa.DateTime(), nullable=True),
        sa.Column("subtotal", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("tax_amount", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("total_amount", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("currency", sa.String(length=3), server_default="AZN", nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("raw_data", sa.JSON(), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        # PK
        sa.PrimaryKeyConstraint("id", name=op.f("pk_erp_invoices")),
        # FKs
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["public.companies.id"],
            name=op.f("fk_erp_invoices_company_id"),
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["branch_id"],
            ["public.branches.id"],
            name=op.f("fk_erp_invoices_branch_id"),
            ondelete="SET NULL",
            onupdate="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["connection_id"],
            ["public.erp_connections.id"],
            name=op.f("fk_erp_invoices_connection_id"),
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["sales_order_id"],
            ["public.erp_sales_orders.id"],
            name=op.f("fk_erp_invoices_sales_order_id"),
            ondelete="SET NULL",
            onupdate="CASCADE",
        ),
        schema="public",
        comment="Invoices synchronized from ERP systems",
    )
    op.create_index(op.f("ix_erp_invoices_id"), "erp_invoices", ["id"], unique=False, schema="public")
    op.create_index(op.f("ix_erp_invoices_company_id"), "erp_invoices", ["company_id"], unique=False, schema="public")
    op.create_index(op.f("ix_erp_invoices_branch_id"), "erp_invoices", ["branch_id"], unique=False, schema="public")
    op.create_index(op.f("ix_erp_invoices_connection_id"), "erp_invoices", ["connection_id"], unique=False, schema="public")
    op.create_index(op.f("ix_erp_invoices_sales_order_id"), "erp_invoices", ["sales_order_id"], unique=False, schema="public")
    op.create_index(op.f("ix_erp_invoices_provider_type"), "erp_invoices", ["provider_type"], unique=False, schema="public")
    op.create_index(op.f("ix_erp_invoices_external_id"), "erp_invoices", ["external_id"], unique=False, schema="public")
    op.create_index(op.f("ix_erp_invoices_external_invoice_number"), "erp_invoices", ["external_invoice_number"], unique=False, schema="public")
    op.create_index(op.f("ix_erp_invoices_status"), "erp_invoices", ["status"], unique=False, schema="public")
    op.create_index(op.f("ix_erp_invoices_created_at"), "erp_invoices", ["created_at"], unique=False, schema="public")

    # -- 11. erp_payments ---------------------------------------------------
    op.create_table(
        "erp_payments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("branch_id", sa.Integer(), nullable=True),
        sa.Column("connection_id", sa.Integer(), nullable=False),
        sa.Column("invoice_id", sa.Integer(), nullable=True),
        sa.Column(
            "provider_type",
            sa.Enum(*ERP_PROVIDER_VALUES, name="erpprovidertype"),
            nullable=False,
        ),
        sa.Column("external_id", sa.String(length=255), nullable=False),
        sa.Column("customer_external_id", sa.String(length=255), nullable=True),
        sa.Column("payment_method", sa.String(length=50), nullable=False),
        sa.Column("amount", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("currency", sa.String(length=3), server_default="AZN", nullable=False),
        sa.Column("payment_date", sa.DateTime(), nullable=False),
        sa.Column("reference_number", sa.String(length=255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("raw_data", sa.JSON(), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        # PK
        sa.PrimaryKeyConstraint("id", name=op.f("pk_erp_payments")),
        # FKs
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["public.companies.id"],
            name=op.f("fk_erp_payments_company_id"),
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["branch_id"],
            ["public.branches.id"],
            name=op.f("fk_erp_payments_branch_id"),
            ondelete="SET NULL",
            onupdate="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["connection_id"],
            ["public.erp_connections.id"],
            name=op.f("fk_erp_payments_connection_id"),
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["invoice_id"],
            ["public.erp_invoices.id"],
            name=op.f("fk_erp_payments_invoice_id"),
            ondelete="SET NULL",
            onupdate="CASCADE",
        ),
        schema="public",
        comment="Payments synchronized from ERP systems",
    )
    op.create_index(op.f("ix_erp_payments_id"), "erp_payments", ["id"], unique=False, schema="public")
    op.create_index(op.f("ix_erp_payments_company_id"), "erp_payments", ["company_id"], unique=False, schema="public")
    op.create_index(op.f("ix_erp_payments_branch_id"), "erp_payments", ["branch_id"], unique=False, schema="public")
    op.create_index(op.f("ix_erp_payments_connection_id"), "erp_payments", ["connection_id"], unique=False, schema="public")
    op.create_index(op.f("ix_erp_payments_invoice_id"), "erp_payments", ["invoice_id"], unique=False, schema="public")
    op.create_index(op.f("ix_erp_payments_provider_type"), "erp_payments", ["provider_type"], unique=False, schema="public")
    op.create_index(op.f("ix_erp_payments_external_id"), "erp_payments", ["external_id"], unique=False, schema="public")
    op.create_index(op.f("ix_erp_payments_status"), "erp_payments", ["status"], unique=False, schema="public")
    op.create_index(op.f("ix_erp_payments_created_at"), "erp_payments", ["created_at"], unique=False, schema="public")


# ---------------------------------------------------------------------------
# downgrade
# ---------------------------------------------------------------------------

def downgrade() -> None:
    """Drop ERP integration tables and ENUMs in reverse dependency order."""

    # -- Drop tables (reverse dependency order) -----------------------------
    op.drop_index(op.f("ix_erp_payments_created_at"), table_name="erp_payments", schema="public")
    op.drop_index(op.f("ix_erp_payments_status"), table_name="erp_payments", schema="public")
    op.drop_index(op.f("ix_erp_payments_external_id"), table_name="erp_payments", schema="public")
    op.drop_index(op.f("ix_erp_payments_provider_type"), table_name="erp_payments", schema="public")
    op.drop_index(op.f("ix_erp_payments_invoice_id"), table_name="erp_payments", schema="public")
    op.drop_index(op.f("ix_erp_payments_connection_id"), table_name="erp_payments", schema="public")
    op.drop_index(op.f("ix_erp_payments_branch_id"), table_name="erp_payments", schema="public")
    op.drop_index(op.f("ix_erp_payments_company_id"), table_name="erp_payments", schema="public")
    op.drop_index(op.f("ix_erp_payments_id"), table_name="erp_payments", schema="public")
    op.drop_table("erp_payments", schema="public")

    op.drop_index(op.f("ix_erp_invoices_created_at"), table_name="erp_invoices", schema="public")
    op.drop_index(op.f("ix_erp_invoices_status"), table_name="erp_invoices", schema="public")
    op.drop_index(op.f("ix_erp_invoices_external_invoice_number"), table_name="erp_invoices", schema="public")
    op.drop_index(op.f("ix_erp_invoices_external_id"), table_name="erp_invoices", schema="public")
    op.drop_index(op.f("ix_erp_invoices_provider_type"), table_name="erp_invoices", schema="public")
    op.drop_index(op.f("ix_erp_invoices_sales_order_id"), table_name="erp_invoices", schema="public")
    op.drop_index(op.f("ix_erp_invoices_connection_id"), table_name="erp_invoices", schema="public")
    op.drop_index(op.f("ix_erp_invoices_branch_id"), table_name="erp_invoices", schema="public")
    op.drop_index(op.f("ix_erp_invoices_company_id"), table_name="erp_invoices", schema="public")
    op.drop_index(op.f("ix_erp_invoices_id"), table_name="erp_invoices", schema="public")
    op.drop_table("erp_invoices", schema="public")

    op.drop_index(op.f("ix_erp_customers_created_at"), table_name="erp_customers", schema="public")
    op.drop_index(op.f("ix_erp_customers_external_id"), table_name="erp_customers", schema="public")
    op.drop_index(op.f("ix_erp_customers_provider_type"), table_name="erp_customers", schema="public")
    op.drop_index(op.f("ix_erp_customers_connection_id"), table_name="erp_customers", schema="public")
    op.drop_index(op.f("ix_erp_customers_branch_id"), table_name="erp_customers", schema="public")
    op.drop_index(op.f("ix_erp_customers_company_id"), table_name="erp_customers", schema="public")
    op.drop_index(op.f("ix_erp_customers_id"), table_name="erp_customers", schema="public")
    op.drop_table("erp_customers", schema="public")

    op.drop_index(op.f("ix_erp_sales_orders_created_at"), table_name="erp_sales_orders", schema="public")
    op.drop_index(op.f("ix_erp_sales_orders_status"), table_name="erp_sales_orders", schema="public")
    op.drop_index(op.f("ix_erp_sales_orders_customer_external_id"), table_name="erp_sales_orders", schema="public")
    op.drop_index(op.f("ix_erp_sales_orders_external_order_number"), table_name="erp_sales_orders", schema="public")
    op.drop_index(op.f("ix_erp_sales_orders_external_id"), table_name="erp_sales_orders", schema="public")
    op.drop_index(op.f("ix_erp_sales_orders_provider_type"), table_name="erp_sales_orders", schema="public")
    op.drop_index(op.f("ix_erp_sales_orders_connection_id"), table_name="erp_sales_orders", schema="public")
    op.drop_index(op.f("ix_erp_sales_orders_branch_id"), table_name="erp_sales_orders", schema="public")
    op.drop_index(op.f("ix_erp_sales_orders_company_id"), table_name="erp_sales_orders", schema="public")
    op.drop_index(op.f("ix_erp_sales_orders_id"), table_name="erp_sales_orders", schema="public")
    op.drop_table("erp_sales_orders", schema="public")

    op.drop_index(op.f("ix_erp_inventory_created_at"), table_name="erp_inventory", schema="public")
    op.drop_index(op.f("ix_erp_inventory_external_id"), table_name="erp_inventory", schema="public")
    op.drop_index(op.f("ix_erp_inventory_provider_type"), table_name="erp_inventory", schema="public")
    op.drop_index(op.f("ix_erp_inventory_product_id"), table_name="erp_inventory", schema="public")
    op.drop_index(op.f("ix_erp_inventory_connection_id"), table_name="erp_inventory", schema="public")
    op.drop_index(op.f("ix_erp_inventory_branch_id"), table_name="erp_inventory", schema="public")
    op.drop_index(op.f("ix_erp_inventory_company_id"), table_name="erp_inventory", schema="public")
    op.drop_index(op.f("ix_erp_inventory_id"), table_name="erp_inventory", schema="public")
    op.drop_table("erp_inventory", schema="public")

    op.drop_index(op.f("ix_erp_products_created_at"), table_name="erp_products", schema="public")
    op.drop_index(op.f("ix_erp_products_barcode"), table_name="erp_products", schema="public")
    op.drop_index(op.f("ix_erp_products_external_code"), table_name="erp_products", schema="public")
    op.drop_index(op.f("ix_erp_products_external_id"), table_name="erp_products", schema="public")
    op.drop_index(op.f("ix_erp_products_provider_type"), table_name="erp_products", schema="public")
    op.drop_index(op.f("ix_erp_products_connection_id"), table_name="erp_products", schema="public")
    op.drop_index(op.f("ix_erp_products_branch_id"), table_name="erp_products", schema="public")
    op.drop_index(op.f("ix_erp_products_company_id"), table_name="erp_products", schema="public")
    op.drop_index(op.f("ix_erp_products_id"), table_name="erp_products", schema="public")
    op.drop_table("erp_products", schema="public")

    op.drop_index(op.f("ix_erp_field_mappings_created_at"), table_name="erp_field_mappings", schema="public")
    op.drop_index(op.f("ix_erp_field_mappings_entity_type"), table_name="erp_field_mappings", schema="public")
    op.drop_index(op.f("ix_erp_field_mappings_provider_type"), table_name="erp_field_mappings", schema="public")
    op.drop_index(op.f("ix_erp_field_mappings_connection_id"), table_name="erp_field_mappings", schema="public")
    op.drop_index(op.f("ix_erp_field_mappings_company_id"), table_name="erp_field_mappings", schema="public")
    op.drop_index(op.f("ix_erp_field_mappings_id"), table_name="erp_field_mappings", schema="public")
    op.drop_table("erp_field_mappings", schema="public")

    op.drop_index(op.f("ix_erp_sync_logs_created_at"), table_name="erp_sync_logs", schema="public")
    op.drop_index(op.f("ix_erp_sync_logs_external_id"), table_name="erp_sync_logs", schema="public")
    op.drop_index(op.f("ix_erp_sync_logs_connection_id"), table_name="erp_sync_logs", schema="public")
    op.drop_index(op.f("ix_erp_sync_logs_job_id"), table_name="erp_sync_logs", schema="public")
    op.drop_index(op.f("ix_erp_sync_logs_company_id"), table_name="erp_sync_logs", schema="public")
    op.drop_index(op.f("ix_erp_sync_logs_id"), table_name="erp_sync_logs", schema="public")
    op.drop_table("erp_sync_logs", schema="public")

    op.drop_index(op.f("ix_erp_sync_jobs_created_at"), table_name="erp_sync_jobs", schema="public")
    op.drop_index(op.f("ix_erp_sync_jobs_status"), table_name="erp_sync_jobs", schema="public")
    op.drop_index(op.f("ix_erp_sync_jobs_connection_id"), table_name="erp_sync_jobs", schema="public")
    op.drop_index(op.f("ix_erp_sync_jobs_branch_id"), table_name="erp_sync_jobs", schema="public")
    op.drop_index(op.f("ix_erp_sync_jobs_company_id"), table_name="erp_sync_jobs", schema="public")
    op.drop_index(op.f("ix_erp_sync_jobs_id"), table_name="erp_sync_jobs", schema="public")
    op.drop_table("erp_sync_jobs", schema="public")

    op.drop_index(op.f("ix_erp_connections_created_at"), table_name="erp_connections", schema="public")
    op.drop_index(op.f("ix_erp_connections_provider_type"), table_name="erp_connections", schema="public")
    op.drop_index(op.f("ix_erp_connections_branch_id"), table_name="erp_connections", schema="public")
    op.drop_index(op.f("ix_erp_connections_company_id"), table_name="erp_connections", schema="public")
    op.drop_index(op.f("ix_erp_connections_id"), table_name="erp_connections", schema="public")
    op.drop_table("erp_connections", schema="public")

    # -- Drop ENUM types (reverse order of creation) ------------------------
    _drop_enum("loglevel")
    _drop_enum("syncjobstatus")
    _drop_enum("syncjobentitytype")
    _drop_enum("syncjobtype")
    _drop_enum("syncstatus")
    _drop_enum("erpprovidertype")
