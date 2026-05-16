"""
Section schema - the atomic building block of pages.
Each section is self-contained with its own config, style, and content.
"""

from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field

from .enums import SectionType, AnimationLevel


class SectionStyle(BaseModel):
    """Visual styling overrides for a section."""
    background_color: Optional[str] = Field(None, description="Hex or CSS color")
    background_image: Optional[str] = Field(None, description="URL to background image")
    background_gradient: Optional[str] = Field(None, description="CSS gradient string")
    text_color: Optional[str] = Field(None, description="Primary text color")
    accent_color: Optional[str] = Field(None, description="Accent/highlight color")
    padding_top: Optional[str] = Field(None, description="Top padding (e.g., '80px')")
    padding_bottom: Optional[str] = Field(None, description="Bottom padding")
    padding_horizontal: Optional[str] = Field(None, description="Horizontal padding")
    max_width: Optional[str] = Field("1200px", description="Content max width")
    full_width: bool = Field(False, description="Full viewport width")
    custom_css: Optional[str] = Field(None, description="Arbitrary CSS overrides")
    class_name: Optional[str] = Field(None, description="Additional CSS class names")

    class Config:
        extra = "allow"


class SectionConfig(BaseModel):
    """Configuration parameters for a section instance."""
    # Layout
    layout_variant: str = Field("default", description="Named layout variant")
    columns: int = Field(1, ge=1, le=6, description="Number of columns")
    alignment: str = Field("center", description="Text/content alignment")
    reverse_order: bool = Field(False, description="Reverse visual order")
    show_divider: bool = Field(False, description="Show section divider")

    # Content display
    show_title: bool = Field(True)
    show_subtitle: bool = Field(True)
    show_description: bool = Field(True)
    show_button: bool = Field(True)
    show_image: bool = Field(True)
    show_icon: bool = Field(False)
    show_border: bool = Field(False)
    show_shadow: bool = Field(False)
    item_count: int = Field(3, ge=1, le=12, description="Max items to display")

    # Animation
    animation_level: AnimationLevel = Field(AnimationLevel.SUBTLE)
    animation_delay: Optional[float] = Field(None, description="Delay in seconds")
    animation_duration: Optional[float] = Field(None, description="Duration in seconds")

    # Interaction
    clickable: bool = Field(False)
    hover_effect: bool = Field(True)
    carousel_enabled: bool = Field(False)
    carousel_autoplay: bool = Field(False)
    carousel_interval: int = Field(5000, description="Autoplay interval ms")

    # SEO
    heading_tag: str = Field("h2", description="HTML heading tag (h1-h6)")
    section_id: Optional[str] = Field(None, description="HTML ID for anchor links")

    class Config:
        extra = "allow"


class Section(BaseModel):
    """
    A section is a self-contained block of a webpage.
    Sections compose pages and carry their own style, config, and content.
    """
    id: Optional[str] = Field(None, description="Unique section instance ID")
    type: SectionType = Field(..., description="Section type from SectionType enum")
    name: Optional[str] = Field(None, description="Human-readable section name")
    order: int = Field(0, ge=0, description="Display order within page")
    is_visible: bool = Field(True, description="Whether section is rendered")
    is_locked: bool = Field(False, description="Prevent editing if True")

    # Core composition
    style: SectionStyle = Field(default_factory=SectionStyle)
    config: SectionConfig = Field(default_factory=SectionConfig)
    content: Dict[str, Any] = Field(default_factory=dict, description="Section-specific content data")

    # Conditional rendering
    conditions: Optional[Dict[str, Any]] = Field(None, description="Conditional display rules")

    # Metadata
    meta: Optional[Dict[str, Any]] = Field(None, description="Editor metadata, analytics tags")

    class Config:
        extra = "allow"

    def to_dict(self) -> Dict[str, Any]:
        """Serialize section to plain dict."""
        return self.model_dump(mode="json", exclude_none=True)

    def to_json(self, indent: Optional[int] = None) -> str:
        """Serialize section to JSON string."""
        import json
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Section":
        """Create Section from a dictionary."""
        return cls(**data)

    @classmethod
    def create(cls, section_type: SectionType, order: int = 0, **kwargs) -> "Section":
        """Factory method for quick section creation."""
        return cls(type=section_type, order=order, **kwargs)
