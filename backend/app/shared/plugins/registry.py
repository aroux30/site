"""Plugin/hook registry (WordPress actions/filters + Strapi plugin model).

Two primitives:
- **Actions** (``do_action``): fire-and-forget observers of a named event.
- **Filters** (``apply_filters``): value transformers chained by priority —
  each handler receives the current value and returns the (possibly) new one.

Plugins register via a ``Plugin`` object with a ``register(registry)`` method
(Strapi-style). Everything is in-process and synchronous-callable friendly;
async handlers are awaited transparently. Handler failures are logged and
never propagated — a broken plugin must not take down the storefront.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol

import structlog

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

HookHandler = Callable[..., Any]


class Plugin(Protocol):
    """A plugin exposes a name and registers its hooks on the registry."""

    name: str

    def register(self, registry: "HookRegistry") -> None: ...


@dataclass(order=True)
class _PrioritizedHandler:
    priority: int
    handler: HookHandler = field(compare=False)
    plugin: str = field(compare=False, default="core")


class HookRegistry:
    """Named action/filter hooks with priority-ordered handlers."""

    def __init__(self) -> None:
        self._actions: dict[str, list[_PrioritizedHandler]] = {}
        self._filters: dict[str, list[_PrioritizedHandler]] = {}
        self._plugins: dict[str, Plugin] = {}
        #: Plugin name -> enabled. Absent means enabled: a freshly registered
        #: plugin runs until an operator turns it off. Only *disabled* names
        #: are stored, so a deployment that never touches the toggles carries
        #: no state and behaves exactly as before this feature existed.
        self._disabled: set[str] = set()

    # ── Registration ──────────────────────────────────────────────────────

    def add_action(
        self, hook: str, handler: HookHandler, *, priority: int = 10, plugin: str = "core"
    ) -> None:
        self._actions.setdefault(hook, []).append(_PrioritizedHandler(priority, handler, plugin))
        self._actions[hook].sort()

    def add_filter(
        self, hook: str, handler: HookHandler, *, priority: int = 10, plugin: str = "core"
    ) -> None:
        self._filters.setdefault(hook, []).append(_PrioritizedHandler(priority, handler, plugin))
        self._filters[hook].sort()

    def register_plugin(self, plugin: Plugin) -> None:
        """Register a plugin's hooks. Idempotent per plugin name."""
        if plugin.name in self._plugins:
            return
        plugin.register(self)
        self._plugins[plugin.name] = plugin
        logger.info("plugin_registered", plugin=plugin.name)

    # ── Enable / disable (per-deployment module toggles) ──────────────────

    def is_enabled(self, plugin_name: str) -> bool:
        """True unless an operator explicitly disabled this plugin."""
        return plugin_name not in self._disabled

    def set_enabled(self, plugin_name: str, enabled: bool) -> bool:
        """Enable or disable a plugin for this process.

        Returns the resulting state. Unknown names are accepted: an operator
        may pre-disable a plugin before the module that registers it is
        imported, which is the only way to keep a slow or broken plugin out
        of a boot it would otherwise join.

        Core plugin points (``plugin="core"``) are not toggleable — they are
        the platform's own hooks, and "disable core" is not a state the
        system can be in.
        """
        if plugin_name == "core":
            raise ValueError("the core plugin point cannot be disabled")
        if enabled:
            self._disabled.discard(plugin_name)
        else:
            self._disabled.add(plugin_name)
        logger.info(
            "plugin_toggle",
            plugin=plugin_name,
            enabled=enabled,
        )
        return self.is_enabled(plugin_name)

    def disabled_plugins(self) -> list[str]:
        """Names currently switched off, for the admin surface."""
        return sorted(self._disabled)

    # ── Introspection (admin surface) ─────────────────────────────────────

    def describe(self) -> dict[str, Any]:
        return {
            "plugins": sorted(self._plugins),
            "disabled_plugins": sorted(self._disabled),
            "plugin_states": {
                name: self.is_enabled(name) for name in sorted(self._plugins)
            },
            "actions": {
                hook: [
                    {"plugin": h.plugin, "priority": h.priority, "handler": h.handler.__name__}
                    for h in handlers
                ]
                for hook, handlers in sorted(self._actions.items())
            },
            "filters": {
                hook: [
                    {"plugin": h.plugin, "priority": h.priority, "handler": h.handler.__name__}
                    for h in handlers
                ]
                for hook, handlers in sorted(self._filters.items())
            },
        }

    # ── Dispatch ──────────────────────────────────────────────────────────

    async def do_action(self, hook: str, *args: Any, **kwargs: Any) -> None:
        for entry in self._actions.get(hook, []):
            if not self.is_enabled(entry.plugin):
                continue
            try:
                result = entry.handler(*args, **kwargs)
                if inspect.isawaitable(result):
                    await result
            except Exception:  # noqa: BLE001 — plugin isolation
                await logger.awarning(
                    "hook_action_failed", hook=hook, plugin=entry.plugin, exc_info=True
                )

    async def apply_filters(self, hook: str, value: Any, *args: Any, **kwargs: Any) -> Any:
        for entry in self._filters.get(hook, []):
            # A disabled plugin is skipped *silently for its handler* but the
            # value still flows to the next handler — its absence must not
            # change the pipeline's shape for everyone else.
            if not self.is_enabled(entry.plugin):
                continue
            try:
                result = entry.handler(value, *args, **kwargs)
                if inspect.isawaitable(result):
                    result = await result
                value = result
            except Exception:  # noqa: BLE001 — a broken filter keeps the old value
                await logger.awarning(
                    "hook_filter_failed", hook=hook, plugin=entry.plugin, exc_info=True
                )
        return value

    def describe(self) -> dict[str, Any]:
        """Every hook, what kind it is, and which plugin handles it.

        Exposed because the alternative is invisible: a hook nobody binds to
        and a hook that is wired and dead look identical from the outside, and
        an author adding a plugin needs to see which points actually exist
        before writing one. The plugins page renders this.
        """
        return {
            # The shape the admin page already consumed. Kept, because
            # replacing it would silently empty a screen: the registry was
            # only ever describing *bound* hooks, which is why a hook with no
            # plugin attached to it was invisible.
            "plugins": sorted(self._plugins),
            "disabled_plugins": sorted(self._disabled_plugins()),
            "plugin_states": {
                name: self.is_enabled(name) for name in sorted(self._plugins)
            },
            "actions": {
                name: [
                    {
                        "plugin": e.plugin,
                        "priority": e.priority,
                        "handler": getattr(e.handler, "__qualname__", repr(e.handler)),
                    }
                    for e in handlers
                ]
                for name, handlers in sorted(self._actions.items())
            },
            "filters": {
                name: [
                    {
                        "plugin": e.plugin,
                        "priority": e.priority,
                        "handler": getattr(e.handler, "__qualname__", repr(e.handler)),
                    }
                    for e in handlers
                ]
                for name, handlers in sorted(self._filters.items())
            },
            # The declared surface, including the points nothing has bound to
            # yet — the ones a new plugin needs to know exist.
            "hooks": [
                {
                    "name": name,
                    "kind": kind,
                    "handlers": [
                        {
                            "plugin": e.plugin,
                            "priority": e.priority,
                            "enabled": self.is_enabled(e.plugin),
                        }
                        for e in (
                            (self._actions if kind == "action" else self._filters).get(name)
                            or []
                        )
                    ],
                    "bound": bool(
                        (self._actions.get(name) or self._filters.get(name))
                    ),
                }
                # Sorted for a stable list between requests: the registry is
                # populated at import time and dict order follows it, which is
                # not a contract the page should depend on.
                for name, kind in sorted(DECLARED_HOOKS.items())
            ],
            "registered_plugins": sorted(self._plugins),
        }

    def _disabled_plugins(self) -> list[str]:
        """Plugins currently switched off. Read from the in-process disabled set.

        The settings row is the persistent half and is applied at startup by
        ``load_disabled_plugins``; this reports what the process is actually
        running with, which is the answer the toggle screen needs.
        """
        return sorted(p for p in self._plugins if not self.is_enabled(p))


