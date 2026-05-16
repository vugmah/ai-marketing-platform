"""
Enumeration types for the website builder schema system.
All enum values are stored as lowercase strings for JSON serialization.
"""

from enum import Enum
from typing import List, Dict, Any


class IndustryType(str, Enum):
    """Business industry verticals supported by the website builder."""
    RESTAURANT = "restaurant"
    CAFE = "cafe"
    RETAIL = "retail"
    ELECTRONICS = "electronics"
    FASHION = "fashion"
    HEALTHCARE = "healthcare"
    FITNESS = "fitness"
    EDUCATION = "education"
    REAL_ESTATE = "real_estate"
    AUTOMOTIVE = "automotive"
    BEAUTY = "beauty"
    SALON = "salon"
    HOTEL = "hotel"
    TRAVEL = "travel"
    CONSULTING = "consulting"
    TECHNOLOGY = "technology"
    FINANCE = "finance"
    LAW = "law"
    CONSTRUCTION = "construction"
    PHARMACY = "pharmacy"
    SUPERMARKET = "supermarket"
    GENERIC = "generic"

    @classmethod
    def get_all(cls) -> List[str]:
        return [member.value for member in cls]

    @classmethod
    def get_display_names(cls) -> Dict[str, str]:
        return {
            cls.RESTAURANT: "Restaurant / Food",
            cls.CAFE: "Cafe / Coffee Shop",
            cls.RETAIL: "Retail Store",
            cls.ELECTRONICS: "Electronics Store",
            cls.FASHION: "Fashion / Clothing",
            cls.HEALTHCARE: "Healthcare / Clinic",
            cls.FITNESS: "Fitness / Gym",
            cls.EDUCATION: "Education / School",
            cls.REAL_ESTATE: "Real Estate",
            cls.AUTOMOTIVE: "Automotive / Car Service",
            cls.BEAUTY: "Beauty / Cosmetics",
            cls.SALON: "Hair Salon / Barber",
            cls.HOTEL: "Hotel / Hospitality",
            cls.TRAVEL: "Travel Agency",
            cls.CONSULTING: "Consulting / Agency",
            cls.TECHNOLOGY: "Technology / Software",
            cls.FINANCE: "Finance / Banking",
            cls.LAW: "Law / Legal Services",
            cls.CONSTRUCTION: "Construction / Contractor",
            cls.PHARMACY: "Pharmacy / Drugstore",
            cls.SUPERMARKET: "Supermarket / Grocery",
            cls.GENERIC: "General Business",
        }


class BusinessSize(str, Enum):
    """Business size tiers affecting feature availability."""
    MICRO = "micro"          # 1-3 employees
    SMALL = "small"          # 4-20 employees
    MEDIUM = "medium"        # 21-100 employees
    LARGE = "large"          # 100+ employees
    ENTERPRISE = "enterprise"

    @classmethod
    def get_all(cls) -> List[str]:
        return [member.value for member in cls]


class ColorScheme(str, Enum):
    """Pre-defined color scheme presets."""
    CORPORATE_BLUE = "corporate_blue"
    WARM_NEUTRAL = "warm_neutral"
    DARK_MODE = "dark_mode"
    VIBRANT = "vibrant"
    MINIMAL_WHITE = "minimal_white"
    EARTH_TONES = "earth_tones"
    PASTEL = "pastel"
    MONOCHROME = "monochrome"
    RETRO = "retro"
    OCEAN = "ocean"
    FOREST = "forest"
    SUNSET = "sunset"
    LUXURY_GOLD = "luxury_gold"
    CUSTOM = "custom"

    @classmethod
    def get_all(cls) -> List[str]:
        return [member.value for member in cls]


