"""
Branch Layout Manager
======================
Handles per-branch (şube) layout overrides and customization.
Each physical branch of a business can have its own pages, content,
style overrides, and section customizations while inheriting from the main site.
"""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from copy import deepcopy

from schemas.enums import IndustryType, SectionType
from schemas.site import Site
from schemas.page import Page
from schemas.section import Section
from schemas.blueprint import Blueprint, BlueprintPage


class BranchOverride(BaseModel):
    """Defines overrides for a specific branch."""
    branch_id: str = Field(..., description="Unique branch identifier")
    branch_name: str = Field(..., description="Human-readable branch name")
    branch_address: Optional[str] = None
    branch_phone: Optional[str] = None
    branch_email: Optional[str] = None

    # Page-level overrides
    enabled_pages: Optional[List[str]] = Field(None, description="Page IDs visible for this branch")
    disabled_pages: Optional[List[str]] = Field(None, description="Page IDs hidden for this branch")
    extra_pages: Optional[List[Dict[str, Any]]] = Field(None, description="Additional branch-specific pages")

    # Section-level overrides
    section_overrides: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict,
        description="section_id -> override dict (content, style, config)"
    )

    # Style overrides
    color_overrides: Optional[Dict[str, str]] = Field(None, description="Branch-specific colors")
    font_override: Optional[str] = None

    # Content overrides
    content_overrides: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict,
        description="section_type -> content override dict"
    )

    # Feature flags
    features: Optional[Dict[str, bool]] = None

    # Metadata
    manager_name: Optional[str] = None
    working_hours: Optional[str] = None
    google_maps_url: Optional[str] = None

    class Config:
        extra = "allow"


class BranchLayout(BaseModel):
    """
    A branch layout defines a complete website variation for a specific branch.
    It inherits from the main site and applies branch-specific overrides.
    """
    branch_id: str
    branch_name: str
    is_active: bool = True
    base_site_id: str
    overrides: BranchOverride

    # Computed/rendered
    rendered_pages: Optional[List[Page]] = None

    class Config:
        extra = "allow"


