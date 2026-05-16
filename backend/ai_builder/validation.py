"""
Blueprint & Site Validation
============================
Validates blueprints and assembled sites against rules and best practices.
Ensures structural integrity, SEO compliance, and accessibility standards.
"""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from enum import Enum

from schemas.enums import IndustryType, SectionType
from schemas.blueprint import Blueprint, BlueprintPage, BlueprintSection
from schemas.site import Site
from schemas.page import Page
from schemas.section import Section


class ValidationSeverity(str, Enum):
    """Validation issue severity levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class ValidationRule(BaseModel):
    """A validation rule definition."""
    rule_id: str
    name: str
    description: str
    severity: ValidationSeverity
    check_fn_name: str  # Name of the method to call
    applies_to: List[str] = Field(default_factory=list)  # "blueprint", "site", "page", "section"

    class Config:
        extra = "allow"


class ValidationIssue(BaseModel):
    """A single validation issue."""
    rule_id: str
    severity: ValidationSeverity
    message: str
    target: str  # What the issue applies to (e.g., "page:home")
    suggestion: Optional[str] = None

    class Config:
        extra = "allow"


class ValidationResult(BaseModel):
    """Result of a validation run."""
    is_valid: bool
    total_issues: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    info_count: int
    issues: List[ValidationIssue]
    summary: str

    class Config:
        extra = "allow"


class BlueprintValidator:
    """
    Validates website blueprints and assembled sites.
    Checks structural integrity, SEO compliance, and best practices.
    """

    # Standard validation rules
    RULES: List[ValidationRule] = [
        ValidationRule(
            rule_id="STRUCT-001",
            name="Minimum Sections",
            description="A page must have at least 1 section",
            severity=ValidationSeverity.CRITICAL,
            check_fn_name="check_minimum_sections",
            applies_to=["page"],
        ),
        ValidationRule(
            rule_id="STRUCT-002",
            name="Homepage Required",
            description="A site must have a homepage",
            severity=ValidationSeverity.CRITICAL,
            check_fn_name="check_homepage_exists",
            applies_to=["blueprint", "site"],
        ),
        ValidationRule(
            rule_id="STRUCT-003",
            name="Unique Page IDs",
            description="All page IDs must be unique",
            severity=ValidationSeverity.CRITICAL,
            check_fn_name="check_unique_page_ids",
            applies_to=["blueprint", "site"],
        ),
        ValidationRule(
            rule_id="SEO-001",
            name="Meta Title Present",
            description="Each page should have a meta title",
            severity=ValidationSeverity.HIGH,
            check_fn_name="check_meta_titles",
            applies_to=["blueprint", "site"],
        ),
        ValidationRule(
            rule_id="SEO-002",
            name="Meta Description Present",
            description="Each page should have a meta description",
            severity=ValidationSeverity.MEDIUM,
            check_fn_name="check_meta_descriptions",
            applies_to=["blueprint", "site"],
        ),
        ValidationRule(
            rule_id="SEO-003",
            name="H1 Tag Present",
            description="Homepage should have at least one h1 heading",
            severity=ValidationSeverity.HIGH,
            check_fn_name="check_h1_present",
            applies_to=["site"],
        ),
        ValidationRule(
            rule_id="UX-001",
            name="CTA Present",
            description="Site should have at least one CTA section",
            severity=ValidationSeverity.MEDIUM,
            check_fn_name="check_cta_present",
            applies_to=["blueprint", "site"],
        ),
        ValidationRule(
            rule_id="UX-002",
            name="Contact Section Present",
            description="Site should have a contact or location section",
            severity=ValidationSeverity.MEDIUM,
            check_fn_name="check_contact_present",
            applies_to=["blueprint", "site"],
        ),
        ValidationRule(
            rule_id="A11Y-001",
            name="Section IDs Present",
            description="All sections should have unique IDs for anchor links",
            severity=ValidationSeverity.LOW,
            check_fn_name="check_section_ids",
            applies_to=["site"],
        ),
        ValidationRule(
            rule_id="PERF-001",
            name="Image Count Reasonable",
            description="Page should not have excessive number of images",
            severity=ValidationSeverity.LOW,
            check_fn_name="check_image_count",
            applies_to=["page"],
        ),
    ]

    def __init__(self):
        self._issues: List[ValidationIssue] = []

    # ── Public API ─────────────────────────────────────────────

    def validate_blueprint(self, blueprint: Blueprint) -> ValidationResult:
        """Validate a blueprint against all applicable rules."""
        self._issues = []

        for rule in self.RULES:
            if "blueprint" in rule.applies_to:
                check_fn = getattr(self, rule.check_fn_name, None)
                if check_fn:
                    check_fn(blueprint=blueprint)

        return self._build_result("blueprint")

    def validate_site(self, site: Site) -> ValidationResult:
        """Validate an assembled site against all applicable rules."""
        self._issues = []

        for rule in self.RULES:
            if "site" in rule.applies_to:
                check_fn = getattr(self, rule.check_fn_name, None)
                if check_fn:
                    check_fn(site=site)

        for page in site.pages:
            for rule in self.RULES:
                if "page" in rule.applies_to:
                    check_fn = getattr(self, rule.check_fn_name, None)
                    if check_fn:
                        check_fn(page=page, site=site)

        return self._build_result("site")

    def validate_page(self, page: Page) -> ValidationResult:
        """Validate a single page."""
        self._issues = []

        for rule in self.RULES:
            if "page" in rule.applies_to:
                check_fn = getattr(self, rule.check_fn_name, None)
                if check_fn:
                    check_fn(page=page)

        return self._build_result(f"page:{page.id}")

    def get_rules(self) -> List[ValidationRule]:
        """Get all validation rules."""
        return self.RULES

    # ── Check Methods ──────────────────────────────────────────

    def check_minimum_sections(self, page: Page = None, **kwargs) -> None:
        """Check that a page has at least one section."""
        if page and not page.sections:
            self._add_issue("STRUCT-001", ValidationSeverity.CRITICAL,
                          f"Page '{page.id}' has no sections",
                          f"page:{page.id}",
                          "Add at least one section to this page")

    def check_homepage_exists(self, blueprint: Blueprint = None, site: Site = None, **kwargs) -> None:
        """Check that a homepage exists."""
        has_homepage = False
        if blueprint:
            has_homepage = any(p.is_homepage for p in blueprint.pages)
        elif site:
            has_homepage = any(p.is_homepage for p in site.pages)

        if not has_homepage:
            self._add_issue("STRUCT-002", ValidationSeverity.CRITICAL,
                          "No homepage defined",
                          "site",
                          "Mark one page as homepage (is_homepage=True)")

    def check_unique_page_ids(self, blueprint: Blueprint = None, site: Site = None, **kwargs) -> None:
        """Check that all page IDs are unique."""
        pages = []
        if blueprint:
            pages = blueprint.pages
        elif site:
            pages = site.pages

        ids = [p.page_id if hasattr(p, 'page_id') else p.id for p in pages]
        seen = set()
        for pid in ids:
            if pid in seen:
                self._add_issue("STRUCT-003", ValidationSeverity.CRITICAL,
                              f"Duplicate page ID: '{pid}'",
                              f"page:{pid}",
                              "Use unique page IDs")
            seen.add(pid)

    def check_meta_titles(self, blueprint: Blueprint = None, site: Site = None, **kwargs) -> None:
        """Check that pages have meta titles."""
        pages = []
        if blueprint:
            pages = blueprint.pages
        elif site:
            pages = site.pages

        for page in pages:
            title = page.meta_title if hasattr(page, 'meta_title') else (page.meta.title if page.meta else None)
            if not title:
                pid = page.page_id if hasattr(page, 'page_id') else page.id
                self._add_issue("SEO-001", ValidationSeverity.HIGH,
                              f"Page '{pid}' has no meta title",
                              f"page:{pid}",
                              "Add a descriptive meta title")

    def check_meta_descriptions(self, blueprint: Blueprint = None, site: Site = None, **kwargs) -> None:
        """Check that pages have meta descriptions."""
        pages = []
        if blueprint:
            pages = blueprint.pages
        elif site:
            pages = site.pages

        for page in pages:
            desc = page.meta_description if hasattr(page, 'meta_description') else (page.meta.description if page.meta else None)
            if not desc:
                pid = page.page_id if hasattr(page, 'page_id') else page.id
                self._add_issue("SEO-002", ValidationSeverity.MEDIUM,
                              f"Page '{pid}' has no meta description",
                              f"page:{pid}",
                              "Add a meta description for SEO")

    def check_h1_present(self, site: Site = None, **kwargs) -> None:
        """Check that homepage has an h1 heading."""
        if not site:
            return
        homepage = site.get_homepage()
        if homepage:
            has_h1 = any(
                s.config.heading_tag == "h1"
                for s in homepage.sections
            )
            if not has_h1:
                self._add_issue("SEO-003", ValidationSeverity.HIGH,
                              "Homepage has no h1 heading",
                              "page:home",
                              "Add a section with heading_tag='h1' on the homepage")

    def check_cta_present(self, blueprint: Blueprint = None, site: Site = None, **kwargs) -> None:
        """Check that site has a CTA section."""
        cta_types = {SectionType.CTA, SectionType.CTA_BANNER, SectionType.CTA_SPLIT, SectionType.CTA_FLOATING}

        has_cta = False
        if blueprint:
            for page in blueprint.pages:
                if any(s.section_type in cta_types for s in page.sections):
                    has_cta = True
                    break
        elif site:
            for page in site.pages:
                if any(s.type in cta_types for s in page.sections):
                    has_cta = True
                    break

        if not has_cta:
            self._add_issue("UX-001", ValidationSeverity.MEDIUM,
                          "No CTA section found",
                          "site",
                          "Add a CTA section to improve conversion")

    def check_contact_present(self, blueprint: Blueprint = None, site: Site = None, **kwargs) -> None:
        """Check that site has a contact section."""
        contact_types = {SectionType.CONTACT, SectionType.CONTACT_FORM, SectionType.CONTACT_MAP,
                        SectionType.CONTACT_INFO, SectionType.LOCATION, SectionType.APPOINTMENT,
                        SectionType.RESERVATION}

        has_contact = False
        if blueprint:
            for page in blueprint.pages:
                if any(s.section_type in contact_types for s in page.sections):
                    has_contact = True
                    break
        elif site:
            for page in site.pages:
                if any(s.type in contact_types for s in page.sections):
                    has_contact = True
                    break

        if not has_contact:
            self._add_issue("UX-002", ValidationSeverity.MEDIUM,
                          "No contact section found",
                          "site",
                          "Add a contact or location section")

    def check_section_ids(self, site: Site = None, **kwargs) -> None:
        """Check that all sections have unique IDs."""
        if not site:
            return

        for page in site.pages:
            ids = []
            for section in page.sections:
                if section.id:
                    if section.id in ids:
                        self._add_issue("A11Y-001", ValidationSeverity.LOW,
                                      f"Duplicate section ID '{section.id}' on page '{page.id}'",
                                      f"page:{page.id}",
                                      "Use unique section IDs for anchor links")
                    ids.append(section.id)

    def check_image_count(self, page: Page = None, **kwargs) -> None:
        """Check that image count is reasonable."""
        if not page:
            return

        image_sections = [SectionType.GALLERY, SectionType.GALLERY_MASONRY,
                         SectionType.GALLERY_CAROUSEL, SectionType.IMAGE_GRID,
                         SectionType.HERO, SectionType.HERO_SLIDER]

        image_count = sum(
            1 for s in page.sections
            if s.type in image_sections
        )

        if image_count > 5:
            self._add_issue("PERF-001", ValidationSeverity.LOW,
                          f"Page '{page.id}' has {image_count} image-heavy sections",
                          f"page:{page.id}",
                          "Consider reducing image count for better performance")

    # ── Private Helpers ────────────────────────────────────────

    def _add_issue(
        self,
        rule_id: str,
        severity: ValidationSeverity,
        message: str,
        target: str,
        suggestion: Optional[str] = None,
    ) -> None:
        """Add a validation issue."""
        self._issues.append(ValidationIssue(
            rule_id=rule_id,
            severity=severity,
            message=message,
            target=target,
            suggestion=suggestion,
        ))

    def _build_result(self, target: str) -> ValidationResult:
        """Build validation result from collected issues."""
        severity_counts = {
            ValidationSeverity.CRITICAL: 0,
            ValidationSeverity.HIGH: 0,
            ValidationSeverity.MEDIUM: 0,
            ValidationSeverity.LOW: 0,
            ValidationSeverity.INFO: 0,
        }

        for issue in self._issues:
            severity_counts[issue.severity] = severity_counts.get(issue.severity, 0) + 1

        is_valid = severity_counts[ValidationSeverity.CRITICAL] == 0

        summary_parts = []
        if severity_counts[ValidationSeverity.CRITICAL] > 0:
            summary_parts.append(f"{severity_counts[ValidationSeverity.CRITICAL]} critical")
        if severity_counts[ValidationSeverity.HIGH] > 0:
            summary_parts.append(f"{severity_counts[ValidationSeverity.HIGH]} high")
        if severity_counts[ValidationSeverity.MEDIUM] > 0:
            summary_parts.append(f"{severity_counts[ValidationSeverity.MEDIUM]} medium")
        if severity_counts[ValidationSeverity.LOW] > 0:
            summary_parts.append(f"{severity_counts[ValidationSeverity.LOW]} low")

        summary = f"Validation of {target}: " + (", ".join(summary_parts) if summary_parts else "No issues found")
        if not is_valid:
            summary += " - NOT VALID"

        return ValidationResult(
            is_valid=is_valid,
            total_issues=len(self._issues),
            critical_count=severity_counts[ValidationSeverity.CRITICAL],
            high_count=severity_counts[ValidationSeverity.HIGH],
            medium_count=severity_counts[ValidationSeverity.MEDIUM],
            low_count=severity_counts[ValidationSeverity.LOW],
            info_count=severity_counts[ValidationSeverity.INFO],
            issues=sorted(self._issues, key=lambda i: [
                ValidationSeverity.CRITICAL,
                ValidationSeverity.HIGH,
                ValidationSeverity.MEDIUM,
                ValidationSeverity.LOW,
                ValidationSeverity.INFO,
            ].index(i.severity)),
            summary=summary,
        )


# Singleton
_validator_instance: Optional[BlueprintValidator] = None


def get_blueprint_validator() -> BlueprintValidator:
    """Get the singleton BlueprintValidator instance."""
    global _validator_instance
    if _validator_instance is None:
        _validator_instance = BlueprintValidator()
    return _validator_instance