# Process-wide registry; modules import this and wire their plugin points.
registry = HookRegistry()


# Canonical hook names (keep stable — third-party plugins bind to these).
HOOK_PAGE_BEFORE_SAVE = "cms.page.before_save"      # filter: payload dict
HOOK_PAGE_AFTER_PUBLISH = "cms.page.after_publish"  # action: page response
HOOK_PAGE_BODY_RENDER = "cms.page.body_render"      # filter: sanitized HTML out
HOOK_SEO_METADATA = "seo.metadata"                  # filter: SEO dict before persist

# Blog hooks. The CMS page had four and the blog had none, which is why a
# plugin could not react to a post being published or change a post's body —
# the two content types with the same shape and a different amount of
# extensibility. Named after the page hooks so a plugin reads the same way.
HOOK_POST_BEFORE_SAVE = "blog.post.before_save"      # filter: update dict
HOOK_POST_AFTER_SAVE = "blog.post.after_save"        # action: post id + status
HOOK_POST_AFTER_PUBLISH = "blog.post.after_publish"  # action: post response
HOOK_POST_BODY_RENDER = "blog.post.body_render"      # filter: rendered HTML out
HOOK_POST_STATUS_CHANGE = "blog.post.status_change"  # action: old + new status
HOOK_COMMENT_BEFORE_CREATE = "blog.comment.before_create"  # filter: comment dict
HOOK_COMMENT_AFTER_CREATE = "blog.comment.after_create"    # action: comment id
HOOK_COMMENT_BEFORE_MODERATE = "blog.comment.before_moderate"  # filter: status
HOOK_MEDIA_BEFORE_DELETE = "media.before_delete"     # filter: asset id
HOOK_MEDIA_AFTER_DELETE = "media.after_delete"       # action: asset id

