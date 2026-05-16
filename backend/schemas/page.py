"""
Page schema - composed of sections with navigation and SEO metadata.
"""

from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field

from .section import Section
from .enums import SectionType


class PageMeta(BaseModel):
    """SEO and social metadata for a page."""
    title: Optional[str] = Field(None, description="Page <title>")
    description: Optional[str] = Field(None, description="Meta description")
    keywords: Optional[List[str]] = Field(None, description="Meta keywords")
    og_title: Optional[str] = Field(None, description="Open Graph title")
    og_description: Optional[str] = Field(None, description="Open Graph description")
    og_image: Optional[str] = Field(None, description="Open Graph image URL")
    canonical_url: Optional[str] = Field(None, description="Canonical URL")
    no_index: bool = Field(False, description="Prevent search indexing")
    schema_org: Optional[Dict[str, Any]] = Field(None, description="Schema.org structured data")
    custom_head: Optional[str] = Field(None, description="Custom HTML for <head>")

    class Config:
        extra = "allow"


class PageNavigation(BaseModel):
    """Navigation settings for a page."""
    label: Optional[str] = Field(None, description="Nav menu label")
    icon: Optional[str] = Field(None, description="Optional nav icon name/URL")
    show_in_nav: bool = Field(True, description="Show in main navigation")
    show_in_footer: bool = Field(False, description="Show in footer links")
    nav_order: int = Field(0, description="Navigation sort order")
    parent_id: Optional[str] = Field(None, description="Parent page ID for dropdowns")
    dropdown_items: Optional[List[Dict[str, str]]] = Field(None, description="Dropdown children")

    class Config:
        extra = "allow"


class Page(BaseModel):
    """
    A page is composed of ordered sections.
    Each page has its own routing, SEO meta, and navigation config.
    """
    id: str = Field(..., description="Unique page ID (used in URL slug)")
    name: str = Field(..., description="Human-readable page name")
    slug: str = Field(..., description="URL path (e.g., 'about', 'services')")
    is_homepage: bool = Field(False, description="Whether this is the homepage")
    is_visible: bool = Field(True, description="Page is publicly accessible")
    is_locked: bool = Field(False, description="Prevent structural edits")

    # Composition
    sections: List[Section] = Field(default_factory=list)

    # SEO & Navigation
    meta: PageMeta = Field(default_factory=PageMeta)
    navigation: PageNavigation = Field(default_factory=PageNavigation)

    # Layout overrides
    layout_template: str = Field("default", description="Named layout template")
    header_override: Optional[str] = Field(None, description="Override header section ID")
    footer_override: Optional[str] = Field(None, description="Override footer section ID")

    # Style overrides
    page_style: Optional[Dict[str, Any]] = Field(None, description="Page-level CSS overrides")

    # Metadata
    meta_info: Optional[Dict[str, Any]] = Field(None, description="Editor metadata")

    class Config:
        extra = "allow"

    def to_dict(self) -> Dict[str, Any]:
        """Serialize page to plain dict."""
        return self.model_dump(mode="json", exclude_none=True)

    def to_json(self, indent: Optional[int] = None) -> str:
        """Serialize page to JSON string."""
        import json
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Page":
        """Create Page from a dictionary."""
        sections_data = data.pop("sections", [])
        sections = [Section.from_dict(s) for s in sections_data]
        return cls(sections=sections, **data)

    @classmethod
    def create(cls, page_id: str, name: str, slug: str, sections: Optional[List[Section]] = None, **kwargs) -> "Page":
        """Factory method for quick page creation."""
        return cls(id=page_id, name=name, slug=slug, sections=sections or [], **kwargs)

    def add_section(self, section: Section) -> "Page":
        """Add a section to the page."""
        self.sections.append(section)
        self.sections.sort(key=lambda s: s.order)
        return self

    def get_section_by_type(self, section_type: SectionType) -> Optional[Section]:
        """Find first section by type."""
        for section in self.sections:
            if section.type == section_type:
                return section
        return None

    def get_sections_by_type(self, section_type: SectionType) -> List[Section]:
        """Find all sections by type."""
        return [s for s in self.sections if s.type == section_type]

    def remove_section(self, section_id: str) -> bool:
        """Remove a section by ID. Returns True if found and removed."""
        for i, s in enumerate(self.sections):
            if s.id == section_id:
                self.sections.pop(i)
                return True
        return False

    def reorder_sections(self) -> "Page":
        """Reassign section orders sequentially."""
        for i, section in enumerate(sorted(self.sections, key=lambda s: s.order)):
            section.order = i
        return self
