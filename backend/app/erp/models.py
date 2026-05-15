"""
ERP synchronization models.

Defines the database schema for ERP connections, sync jobs, and synced entities
(products, inventory, sales orders, customers, invoices, payments).
"""

import enum
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    JSON,
)
from sqlalchemy.orm import relationship

from app.database import Base


class SyncStatus(str, enum.Enum):
    """Sync job lifecycle statuses."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SyncTrigger(str, enum.Enum):
    """How the sync job was triggered."""

    MANUAL = "manual"
    SCHEDULED = "scheduled"
    WEBHOOK = "webhook"
    RETRY = "retry"


class ERPConnection(Base):
    """
    ERP system connection configuration.

    Each connection links a company/branch to an external ERP system.
    Stores credentials (encrypted), endpoint configuration, and sync state.
    """

    __tablename__ = "erp_connections"
    __table_args__ = {"schema": "public", "comment": "ERP system connections"}

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # Tenant
    company_id = Column(Integer, ForeignKey("public.companies.id"), nullable=False)
    branch_id = Column(Integer, ForeignKey("public.branches.id"), nullable=True)

    # ERP system info
    name = Column(String(255), nullable=False, comment="User-defined connection name")
    provider_type = Column(String(50), nullable=False, comment="ERP provider: custom, odoo, sap, netsuite")
    base_url = Column(String(500), nullable=False, comment="ERP API base URL")
    api_key = Column(String(500), nullable=True, comment="API key or OAuth token")
    api_secret = Column(String(500), nullable=True, comment="API secret or refresh token")

    # Sync configuration
    sync_enabled = Column(Boolean, default=True, nullable=False)
    sync_interval_minutes = Column(Integer, default=60, nullable=False)
    sync_entities = Column(JSON, default=list, nullable=False, comment="List of entity types to sync")

    # Field mappings (ERP field -> our field)
    field_mappings = Column(JSON, default=dict, nullable=True)

    # Webhook configuration
    webhook_url = Column(String(500), nullable=True)
    webhook_secret = Column(String(255), nullable=True)

    # Sync state
    last_sync_at = Column(DateTime, nullable=True)
    last_sync_status = Column(String(20), nullable=True)
    last_sync_error = Column(Text, nullable=True)

    # Status & timestamps
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"<ERPConnection(id={self.id}, name='{self.name}', "
            f"provider='{self.provider_type}')>"
        )


class ERPSyncJob(Base):
    """
    Individual sync job execution record.

    Tracks each sync run: when it started, what it synced,
    how many records were processed, and the outcome.
    """

    __tablename__ = "erp_sync_jobs"
    __table_args__ = {"schema": "public", "comment": "ERP sync job executions"}

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # FK to connection
    connection_id = Column(
        Integer,
        ForeignKey("public.erp_connections.id"),
        nullable=False,
    )

    # Job details
    entity_type = Column(String(50), nullable=False, comment="Entity: products, inventory, all, etc.")
    sync_type = Column(String(20), nullable=False, default="incremental", comment="incremental or full")
    trigger = Column(String(20), nullable=False, default=SyncTrigger.MANUAL)

    # Status
    status = Column(String(20), nullable=False, default=SyncStatus.PENDING)

    # Results
    records_processed = Column(Integer, default=0, nullable=False)
    records_failed = Column(Integer, default=0, nullable=False)
    error_message = Column(Text, nullable=True)

    # Timing
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # Raw log
    logs = Column(JSON, default=list, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    connection = relationship("ERPConnection", lazy="selectin")

    def __repr__(self) -> str:
        return (
            f"<ERPSyncJob(id={self.id}, connection_id={self.connection_id}, "
            f"entity='{self.entity_type}', status='{self.status}')>"
        )


class ERPProduct(Base):
    """
    Product synced from an ERP system.

    Mirrors the product data from the external ERP with raw_data
    preserving the original response for debugging.
    """

    __tablename__ = "erp_products"
    __table_args__ = {"schema": "public", "comment": "Products synced from ERP"}

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # Tenant
    company_id = Column(Integer, ForeignKey("public.companies.id"), nullable=False)
    branch_id = Column(Integer, ForeignKey("public.branches.id"), nullable=True)

    # Connection
    connection_id = Column(
        Integer,
        ForeignKey("public.erp_connections.id"),
        nullable=False,
        index=True,
    )
    provider_type = Column(String(50), nullable=False)

    # External reference
    external_id = Column(String(255), nullable=False, comment="Product ID in the ERP")
    external_code = Column(String(255), nullable=True, comment="SKU or product code in ERP")

    # Product data
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(255), nullable=True)
    unit_price = Column(Float, default=0.0, nullable=True)
    cost_price = Column(Float, nullable=True)
    tax_rate = Column(Float, default=0.0, nullable=True)
    barcode = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    # Raw ERP data
    raw_data = Column(Text, nullable=True, comment="Original JSON from ERP")

    # Sync metadata
    last_synced_at = Column(DateTime, nullable=True)
    sync_status = Column(String(20), default="synced", nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<ERPProduct(id={self.id}, name='{self.name}', ext_id='{self.external_id}')>"


class ERPInventory(Base):
    """Inventory/stock levels synced from an ERP system."""

    __tablename__ = "erp_inventory"
    __table_args__ = {"schema": "public", "comment": "Inventory levels synced from ERP"}

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    company_id = Column(Integer, ForeignKey("public.companies.id"), nullable=False)
    branch_id = Column(Integer, ForeignKey("public.branches.id"), nullable=True)
    connection_id = Column(
        Integer,
        ForeignKey("public.erp_connections.id"),
        nullable=False,
    )

    external_product_id = Column(String(255), nullable=False)
    warehouse_code = Column(String(100), nullable=True)
    quantity_on_hand = Column(Float, default=0.0, nullable=False)
    quantity_reserved = Column(Float, default=0.0, nullable=False)
    quantity_available = Column(Float, default=0.0, nullable=False)

    raw_data = Column(Text, nullable=True)
    last_synced_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )


class ERPSalesOrder(Base):
    """Sales orders synced from an ERP system."""

    __tablename__ = "erp_sales_orders"
    __table_args__ = {"schema": "public", "comment": "Sales orders synced from ERP"}

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    company_id = Column(Integer, ForeignKey("public.companies.id"), nullable=False)
    branch_id = Column(Integer, ForeignKey("public.branches.id"), nullable=True)
    connection_id = Column(
        Integer,
        ForeignKey("public.erp_connections.id"),
        nullable=False,
    )

    external_id = Column(String(255), nullable=False)
    external_customer_id = Column(String(255), nullable=True)

    order_number = Column(String(100), nullable=True)
    order_date = Column(DateTime, nullable=True)
    status = Column(String(50), nullable=True)
    total_amount = Column(Float, default=0.0, nullable=True)
    currency = Column(String(3), default="AZN", nullable=True)

    raw_data = Column(Text, nullable=True)
    last_synced_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )


class ERPCustomer(Base):
    """Customers synced from an ERP system."""

    __tablename__ = "erp_customers"
    __table_args__ = {"schema": "public", "comment": "Customers synced from ERP"}

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    company_id = Column(Integer, ForeignKey("public.companies.id"), nullable=False)
    branch_id = Column(Integer, ForeignKey("public.branches.id"), nullable=True)
    connection_id = Column(
        Integer,
        ForeignKey("public.erp_connections.id"),
        nullable=False,
    )

    external_id = Column(String(255), nullable=False)
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)
    tax_number = Column(String(50), nullable=True)
    address = Column(Text, nullable=True)
    customer_type = Column(String(50), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    raw_data = Column(Text, nullable=True)
    last_synced_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )


class ERPInvoice(Base):
    """Invoices synced from an ERP system."""

    __tablename__ = "erp_invoices"
    __table_args__ = {"schema": "public", "comment": "Invoices synced from ERP"}

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    company_id = Column(Integer, ForeignKey("public.companies.id"), nullable=False)
    branch_id = Column(Integer, ForeignKey("public.branches.id"), nullable=True)
    connection_id = Column(
        Integer,
        ForeignKey("public.erp_connections.id"),
        nullable=False,
    )

    external_id = Column(String(255), nullable=False)
    external_order_id = Column(String(255), nullable=True)
    invoice_number = Column(String(100), nullable=True)
    invoice_date = Column(DateTime, nullable=True)
    due_date = Column(DateTime, nullable=True)
    status = Column(String(50), nullable=True)
    total_amount = Column(Float, default=0.0, nullable=True)
    paid_amount = Column(Float, default=0.0, nullable=True)
    currency = Column(String(3), default="AZN", nullable=True)

    raw_data = Column(Text, nullable=True)
    last_synced_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )


class ERPPayment(Base):
    """Payments synced from an ERP system."""

    __tablename__ = "erp_payments"
    __table_args__ = {"schema": "public", "comment": "Payments synced from ERP"}

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    company_id = Column(Integer, ForeignKey("public.companies.id"), nullable=False)
    branch_id = Column(Integer, ForeignKey("public.branches.id"), nullable=True)
    connection_id = Column(
        Integer,
        ForeignKey("public.erp_connections.id"),
        nullable=False,
    )

    external_id = Column(String(255), nullable=False)
    external_invoice_id = Column(String(255), nullable=True)
    payment_date = Column(DateTime, nullable=True)
    amount = Column(Float, default=0.0, nullable=True)
    currency = Column(String(3), default="AZN", nullable=True)
    payment_method = Column(String(50), nullable=True)
    status = Column(String(50), nullable=True)
    reference = Column(String(255), nullable=True)

    raw_data = Column(Text, nullable=True)
    last_synced_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )
