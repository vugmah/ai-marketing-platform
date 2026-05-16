"""
AI Website Builder Foundation Package
======================================
Core foundation for an AI-powered website builder system.
Provides blueprint generation, section composition, and site assembly.
"""

from .blueprint_generator import (
    BlueprintGenerator,
    get_blueprint_generator,
    GenerationContext,
)
from .site_assembler import (
    SiteAssembler,
    get_site_assembler,
    AssemblyConfig,
)
from .content_generator import (
    ContentGenerator,
    get_content_generator,
    ContentGenerationRequest,
)
from .validation import (
    BlueprintValidator,
    get_blueprint_validator,
    ValidationResult,
    ValidationRule,
)

__all__ = [
    "BlueprintGenerator",
    "get_blueprint_generator",
    "GenerationContext",
    "SiteAssembler",
    "get_site_assembler",
    "AssemblyConfig",
    "ContentGenerator",
    "get_content_generator",
    "ContentGenerationRequest",
    "BlueprintValidator",
    "get_blueprint_validator",
    "ValidationResult",
    "ValidationRule",
]
