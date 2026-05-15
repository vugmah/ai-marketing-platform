"""
ERP Integration module.

Provides models and services for synchronizing data with external ERP systems
including products, inventory, sales orders, customers, invoices, and payments.

Supported providers: custom, odoo, sap, netsuite, dynamics, logo, mikro, parasut, 1c.
"""

from app.erp.router import router as erp_router