class BranchLayoutManager:
    """
    Manages branch layouts for a multi-branch business.
    Handles creation, storage, and application of branch-specific layouts.
    """

    def __init__(self):
        self._layouts: Dict[str, BranchLayout] = {}
        self._branch_overrides: Dict[str, BranchOverride] = {}

    # ── Layout CRUD ────────────────────────────────────────────

    def register_branch(self, override: BranchOverride) -> "BranchLayoutManager":
        """Register a branch override configuration."""
        self._branch_overrides[override.branch_id] = override
        return self

    def create_layout(self, branch_id: str, base_site_id: str, branch_name: str) -> BranchLayout:
        """Create a new branch layout."""
        overrides = self._branch_overrides.get(branch_id, BranchOverride(
            branch_id=branch_id,
            branch_name=branch_name,
        ))
        layout = BranchLayout(
            branch_id=branch_id,
            branch_name=branch_name,
            base_site_id=base_site_id,
            overrides=overrides,
        )
        self._layouts[branch_id] = layout
        return layout

    def get_layout(self, branch_id: str) -> Optional[BranchLayout]:
        """Get a branch layout by ID."""
        return self._layouts.get(branch_id)

    def list_branches(self) -> List[str]:
        """List all registered branch IDs."""
        return list(self._layouts.keys())

    def remove_branch(self, branch_id: str) -> bool:
        """Remove a branch layout."""
        if branch_id in self._layouts:
            del self._layouts[branch_id]
            return True
        return False

    # ── Site Rendering ─────────────────────────────────────────

    def render_branch_site(self, base_site: Site, branch_id: str) -> Site:
        """
        Render a branch-specific version of a site by applying overrides.

        Args:
            base_site: The main site configuration
            branch_id: The branch to render for

        Returns:
            A new Site instance with branch overrides applied
        """
        layout = self._layouts.get(branch_id)
        if layout is None:
            return base_site

        overrides = layout.overrides

        # Deep copy the base site
        branch_site = Site.from_dict(deepcopy(base_site.to_dict()))

        # Apply branch identity
        branch_site.id = f"{base_site.id}_{branch_id}"
        if overrides.branch_name:
            branch_site.meta.site_name = overrides.branch_name
        if overrides.branch_address:
            branch_site.meta.address = overrides.branch_address
        if overrides.branch_phone:
            branch_site.meta.contact_phone = overrides.branch_phone
        if overrides.branch_email:
            branch_site.meta.contact_email = overrides.branch_email

        # Apply color overrides
        if overrides.color_overrides:
            for key, value in overrides.color_overrides.items():
                setattr(branch_site.config, key, value)

        # Apply font override
        if overrides.font_override:
            branch_site.config.font_pair = overrides.font_override

        # Filter pages
        if overrides.enabled_pages:
            branch_site.pages = [
                p for p in branch_site.pages
                if p.id in overrides.enabled_pages
            ]
        if overrides.disabled_pages:
            branch_site.pages = [
                p for p in branch_site.pages
                if p.id not in overrides.disabled_pages
            ]

        # Apply section overrides
        for page in branch_site.pages:
            for section in page.sections:
                section_key = section.id or section.type.value
                if section_key in overrides.section_overrides:
                    sec_override = overrides.section_overrides[section_key]
                    if "content" in sec_override:
                        section.content.update(sec_override["content"])
                    if "style" in sec_override:
                        for k, v in sec_override["style"].items():
                            setattr(section.style, k, v)
                    if "config" in sec_override:
                        for k, v in sec_override["config"].items():
                            setattr(section.config, k, v)

        # Apply content overrides by section type
        for page in branch_site.pages:
            for section in page.sections:
                type_key = section.type.value
                if type_key in overrides.content_overrides:
                    section.content.update(overrides.content_overrides[type_key])

        # Update feature flags
        if overrides.features:
            for key, value in overrides.features.items():
                # This would update the blueprint or site config
                pass

        return branch_site

    def render_all_branches(self, base_site: Site) -> Dict[str, Site]:
        """Render sites for all registered branches."""
        return {
            branch_id: self.render_branch_site(base_site, branch_id)
            for branch_id in self._layouts.keys()
        }

    # ── Blueprint Integration ──────────────────────────────────

    def generate_branch_blueprint(
        self,
        base_blueprint: Blueprint,
        branch_id: str,
    ) -> Blueprint:
        """
        Generate a branch-specific blueprint from a base blueprint.
        """
        layout = self._layouts.get(branch_id)
        if layout is None:
            return base_blueprint

        overrides = layout.overrides
        branch_blueprint = Blueprint.from_dict(deepcopy(base_blueprint.to_dict()))

        # Apply branch name
        if overrides.branch_name:
            branch_blueprint.business_name = overrides.branch_name

        # Filter pages in blueprint
        if overrides.enabled_pages:
            branch_blueprint.pages = [
                p for p in branch_blueprint.pages
                if p.page_id in overrides.enabled_pages
            ]

        # Apply content overrides to blueprint pages
        for bp_page in branch_blueprint.pages:
            for bp_section in bp_page.sections:
                type_key = bp_section.section_type.value
                if type_key in overrides.content_overrides:
                    bp_section.content_guidelines = str(overrides.content_overrides[type_key])

        return branch_blueprint

    # ── Validation ─────────────────────────────────────────────

    def validate_layout(self, branch_id: str, base_site: Site) -> List[str]:
        """Validate a branch layout against a base site. Returns list of issues."""
        issues = []
        layout = self._layouts.get(branch_id)
        if layout is None:
            return [f"Layout for branch '{branch_id}' not found"]

        overrides = layout.overrides

        # Check enabled pages exist
        if overrides.enabled_pages:
            site_page_ids = {p.id for p in base_site.pages}
            for pid in overrides.enabled_pages:
                if pid not in site_page_ids:
                    issues.append(f"Enabled page '{pid}' not found in base site")

        # Check section override IDs exist
        for page in base_site.pages:
            section_ids = {s.id for s in page.sections if s.id}
            for sid in overrides.section_overrides.keys():
                if sid not in section_ids:
                    issues.append(f"Section override '{sid}' not found in any page")

        return issues


# Singleton
_manager_instance: Optional[BranchLayoutManager] = None


def get_layout_manager() -> BranchLayoutManager:
    """Get the singleton BranchLayoutManager instance."""
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = BranchLayoutManager()
    return _manager_instance


# ── Convenience Functions ────────────────────────────────────

def create_branch_layout(
    branch_id: str,
    branch_name: str,
    base_site_id: str,
    overrides: Optional[Dict[str, Any]] = None,
) -> BranchLayout:
    """Convenience function to create a branch layout."""
    manager = get_layout_manager()
    branch_override = BranchOverride(
        branch_id=branch_id,
        branch_name=branch_name,
        **(overrides or {})
    )
    manager.register_branch(branch_override)
    return manager.create_layout(branch_id, base_site_id, branch_name)


def apply_branch_layout(site: Site, branch_id: str) -> Site:
    """Convenience function to apply a branch layout to a site."""
    manager = get_layout_manager()
    return manager.render_branch_site(site, branch_id)
