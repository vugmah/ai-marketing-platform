"""Revenue Intelligence Layer models - Phase 5."""

from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Numeric, JSON, ForeignKey, Index
from sqlalchemy.sql import func

from app.database import Base


class CampaignRevenueCorrelation(Base):
    """Campaign ROI to sales correlation."""
    __tablename__ = "campaign_revenue_correlations"
    __table_args__ = (
        Index("ix_crc_campaign", "campaign_id"),
        Index("ix_crc_company", "company_id"),
        {"schema": "public", "comment": "Campaign-to-revenue attribution"},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, nullable=False, index=True)
    branch_id = Column(Integer, nullable=True, index=True)
    campaign_id = Column(Integer, nullable=False, index=True)
    campaign_type = Column(String(50), nullable=False)
    period = Column(String(10), nullable=False)  # daily, weekly, monthly
    campaign_spend = Column(Numeric(12, 2), nullable=False, default=0)
    attributed_revenue = Column(Numeric(12, 2), nullable=False, default=0)
    attributed_orders = Column(Integer, nullable=False, default=0)
    attributed_customers = Column(Integer, nullable=False, default=0)
    roi_pct = Column(Numeric(7, 2), nullable=False, default=0)
    cost_per_acquisition = Column(Numeric(10, 2), nullable=False, default=0)
    correlation_strength = Column(Numeric(3, 2), nullable=False, default=0)  # 0-1
    created_at = Column(DateTime, server_default=func.now(), nullable=False)


class BranchRevenueAttribution(Base):
    """Branch-level revenue attribution."""
    __tablename__ = "branch_revenue_attributions"
    __table_args__ = (
        Index("ix_bra_branch", "branch_id"),
        Index("ix_bra_company", "company_id"),
        {"schema": "public", "comment": "Branch revenue attribution"},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, nullable=False, index=True)
    branch_id = Column(Integer, nullable=False, index=True)
    date = Column(String(10), nullable=False)
    total_revenue = Column(Numeric(12, 2), nullable=False, default=0)
    campaign_attributed_revenue = Column(Numeric(12, 2), nullable=False, default=0)
    organic_revenue = Column(Numeric(12, 2), nullable=False, default=0)
    social_media_attributed = Column(Numeric(12, 2), nullable=False, default=0)
    ad_spend = Column(Numeric(12, 2), nullable=False, default=0)
    profit_margin_pct = Column(Numeric(5, 2), nullable=False, default=0)
    customer_count = Column(Integer, nullable=False, default=0)
    avg_order_value = Column(Numeric(10, 2), nullable=False, default=0)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)


class InventoryCampaignAnalysis(Base):
    """Inventory-to-campaign analysis."""
    __tablename__ = "inventory_campaign_analysis"
    __table_args__ = (
        Index("ix_ica_product", "product_id"),
        Index("ix_ica_company", "company_id"),
        {"schema": "public", "comment": "Inventory campaign effectiveness"},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, nullable=False, index=True)
    branch_id = Column(Integer, nullable=True, index=True)
    product_id = Column(Integer, nullable=False, index=True)
    product_name = Column(String(255), nullable=False)
    campaign_id = Column(Integer, nullable=False, index=True)
    pre_campaign_stock = Column(Integer, nullable=False, default=0)
    post_campaign_stock = Column(Integer, nullable=False, default=0)
    units_sold = Column(Integer, nullable=False, default=0)
    stock_turnover_rate = Column(Numeric(5, 2), nullable=False, default=0)
    campaign_lift_pct = Column(Numeric(7, 2), nullable=False, default=0)
    revenue_generated = Column(Numeric(12, 2), nullable=False, default=0)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)


class PromotionEffectiveness(Base):
    """Promotion effectiveness tracking."""
    __tablename__ = "promotion_effectiveness"
    __table_args__ = (
        Index("ix_pe_promo", "promotion_id"),
        Index("ix_pe_company", "company_id"),
        {"schema": "public", "comment": "Promotion effectiveness metrics"},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, nullable=False, index=True)
    branch_id = Column(Integer, nullable=True, index=True)
    promotion_id = Column(Integer, nullable=False, index=True)
    promotion_type = Column(String(50), nullable=False)  # discount, bundle, free_shipping, coupon
    discount_pct = Column(Numeric(5, 2), nullable=False, default=0)
    revenue_lift_pct = Column(Numeric(7, 2), nullable=False, default=0)
    units_lift_pct = Column(Numeric(7, 2), nullable=False, default=0)
    customer_lift_pct = Column(Numeric(7, 2), nullable=False, default=0)
    margin_impact_pct = Column(Numeric(6, 2), nullable=False, default=0)
    cannibalization_pct = Column(Numeric(5, 2), nullable=False, default=0)
    overall_score = Column(Numeric(5, 2), nullable=False, default=0)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)


class CustomerLifetimeValue(Base):
    """Customer lifetime value foundation."""
    __tablename__ = "customer_lifetime_values"
    __table_args__ = (
        Index("ix_clv_customer", "customer_id"),
        Index("ix_clv_company", "company_id"),
        {"schema": "public", "comment": "Customer lifetime value tracking"},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, nullable=False, index=True)
    branch_id = Column(Integer, nullable=True, index=True)
    customer_id = Column(Integer, nullable=False, index=True)
    total_orders = Column(Integer, nullable=False, default=0)
    total_revenue = Column(Numeric(12, 2), nullable=False, default=0)
    total_visits = Column(Integer, nullable=False, default=0)
    avg_order_value = Column(Numeric(10, 2), nullable=False, default=0)
    first_order_date = Column(DateTime, nullable=True)
    last_order_date = Column(DateTime, nullable=True)
    predicted_ltv = Column(Numeric(12, 2), nullable=True)
    predicted_ltv_confidence = Column(Numeric(4, 3), nullable=False, default=0.0)
    churn_risk = Column(String(20), nullable=False, default="unknown")
    days_since_last_order = Column(Integer, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
