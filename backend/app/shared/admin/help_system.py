"""Admin inline documentation / help system (WordPress parity).

Provides contextual help text and documentation for admin panel sections.
Each admin route/section can register help tabs that appear in a collapsible
panel at the top of the page.

Usage:
    from app.shared.admin.help_system import HelpSystem
    help_data = HelpSystem.get_help("blog_posts")
"""

from __future__ import annotations

from typing import Any


# Help content registry: section_id -> list of help tabs
_HELP_REGISTRY: dict[str, list[dict[str, str]]] = {
    "blog_posts": [
        {
            "title": "Managing Posts",
            "content": (
                "This screen lists all your blog posts. You can filter by status "
                "(Draft, Published, Archived), search by title or content, and sort "
                "by date or title. Use the bulk actions dropdown to publish, unpublish, "
                "or trash multiple posts at once."
            ),
        },
        {
            "title": "Post Statuses",
            "content": (
                "**Draft**: Not visible to the public. Save as draft to continue editing later.\n"
                "**Published**: Live on the site and visible to visitors.\n"
                "**Archived**: Removed from public listings but preserved.\n"
                "**Trashed**: Soft-deleted; can be restored or permanently deleted."
            ),
        },
    ],
    "blog_comments": [
        {
            "title": "Comment Moderation",
            "content": (
                "Comments can be Pending (awaiting approval), Approved (visible), "
                "Spam (flagged), or Trashed. Authenticated users' comments are "
                "auto-approved by default. You can change moderation rules in Settings."
            ),
        },
    ],
    "media_library": [
        {
            "title": "Managing Media",
            "content": (
                "Upload images, documents, and other files. Each file gets a unique URL, "
                "alt text for accessibility, and optional caption/description. "
                "Use folders to organize your media library."
            ),
        },
        {
            "title": "Image Editing",
            "content": (
                "Click on any image to crop, resize, rotate, or flip it. "
                "Edits create a new file — the original is preserved. "
                "Focal point can be set for smart cropping in responsive layouts."
            ),
        },
    ],
    "cms_pages": [
        {
            "title": "Managing Pages",
            "content": (
                "Pages are static content like About, Contact, Terms. Unlike blog posts, "
                "pages can be hierarchical (parent-child). Set a page template to control "
                "its layout (full-width, with sidebar, landing page)."
            ),
        },
    ],
    "settings": [
        {
            "title": "Site Settings",
            "content": (
                "Configure site-wide options: title, description, permalink structure, "
                "comment defaults, media sizes, and more. Changes apply immediately."
            ),
        },
    ],
    "seo": [
        {
            "title": "SEO Settings",
            "content": (
                "Each post and page can have custom SEO title, description, and Open Graph "
                "tags. Redirects let you manage old URLs. The sitemap is auto-generated."
            ),
        },
    ],
}


class HelpSystem:
    """Admin contextual help system."""

    @staticmethod
    def get_help(section: str) -> list[dict[str, str]]:
        """Get help tabs for a given admin section."""
        return _HELP_REGISTRY.get(section, [])

    @staticmethod
    def get_all_sections() -> list[str]:
        """List all sections that have help content."""
        return sorted(_HELP_REGISTRY.keys())

    @staticmethod
    def register_help(section: str, title: str, content: str) -> None:
        """Register a new help tab for a section (plugin extensibility)."""
        if section not in _HELP_REGISTRY:
            _HELP_REGISTRY[section] = []
        _HELP_REGISTRY[section].append({"title": title, "content": content})

    @staticmethod
    def get_all_help() -> dict[str, list[dict[str, str]]]:
        """Get all help content for all sections."""
        return _HELP_REGISTRY.copy()
