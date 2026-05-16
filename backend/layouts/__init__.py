"""
Branch-based Layouts Package
=============================
Manages per-branch (şube) website layouts and configuration overrides.
Each branch can have its own pages, sections, style overrides, and content customizations.
"""

from .branch_layout import (
    BranchLayout,
    BranchLayoutManager,
    get_layout_manager,
    create_branch_layout,
    apply_branch_layout,
)
from .industry_layouts import (
    get_industry_layout,
    get_restaurant_layout,
    get_cafe_layout,
    get_retail_layout,
    get_healthcare_layout,
    get_fitness_layout,
    get_salon_layout,
    get_hotel_layout,
    get_technology_layout,
    get_construction_layout,
)

__all__ = [
    "BranchLayout",
    "BranchLayoutManager",
    "get_layout_manager",
    "create_branch_layout",
    "apply_branch_layout",
    "get_industry_layout",
    "get_restaurant_layout",
    "get_cafe_layout",
    "get_retail_layout",
    "get_healthcare_layout",
    "get_fitness_layout",
    "get_salon_layout",
    "get_hotel_layout",
    "get_technology_layout",
    "get_construction_layout",
]