class FontPair(str, Enum):
    """Pre-defined font pairings."""
    MODERN_SANS = "modern_sans"           # Inter + Inter
    CLASSIC_SERIF = "classic_serif"       # Playfair Display + Lato
    TECH_MONO = "tech_mono"               # JetBrains Mono + Open Sans
    ELEGANT = "elegant"                   # Cormorant Garamond + Montserrat
    BOLD_IMPACT = "bold_impact"           # Oswald + Roboto
    FRIENDLY = "friendly"                 # Nunito + Nunito Sans
    MINIMAL = "minimal"                   # Helvetica Neue + Arial
    LUXURY = "luxury"                     # Bodoni Moda + Futura
    HANDWRITTEN = "handwritten"           # Caveat + Open Sans
    STARTUP = "startup"                   # Poppins + Source Sans Pro

    @classmethod
    def get_all(cls) -> List[str]:
        return [member.value for member in cls]

    @classmethod
    def get_fonts(cls, pair: "FontPair") -> Dict[str, str]:
        """Get the actual font names for a given pair."""
        mapping = {
            cls.MODERN_SANS: {"heading": "Inter", "body": "Inter"},
            cls.CLASSIC_SERIF: {"heading": "Playfair Display", "body": "Lato"},
            cls.TECH_MONO: {"heading": "JetBrains Mono", "body": "Open Sans"},
            cls.ELEGANT: {"heading": "Cormorant Garamond", "body": "Montserrat"},
            cls.BOLD_IMPACT: {"heading": "Oswald", "body": "Roboto"},
            cls.FRIENDLY: {"heading": "Nunito", "body": "Nunito Sans"},
            cls.MINIMAL: {"heading": "Helvetica Neue", "body": "Arial"},
            cls.LUXURY: {"heading": "Bodoni Moda", "body": "Futura"},
            cls.HANDWRITTEN: {"heading": "Caveat", "body": "Open Sans"},
            cls.STARTUP: {"heading": "Poppins", "body": "Source Sans Pro"},
        }
        return mapping.get(pair, {"heading": "Inter", "body": "Inter"})


class AnimationLevel(str, Enum):
    """Animation complexity levels."""
    NONE = "none"
    SUBTLE = "subtle"         # Fade-ins, smooth scroll
    MODERATE = "moderate"     # Slide-ups, parallax, hover effects
    HIGH = "high"             # Full scroll-triggered animations, 3D transforms
    CINEMATIC = "cinematic"   # Complex sequenced animations, particle effects

    @classmethod
    def get_all(cls) -> List[str]:
        return [member.value for member in cls]


class DeviceTarget(str, Enum):
    """Primary device targets for responsive optimization."""
    MOBILE_FIRST = "mobile_first"
    DESKTOP_FIRST = "desktop_first"
    ALL_DEVICES = "all_devices"


