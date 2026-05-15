"""
ERP Integration models for multi-tenant external system synchronization.

Provides 9 tables for managing ERP connections, sync jobs, field mappings,
and synchronized entity data (products, inventory, sales orders, customers,
invoices, payments) across 9 provider types.
"""

import enum
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.database import Base


# ---------------------------------------------------------------------------
# Shared ENUMs
# ---------------------------------------------------------------------------

class ERPProviderType(str, enum.Enum):
    """Supported ERP/external system providers."""

    CUSTOM = "custom"
    ODOO = "odoo"
    SAP = "sap"
    NETSUITE = "netsuite"
    DYNAMICS = "dynamics"
    LOGO = "logo"
    MIKRO = "mikro"
    PARASUT = "parasut"
    ONE_C = "1c"


class SyncStatus(str, enum.Enum):
    """High-level sync status for connections and jobs."""

    SUCCESS = "success"
    FAILED = "failed"
    PENDING = "pending"
    NEVER = "never"


class SyncJobType(str, enum.Enum):
    """How a sync job was triggered."""

    MANUAL = "manual"
    SCHEDULED = "scheduled"
    WEBHOOK = "webhook"
    INCREMENTAL = "incremental"
    FULL = "full"


class SyncJobEntityType(str, enum.Enum):
    """Entity scope for a sync job."""

    PRODUCTS = "products"
    INVENTORY = "inventory"
    SALES_ORDERS = "sales_orders"
    CUSTOMERS = "customers"
    INVOICES = "invoices"
    PAYMENTS = "payments"
    ALL = "all"


