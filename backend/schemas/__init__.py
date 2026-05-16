"""
Website Builder Schemas Package
================================
Pydantic-based schemas for AI-powered website generation.
Supports section-based page composition with branch-specific layouts.
"""

from .section import Section, SectionType, SectionConfig, SectionStyle
from .page import Page, PageMeta, PageNavigation
from .site import Site, SiteConfig, SiteMeta, SiteNavigation, SiteAnalytics
from .blueprint import Blueprint, BlueprintPage, BlueprintSection, BlueprintRecommendation
from .enums import (
    IndustryType,
    BusinessSize,
    ColorScheme,
    FontPair,
    AnimationLevel,
    DeviceTarget,
)

__all__ = [
    "Section",
    "SectionType",
    "SectionConfig",
    "SectionStyle",
    "Page",
    "PageType",
    "PageMeta",
    "PageNavigation",
    "Site",
    "SiteConfig",
    "SiteMeta",
    "SiteNavigation",
    "SiteAnalytics",
    "Blueprint",
    "BlueprintPage",
    "BlueprintSection",
    "BlueprintRecommendation",
    "IndustryType",
    "BusinessSize",
    "ColorScheme",
    "FontPair",
    "AnimationLevel",
    "DeviceTarget",
]