class SectionType(str, Enum):
    """All available section types for page composition."""
    # Hero sections
    HERO = "hero"
    HERO_VIDEO = "hero_video"
    HERO_SLIDER = "hero_slider"
    HERO_SPLIT = "hero_split"
    HERO_MINIMAL = "hero_minimal"

    # Navigation
    NAVBAR = "navbar"
    MEGA_MENU = "mega_menu"
    SIDEBAR = "sidebar"

    # Content sections
    ABOUT = "about"
    ABOUT_SPLIT = "about_split"
    ABOUT_TEAM = "about_team"
    ABOUT_STATS = "about_stats"

    # Service/Product
    SERVICES = "services"
    SERVICES_GRID = "services_grid"
    SERVICES_CARDS = "services_cards"
    PRODUCTS = "products"
    PRODUCT_SHOWCASE = "product_showcase"
    FEATURES = "features"
    FEATURES_TABS = "features_tabs"

    # Gallery/Media
    GALLERY = "gallery"
    GALLERY_MASONRY = "gallery_masonry"
    GALLERY_CAROUSEL = "gallery_carousel"
    IMAGE_GRID = "image_grid"
    VIDEO_SECTION = "video_section"

    # Testimonials
    TESTIMONIALS = "testimonials"
    TESTIMONIALS_CAROUSEL = "testimonials_carousel"
    TESTIMONIALS_GRID = "testimonials_grid"

    # Pricing
    PRICING = "pricing"
    PRICING_TABLES = "pricing_tables"
    PRICING_TOGGLE = "pricing_toggle"

    # Contact
    CONTACT = "contact"
    CONTACT_FORM = "contact_form"
    CONTACT_MAP = "contact_map"
    CONTACT_INFO = "contact_info"

    # CTA
    CTA = "cta"
    CTA_BANNER = "cta_banner"
    CTA_SPLIT = "cta_split"
    CTA_FLOATING = "cta_floating"

    # Footer
    FOOTER = "footer"
    FOOTER_MINIMAL = "footer_minimal"
    FOOTER_MEGA = "footer_mega"

    # Specialized
    MENU = "menu"                     # Restaurant/food menu
    MENU_BOARD = "menu_board"
    RESERVATION = "reservation"
    APPOINTMENT = "appointment"
    PORTFOLIO = "portfolio"
    BLOG = "blog"
    BLOG_PREVIEW = "blog_preview"
    FAQ = "faq"
    FAQ_ACCORDION = "faq_accordion"
    SCHEDULE = "schedule"
    LOCATION = "location"
    MAP = "map"
    SOCIAL_FEED = "social_feed"
    NEWSLETTER = "newsletter"
    TRUST_BADGES = "trust_badges"
    COMPARISON = "comparison"
    INTEGRATIONS = "integrations"
    PROCESS_STEPS = "process_steps"
    TIMELINE = "timeline"
    STATS_COUNTERS = "stats_counters"
    PARTNERS_LOGOS = "partners_logos"
    CAREERS = "careers"
    PRESS = "press"

    # E-commerce
    SHOP = "shop"
    CART_PREVIEW = "cart_preview"
    PRODUCT_DETAIL = "product_detail"

    @classmethod
    def get_all(cls) -> List[str]:
        return [member.value for member in cls]

    @classmethod
    def get_categories(cls) -> Dict[str, List[str]]:
        """Group section types by category."""
        return {
            "hero": [
                cls.HERO, cls.HERO_VIDEO, cls.HERO_SLIDER,
                cls.HERO_SPLIT, cls.HERO_MINIMAL,
            ],
            "navigation": [
                cls.NAVBAR, cls.MEGA_MENU, cls.SIDEBAR,
            ],
            "about": [
                cls.ABOUT, cls.ABOUT_SPLIT, cls.ABOUT_TEAM, cls.ABOUT_STATS,
            ],
            "services": [
                cls.SERVICES, cls.SERVICES_GRID, cls.SERVICES_CARDS,
                cls.PRODUCTS, cls.PRODUCT_SHOWCASE, cls.FEATURES, cls.FEATURES_TABS,
            ],
            "gallery": [
                cls.GALLERY, cls.GALLERY_MASONRY, cls.GALLERY_CAROUSEL,
                cls.IMAGE_GRID, cls.VIDEO_SECTION,
            ],
            "testimonials": [
                cls.TESTIMONIALS, cls.TESTIMONIALS_CAROUSEL, cls.TESTIMONIALS_GRID,
            ],
            "pricing": [
                cls.PRICING, cls.PRICING_TABLES, cls.PRICING_TOGGLE,
            ],
            "contact": [
                cls.CONTACT, cls.CONTACT_FORM, cls.CONTACT_MAP, cls.CONTACT_INFO,
            ],
            "cta": [
                cls.CTA, cls.CTA_BANNER, cls.CTA_SPLIT, cls.CTA_FLOATING,
            ],
            "footer": [
                cls.FOOTER, cls.FOOTER_MINIMAL, cls.FOOTER_MEGA,
            ],
            "specialized": [
                cls.MENU, cls.MENU_BOARD, cls.RESERVATION, cls.APPOINTMENT,
                cls.PORTFOLIO, cls.BLOG, cls.BLOG_PREVIEW, cls.FAQ,
                cls.FAQ_ACCORDION, cls.SCHEDULE, cls.LOCATION, cls.MAP,
                cls.SOCIAL_FEED, cls.NEWSLETTER, cls.TRUST_BADGES,
                cls.COMPARISON, cls.INTEGRATIONS, cls.PROCESS_STEPS,
                cls.TIMELINE, cls.STATS_COUNTERS, cls.PARTNERS_LOGOS,
                cls.CAREERS, cls.PRESS,
            ],
            "ecommerce": [
                cls.SHOP, cls.CART_PREVIEW, cls.PRODUCT_DETAIL,
            ],
        }

    @classmethod
    def get_by_industry(cls, industry: IndustryType) -> List[str]:
        """Get recommended section types for a given industry."""
        recommendations = {
            IndustryType.RESTAURANT: [
                cls.HERO, cls.ABOUT, cls.MENU, cls.GALLERY,
                cls.RESERVATION, cls.TESTIMONIALS, cls.LOCATION, cls.CONTACT, cls.FOOTER,
            ],
            IndustryType.CAFE: [
                cls.HERO, cls.ABOUT, cls.MENU, cls.GALLERY,
                cls.TESTIMONIALS, cls.LOCATION, cls.CONTACT, cls.FOOTER,
            ],
            IndustryType.RETAIL: [
                cls.HERO, cls.PRODUCTS, cls.FEATURES, cls.GALLERY,
                cls.TESTIMONIALS, cls.CTA, cls.CONTACT, cls.FOOTER,
            ],
            IndustryType.ELECTRONICS: [
                cls.HERO, cls.PRODUCT_SHOWCASE, cls.FEATURES_TABS, cls.SPECIFICATIONS,
                cls.COMPARISON, cls.TESTIMONIALS, cls.CTA, cls.FOOTER,
            ],
            IndustryType.FASHION: [
                cls.HERO_SLIDER, cls.PRODUCTS, cls.GALLERY, cls.TESTIMONIALS,
                cls.INSTAGRAM_FEED, cls.CTA, cls.FOOTER,
            ],
            IndustryType.HEALTHCARE: [
                cls.HERO, cls.SERVICES, cls.ABOUT, cls.APPOINTMENT,
                cls.TESTIMONIALS, cls.FAQ, cls.CONTACT, cls.FOOTER,
            ],
            IndustryType.FITNESS: [
                cls.HERO_VIDEO, cls.SERVICES, cls.PRICING, cls.TRAINERS,
                cls.TESTIMONIALS, cls.SCHEDULE, cls.CTA, cls.FOOTER,
            ],
            IndustryType.EDUCATION: [
                cls.HERO, cls.SERVICES, cls.FEATURES, cls.TESTIMONIALS,
                cls.FAQ, cls.CONTACT, cls.FOOTER,
            ],
            IndustryType.REAL_ESTATE: [
                cls.HERO, cls.PROPERTIES, cls.ABOUT, cls.TESTIMONIALS,
                cls.CTA, cls.CONTACT, cls.FOOTER,
            ],
            IndustryType.AUTOMOTIVE: [
                cls.HERO, cls.SERVICES, cls.FEATURES, cls.GALLERY,
                cls.TESTIMONIALS, cls.APPOINTMENT, cls.FOOTER,
            ],
            IndustryType.SALON: [
                cls.HERO, cls.SERVICES, cls.GALLERY, cls.PRICING,
                cls.APPOINTMENT, cls.TESTIMONIALS, cls.FOOTER,
            ],
            IndustryType.HOTEL: [
                cls.HERO_SLIDER, cls.ABOUT, cls.ROOMS, cls.AMENITIES,
                cls.GALLERY, cls.TESTIMONIALS, cls.RESERVATION, cls.FOOTER,
            ],
            IndustryType.CONSULTING: [
                cls.HERO, cls.SERVICES, cls.ABOUT, cls.PROCESS_STEPS,
                cls.TESTIMONIALS, cls.CTA, cls.FOOTER,
            ],
            IndustryType.TECHNOLOGY: [
                cls.HERO, cls.FEATURES, cls.INTEGRATIONS, cls.PRICING,
                cls.TESTIMONIALS, cls.CTA, cls.FOOTER,
            ],
            IndustryType.FINANCE: [
                cls.HERO, cls.SERVICES, cls.TRUST_BADGES, cls.TESTIMONIALS,
                cls.CTA, cls.CONTACT, cls.FOOTER,
            ],
            IndustryType.LAW: [
                cls.HERO, cls.SERVICES, cls.ABOUT_TEAM, cls.TESTIMONIALS,
                cls.CTA, cls.CONTACT, cls.FOOTER,
            ],
            IndustryType.CONSTRUCTION: [
                cls.HERO, cls.SERVICES, cls.PROJECTS, cls.ABOUT,
                cls.TESTIMONIALS, cls.CTA, cls.FOOTER,
            ],
            IndustryType.PHARMACY: [
                cls.HERO, cls.SERVICES, cls.PRODUCTS, cls.LOCATION,
                cls.CONTACT, cls.FOOTER,
            ],
            IndustryType.SUPERMARKET: [
                cls.HERO, cls.CATEGORIES, cls.DEALS, cls.LOCATION,
                cls.CONTACT, cls.FOOTER,
            ],
            IndustryType.GENERIC: [
                cls.HERO, cls.ABOUT, cls.SERVICES, cls.TESTIMONIALS,
                cls.CTA, cls.CONTACT, cls.FOOTER,
            ],
        }
        return [s.value for s in recommendations.get(industry, recommendations[IndustryType.GENERIC])]