class SyncJobStatus(str, enum.Enum):
    """Lifecycle status of a sync job."""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class LogLevel(str, enum.Enum):
    """Severity level for sync log entries."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    DEBUG = "debug"


# ---------------------------------------------------------------------------
# 1. ERP Connection
# ---------------------------------------------------------------------------

class ERPConnection(Base):
    """
    Connection configuration for an external ERP system.

    Stores encrypted credentials, sync schedule, webhook settings, and
    status for a single ERP integration per company/branch.
    """

    __tablename__ = "erp_connections"
    __table_args__ = {
        "schema": "public",
        "comment": "ERP/external system connection configurations",
    }

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    company_id = Column(
        Integer,
        ForeignKey(
            "public.companies.id",
            ondelete="CASCADE",
            onupdate="CASCADE",
            name="fk_erp_connections_company_id",
        ),
        nullable=False,
        index=True,
    )
    branch_id = Column(
        Integer,
        ForeignKey(
            "public.branches.id",
            ondelete="SET NULL",
            onupdate="CASCADE",
            name="fk_erp_connections_branch_id",
        ),
        nullable=True,
        index=True,
    )

    provider_type = Column(
        Enum(ERPProviderType, name="erpprovidertype", create_type=True),
        nullable=False,
        index=True,
    )
    name = Column(String(255), nullable=False)

    # Connection config (values encrypted at rest in production)
    base_url = Column(String(500), nullable=True)
    api_key = Column(String(500), nullable=True)
    api_secret = Column(String(500), nullable=True)
    oauth_token = Column(Text, nullable=True)
    oauth_refresh_token = Column(Text, nullable=True)
    oauth_expires_at = Column(DateTime, nullable=True)

    # Sync config
    sync_enabled = Column(Boolean, default=True, nullable=False)
    auto_sync_interval_minutes = Column(Integer, default=60, nullable=False)
    last_sync_at = Column(DateTime, nullable=True)
    last_sync_status = Column(
        Enum(SyncStatus, name="syncstatus", create_type=True),
        default=SyncStatus.NEVER,
        nullable=False,
    )

    # Webhook config
    webhook_secret = Column(String(255), nullable=True)
    webhook_url = Column(String(500), nullable=True)

    # Status
    is_active = Column(Boolean, default=True, nullable=False)

    # Timestamps
    created_at = Column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    sync_jobs = relationship(
        "ERPSyncJob",
        back_populates="connection",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    sync_logs = relationship(
        "ERPSyncLog",
        back_populates="connection",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    field_mappings = relationship(
        "ERPFieldMapping",
        back_populates="connection",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    products = relationship(
        "ERPProduct",
        back_populates="connection",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    inventory_items = relationship(
        "ERPInventory",
        back_populates="connection",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    sales_orders = relationship(
        "ERPSalesOrder",
        back_populates="connection",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    customers = relationship(
        "ERPCustomer",
        back_populates="connection",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    invoices = relationship(
        "ERPInvoice",
        back_populates="connection",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    payments = relationship(
        "ERPPayment",
        back_populates="connection",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return (
            f"<ERPConnection(id={self.id}, name='{self.name}', "
            f"provider='{self.provider_type}', company_id={self.company_id})>"
        )


# ---------------------------------------------------------------------------
# 2. ERP Sync Job
# ---------------------------------------------------------------------------

class ERPSyncJob(Base):
    """
    A single synchronization job run.

    Tracks progress, record counts, errors, and pagination state for
    long-running or incremental sync operations.
    """

    __tablename__ = "erp_sync_jobs"
    __table_args__ = {
        "schema": "public",
        "comment": "ERP synchronization job tracking",
    }

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    company_id = Column(
        Integer,
        ForeignKey(
            "public.companies.id",
            ondelete="CASCADE",
            onupdate="CASCADE",
            name="fk_erp_sync_jobs_company_id",
        ),
        nullable=False,
        index=True,
    )
    branch_id = Column(
        Integer,
        ForeignKey(
            "public.branches.id",
            ondelete="SET NULL",
            onupdate="CASCADE",
            name="fk_erp_sync_jobs_branch_id",
        ),
        nullable=True,
        index=True,
    )
    connection_id = Column(
        Integer,
        ForeignKey(
            "public.erp_connections.id",
            ondelete="CASCADE",
            onupdate="CASCADE",
            name="fk_erp_sync_jobs_connection_id",
        ),
        nullable=False,
        index=True,
    )

    job_type = Column(
        Enum(SyncJobType, name="syncjobtype", create_type=True),
        nullable=False,
    )
    entity_type = Column(
        Enum(SyncJobEntityType, name="syncjobentitytype", create_type=True),
        nullable=False,
    )

    status = Column(
        Enum(SyncJobStatus, name="syncjobstatus", create_type=True),
        default=SyncJobStatus.QUEUED,
        nullable=False,
        index=True,
    )
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    records_total = Column(Integer, default=0, nullable=False)
    records_processed = Column(Integer, default=0, nullable=False)
    records_failed = Column(Integer, default=0, nullable=False)

    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0, nullable=False)
    max_retries = Column(Integer, default=3, nullable=False)

    next_page_token = Column(String(255), nullable=True)

    created_at = Column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    connection = relationship("ERPConnection", back_populates="sync_jobs")
    logs = relationship(
        "ERPSyncLog",
        back_populates="job",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return (
            f"<ERPSyncJob(id={self.id}, type='{self.job_type}', "
            f"entity='{self.entity_type}', status='{self.status}')>"
        )


# ---------------------------------------------------------------------------
# 3. ERP Sync Log
# ---------------------------------------------------------------------------

class ERPSyncLog(Base):
    """
    Granular log entry for a sync operation.

    Records individual record-level events (create, update, delete, skip)
    with external/internal ID correlation and full detail payloads.
    """

    __tablename__ = "erp_sync_logs"
    __table_args__ = {
        "schema": "public",
        "comment": "Granular ERP synchronization log entries",
    }

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    company_id = Column(
        Integer,
        ForeignKey(
            "public.companies.id",
            ondelete="CASCADE",
            onupdate="CASCADE",
            name="fk_erp_sync_logs_company_id",
        ),
        nullable=False,
        index=True,
    )
    job_id = Column(
        Integer,
        ForeignKey(
            "public.erp_sync_jobs.id",
            ondelete="SET NULL",
            onupdate="CASCADE",
            name="fk_erp_sync_logs_job_id",
        ),
        nullable=True,
        index=True,
    )
    connection_id = Column(
        Integer,
        ForeignKey(
            "public.erp_connections.id",
            ondelete="CASCADE",
            onupdate="CASCADE",
            name="fk_erp_sync_logs_connection_id",
        ),
        nullable=False,
        index=True,
    )

    log_level = Column(
        Enum(LogLevel, name="loglevel", create_type=True),
        default=LogLevel.INFO,
        nullable=False,
    )
    entity_type = Column(String(50), nullable=False)
    action = Column(String(50), nullable=False)

    external_id = Column(String(255), nullable=False, index=True)
    internal_id = Column(Integer, nullable=True)

    message = Column(Text, nullable=False)
    details = Column(JSON, nullable=True)

    created_at = Column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )

    # Relationships
    job = relationship("ERPSyncJob", back_populates="logs")
    connection = relationship("ERPConnection", back_populates="sync_logs")

    def __repr__(self) -> str:
        return (
            f"<ERPSyncLog(id={self.id}, level='{self.log_level}', "
            f"entity='{self.entity_type}', action='{self.action}')>"
        )


# ---------------------------------------------------------------------------
# 4. ERP Field Mapping
# ---------------------------------------------------------------------------

class ERPFieldMapping(Base):
    """
    Field-level mapping between ERP and internal schemas.

    Allows configurable transformation rules per provider and entity type,
    enabling flexible integrations without code changes.
    """

    __tablename__ = "erp_field_mappings"
    __table_args__ = {
        "schema": "public",
        "comment": "ERP-to-internal field mapping and transformation rules",
    }

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    company_id = Column(
        Integer,
        ForeignKey(
            "public.companies.id",
            ondelete="CASCADE",
            onupdate="CASCADE",
            name="fk_erp_field_mappings_company_id",
        ),
        nullable=False,
        index=True,
    )
    connection_id = Column(
        Integer,
        ForeignKey(
            "public.erp_connections.id",
            ondelete="CASCADE",
            onupdate="CASCADE",
            name="fk_erp_field_mappings_connection_id",
        ),
        nullable=False,
        index=True,
    )

    provider_type = Column(
        Enum(ERPProviderType, name="erpprovidertype", create_type=True),
        nullable=False,
        index=True,
    )
    entity_type = Column(String(50), nullable=False, index=True)

    erp_field = Column(String(255), nullable=False)
    internal_field = Column(String(255), nullable=False)
    transformation = Column(String(255), nullable=True)
    is_required = Column(Boolean, default=False, nullable=False)
    default_value = Column(String(255), nullable=True)

    created_at = Column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    connection = relationship("ERPConnection", back_populates="field_mappings")

    def __repr__(self) -> str:
        return (
            f"<ERPFieldMapping(id={self.id}, "
            f"erp_field='{self.erp_field}', "
            f"internal_field='{self.internal_field}')>"
        )


# ---------------------------------------------------------------------------
# 5. ERP Product
# ---------------------------------------------------------------------------

class ERPProduct(Base):
    """
    Product data synchronized from an external ERP.

    Mirrors the ERP product catalog with pricing, taxonomy, and raw data
    snapshots for audit and reconciliation.
    """

    __tablename__ = "erp_products"
    __table_args__ = {
        "schema": "public",
        "comment": "Products synchronized from ERP systems",
    }

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    company_id = Column(
        Integer,
        ForeignKey(
            "public.companies.id",
            ondelete="CASCADE",
            onupdate="CASCADE",
            name="fk_erp_products_company_id",
        ),
        nullable=False,
        index=True,
    )
    branch_id = Column(
        Integer,
        ForeignKey(
            "public.branches.id",
            ondelete="SET NULL",
            onupdate="CASCADE",
            name="fk_erp_products_branch_id",
        ),
        nullable=True,
        index=True,
    )
    connection_id = Column(
        Integer,
        ForeignKey(
            "public.erp_connections.id",
            ondelete="CASCADE",
            onupdate="CASCADE",
            name="fk_erp_products_connection_id",
        ),
        nullable=False,
        index=True,
    )

    provider_type = Column(
        Enum(ERPProviderType, name="erpprovidertype", create_type=True),
        nullable=False,
        index=True,
    )
    external_id = Column(String(255), nullable=False, index=True)
    external_code = Column(String(255), nullable=True, index=True)

    name = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(255), nullable=True)

    unit_price = Column(Float, default=0.0, nullable=False)
    currency = Column(String(3), default="AZN", nullable=False)
    cost_price = Column(Float, nullable=True)

    tax_rate = Column(Float, default=0.0, nullable=False)
    barcode = Column(String(255), nullable=True, index=True)

    is_active = Column(Boolean, default=True, nullable=False)

    raw_data = Column(JSON, nullable=True)

    last_synced_at = Column(DateTime, nullable=False)
    created_at = Column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    connection = relationship("ERPConnection", back_populates="products")
    inventory_items = relationship(
        "ERPInventory",
        back_populates="product",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return (
            f"<ERPProduct(id={self.id}, name='{self.name}', "
            f"external_id='{self.external_id}')>"
        )


# ---------------------------------------------------------------------------
# 6. ERP Inventory
# ---------------------------------------------------------------------------

class ERPInventory(Base):
    """
    Inventory/stock levels synchronized from an external ERP.

    Tracks available, reserved, and incoming quantities with reorder
    thresholds per warehouse or location.
    """

    __tablename__ = "erp_inventory"
    __table_args__ = {
        "schema": "public",
        "comment": "Inventory levels synchronized from ERP systems",
    }

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    company_id = Column(
        Integer,
        ForeignKey(
            "public.companies.id",
            ondelete="CASCADE",
            onupdate="CASCADE",
            name="fk_erp_inventory_company_id",
        ),
        nullable=False,
        index=True,
    )
    branch_id = Column(
        Integer,
        ForeignKey(
            "public.branches.id",
            ondelete="SET NULL",
            onupdate="CASCADE",
            name="fk_erp_inventory_branch_id",
        ),
        nullable=True,
        index=True,
    )
    connection_id = Column(
        Integer,
        ForeignKey(
            "public.erp_connections.id",
            ondelete="CASCADE",
            onupdate="CASCADE",
            name="fk_erp_inventory_connection_id",
        ),
        nullable=False,
        index=True,
    )
    product_id = Column(
        Integer,
        ForeignKey(
            "public.erp_products.id",
            ondelete="SET NULL",
            onupdate="CASCADE",
            name="fk_erp_inventory_product_id",
        ),
        nullable=True,
        index=True,
    )

    provider_type = Column(
        Enum(ERPProviderType, name="erpprovidertype", create_type=True),
        nullable=False,
        index=True,
    )
    external_id = Column(String(255), nullable=False, index=True)
    external_warehouse_code = Column(String(255), nullable=True)

    quantity_available = Column(Float, default=0.0, nullable=False)
    quantity_reserved = Column(Float, default=0.0, nullable=False)
    quantity_incoming = Column(Float, default=0.0, nullable=False)

    reorder_level = Column(Float, nullable=True)
    reorder_quantity = Column(Float, nullable=True)

    last_synced_at = Column(DateTime, nullable=False)
    created_at = Column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    connection = relationship("ERPConnection", back_populates="inventory_items")
    product = relationship("ERPProduct", back_populates="inventory_items")

    def __repr__(self) -> str:
        return (
            f"<ERPInventory(id={self.id}, "
            f"quantity_available={self.quantity_available}, "
            f"external_id='{self.external_id}')>"
        )


# ---------------------------------------------------------------------------
# 7. ERP Sales Order
# ---------------------------------------------------------------------------

class ERPSalesOrder(Base):
    """
    Sales order data synchronized from an external ERP.

    Captures order lifecycle, customer references, financial totals,
    and delivery scheduling with raw audit snapshots.
    """

    __tablename__ = "erp_sales_orders"
    __table_args__ = {
        "schema": "public",
        "comment": "Sales orders synchronized from ERP systems",
    }

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    company_id = Column(
        Integer,
        ForeignKey(
            "public.companies.id",
            ondelete="CASCADE",
            onupdate="CASCADE",
            name="fk_erp_sales_orders_company_id",
        ),
        nullable=False,
        index=True,
    )
    branch_id = Column(
        Integer,
        ForeignKey(
            "public.branches.id",
            ondelete="SET NULL",
            onupdate="CASCADE",
            name="fk_erp_sales_orders_branch_id",
        ),
        nullable=True,
        index=True,
    )
    connection_id = Column(
        Integer,
        ForeignKey(
            "public.erp_connections.id",
            ondelete="CASCADE",
            onupdate="CASCADE",
            name="fk_erp_sales_orders_connection_id",
        ),
        nullable=False,
        index=True,
    )

    provider_type = Column(
        Enum(ERPProviderType, name="erpprovidertype", create_type=True),
        nullable=False,
        index=True,
    )
    external_id = Column(String(255), nullable=False, index=True)
    external_order_number = Column(String(255), nullable=True, index=True)

    customer_external_id = Column(String(255), nullable=True, index=True)
    customer_name = Column(String(255), nullable=True)

    order_date = Column(DateTime, nullable=False)
    delivery_date = Column(DateTime, nullable=True)

    total_amount = Column(Float, default=0.0, nullable=False)
    tax_amount = Column(Float, default=0.0, nullable=False)
    discount_amount = Column(Float, default=0.0, nullable=False)
    currency = Column(String(3), default="AZN", nullable=False)

    status = Column(String(50), nullable=False, index=True)
    payment_status = Column(String(50), nullable=False, index=True)

    raw_data = Column(JSON, nullable=True)

    last_synced_at = Column(DateTime, nullable=False)
    created_at = Column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    connection = relationship("ERPConnection", back_populates="sales_orders")
    invoices = relationship(
        "ERPInvoice",
        back_populates="sales_order",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return (
            f"<ERPSalesOrder(id={self.id}, "
            f"external_order_number='{self.external_order_number}', "
            f"status='{self.status}')>"
        )


# ---------------------------------------------------------------------------
# 8. ERP Customer
# ---------------------------------------------------------------------------

class ERPCustomer(Base):
    """
    Customer data synchronized from an external ERP.

    Mirrors the ERP customer/master data with contact info,
    tax details, credit limits, and classification.
    """

    __tablename__ = "erp_customers"
    __table_args__ = {
        "schema": "public",
        "comment": "Customers synchronized from ERP systems",
    }

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    company_id = Column(
        Integer,
        ForeignKey(
            "public.companies.id",
            ondelete="CASCADE",
            onupdate="CASCADE",
            name="fk_erp_customers_company_id",
        ),
        nullable=False,
        index=True,
    )
    branch_id = Column(
        Integer,
        ForeignKey(
            "public.branches.id",
            ondelete="SET NULL",
            onupdate="CASCADE",
            name="fk_erp_customers_branch_id",
        ),
        nullable=True,
        index=True,
    )
    connection_id = Column(
        Integer,
        ForeignKey(
            "public.erp_connections.id",
            ondelete="CASCADE",
            onupdate="CASCADE",
            name="fk_erp_customers_connection_id",
        ),
        nullable=False,
        index=True,
    )

    provider_type = Column(
        Enum(ERPProviderType, name="erpprovidertype", create_type=True),
        nullable=False,
        index=True,
    )
    external_id = Column(String(255), nullable=False, index=True)
    external_code = Column(String(255), nullable=True)

    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)
    tax_number = Column(String(50), nullable=True)
    address = Column(Text, nullable=True)
    city = Column(String(100), nullable=True)
    country = Column(String(100), default="Azerbaijan", nullable=False)

    customer_type = Column(String(50), nullable=False)
    credit_limit = Column(Float, nullable=True)

    is_active = Column(Boolean, default=True, nullable=False)

    raw_data = Column(JSON, nullable=True)
    last_synced_at = Column(DateTime, nullable=False)
    created_at = Column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    connection = relationship("ERPConnection", back_populates="customers")

    def __repr__(self) -> str:
        return (
            f"<ERPCustomer(id={self.id}, name='{self.name}', "
            f"external_id='{self.external_id}')>"
        )


# ---------------------------------------------------------------------------
# 9. ERP Invoice
# ---------------------------------------------------------------------------

class ERPInvoice(Base):
    """
    Invoice data synchronized from an external ERP.

    Captures billing documents linked to sales orders with
    financial breakdowns and status tracking.
    """

    __tablename__ = "erp_invoices"
    __table_args__ = {
        "schema": "public",
        "comment": "Invoices synchronized from ERP systems",
    }

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    company_id = Column(
        Integer,
        ForeignKey(
            "public.companies.id",
            ondelete="CASCADE",
            onupdate="CASCADE",
            name="fk_erp_invoices_company_id",
        ),
        nullable=False,
        index=True,
    )
    branch_id = Column(
        Integer,
        ForeignKey(
            "public.branches.id",
            ondelete="SET NULL",
            onupdate="CASCADE",
            name="fk_erp_invoices_branch_id",
        ),
        nullable=True,
        index=True,
    )
    connection_id = Column(
        Integer,
        ForeignKey(
            "public.erp_connections.id",
            ondelete="CASCADE",
            onupdate="CASCADE",
            name="fk_erp_invoices_connection_id",
        ),
        nullable=False,
        index=True,
    )
    sales_order_id = Column(
        Integer,
        ForeignKey(
            "public.erp_sales_orders.id",
            ondelete="SET NULL",
            onupdate="CASCADE",
            name="fk_erp_invoices_sales_order_id",
        ),
        nullable=True,
        index=True,
    )

    provider_type = Column(
        Enum(ERPProviderType, name="erpprovidertype", create_type=True),
        nullable=False,
        index=True,
    )
    external_id = Column(String(255), nullable=False, index=True)
    external_invoice_number = Column(String(255), nullable=True, index=True)

    customer_external_id = Column(String(255), nullable=True, index=True)
    customer_name = Column(String(255), nullable=True)

    invoice_date = Column(DateTime, nullable=False)
    due_date = Column(DateTime, nullable=True)

    subtotal = Column(Float, default=0.0, nullable=False)
    tax_amount = Column(Float, default=0.0, nullable=False)
    total_amount = Column(Float, default=0.0, nullable=False)
    currency = Column(String(3), default="AZN", nullable=False)

    status = Column(String(50), nullable=False, index=True)

    raw_data = Column(JSON, nullable=True)

    last_synced_at = Column(DateTime, nullable=False)
    created_at = Column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    connection = relationship("ERPConnection", back_populates="invoices")
    sales_order = relationship("ERPSalesOrder", back_populates="invoices")
    payments = relationship(
        "ERPPayment",
        back_populates="invoice",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return (
            f"<ERPInvoice(id={self.id}, "
            f"external_invoice_number='{self.external_invoice_number}', "
            f"status='{self.status}')>"
        )


# ---------------------------------------------------------------------------
# 10. ERP Payment
# ---------------------------------------------------------------------------

class ERPPayment(Base):
    """
    Payment data synchronized from an external ERP.

    Records payment transactions linked to invoices with
    method, amount, reference numbers, and status.
    """

    __tablename__ = "erp_payments"
    __table_args__ = {
        "schema": "public",
        "comment": "Payments synchronized from ERP systems",
    }

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    company_id = Column(
        Integer,
        ForeignKey(
            "public.companies.id",
            ondelete="CASCADE",
            onupdate="CASCADE",
            name="fk_erp_payments_company_id",
        ),
        nullable=False,
        index=True,
    )
    branch_id = Column(
        Integer,
        ForeignKey(
            "public.branches.id",
            ondelete="SET NULL",
            onupdate="CASCADE",
            name="fk_erp_payments_branch_id",
        ),
        nullable=True,
        index=True,
    )
    connection_id = Column(
        Integer,
        ForeignKey(
            "public.erp_connections.id",
            ondelete="CASCADE",
            onupdate="CASCADE",
            name="fk_erp_payments_connection_id",
        ),
        nullable=False,
        index=True,
    )
    invoice_id = Column(
        Integer,
        ForeignKey(
            "public.erp_invoices.id",
            ondelete="SET NULL",
            onupdate="CASCADE",
            name="fk_erp_payments_invoice_id",
        ),
        nullable=True,
        index=True,
    )

    provider_type = Column(
        Enum(ERPProviderType, name="erpprovidertype", create_type=True),
        nullable=False,
        index=True,
    )
    external_id = Column(String(255), nullable=False, index=True)

    customer_external_id = Column(String(255), nullable=True)
    payment_method = Column(String(50), nullable=False)

    amount = Column(Float, default=0.0, nullable=False)
    currency = Column(String(3), default="AZN", nullable=False)

    payment_date = Column(DateTime, nullable=False)
    reference_number = Column(String(255), nullable=True)
    notes = Column(Text, nullable=True)

    status = Column(String(50), nullable=False, index=True)

    raw_data = Column(JSON, nullable=True)

    last_synced_at = Column(DateTime, nullable=False)
    created_at = Column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    connection = relationship("ERPConnection", back_populates="payments")
    invoice = relationship("ERPInvoice", back_populates="payments")

    def __repr__(self) -> str:
        return (
            f"<ERPPayment(id={self.id}, amount={self.amount}, "
            f"method='{self.payment_method}', status='{self.status}')>"
        )