#: Every hook the platform fires, with its kind. Listed explicitly rather than
#: derived from the registry, because a hook with no handler bound yet is
#: exactly the one an author needs to see: derived, it would be invisible until
#: the first plugin used it, and nobody writes a plugin for a point they cannot
#: see. The list is the API surface; the registry is what runs it.
DECLARED_HOOKS: dict[str, str] = {
    HOOK_PAGE_BEFORE_SAVE: "filter",
    HOOK_PAGE_AFTER_PUBLISH: "action",
    HOOK_PAGE_BODY_RENDER: "filter",
    HOOK_SEO_METADATA: "filter",
    HOOK_POST_BEFORE_SAVE: "filter",
    HOOK_POST_AFTER_SAVE: "action",
    HOOK_POST_AFTER_PUBLISH: "action",
    HOOK_POST_BODY_RENDER: "filter",
    HOOK_POST_STATUS_CHANGE: "action",
    HOOK_COMMENT_BEFORE_CREATE: "filter",
    HOOK_COMMENT_AFTER_CREATE: "action",
    HOOK_COMMENT_BEFORE_MODERATE: "filter",
    HOOK_MEDIA_BEFORE_DELETE: "filter",
    HOOK_MEDIA_AFTER_DELETE: "action",
}

# -- Persistence: plugin toggles survive a restart ---------------------------

#: The site-settings key holding the disabled-plugin list. One JSONB row,
#: written only when a toggle is used, so a deployment that never touches the
#: toggles never grows a row.
DISABLED_PLUGINS_SETTING_KEY = "plugins.disabled"


async def load_disabled_plugins(db: Any) -> list[str]:
    """Apply the persisted disable list to the in-process registry.

    Called once at startup. A missing row means "nothing disabled". A failure
    is logged and swallowed: a settings-table problem must not stop the app
    from booting, and the worst case (plugins enabled that an operator turned
    off) is visible in the admin surface.
    """
    from sqlalchemy import select

    from app.modules.settings.domain.models import SiteSetting

    try:
        row = (
            await db.execute(
                select(SiteSetting).where(SiteSetting.key == DISABLED_PLUGINS_SETTING_KEY)
            )
        ).scalar_one_or_none()
    except Exception:  # noqa: BLE001 - never block startup on a settings read
        logger.warning("plugin_toggle_load_failed", exc_info=True)
        return []

    if row is None or not row.value:
        return []
    names = row.value.get("names") if isinstance(row.value, dict) else None
    if not isinstance(names, list):
        return []
    for name in names:
        if isinstance(name, str) and name != "core":
            registry._disabled.add(name)
    return sorted(registry._disabled)


async def persist_disabled_plugins(db: Any) -> list[str]:
    """Write the current disable list back to the settings row."""
    from sqlalchemy import select

    from app.modules.settings.domain.models import SiteSetting

    names = sorted(registry._disabled)
    row = (
        await db.execute(
            select(SiteSetting).where(SiteSetting.key == DISABLED_PLUGINS_SETTING_KEY)
        )
    ).scalar_one_or_none()
    if row is None:
        row = SiteSetting(
            key=DISABLED_PLUGINS_SETTING_KEY,
            value={"names": names},
            group="plugins",
            description="پلاگین‌های غیرفعال این نصب",
            is_public=False,
        )
        db.add(row)
    else:
        row.value = {"names": names}
    await db.flush()
    return names
