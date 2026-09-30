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


# Process-wide registry; modules import this and wire their plugin points.
registry = HookRegistry()


# Canonical hook names (keep stable — third-party plugins bind to these).
HOOK_PAGE_BEFORE_SAVE = "cms.page.before_save"      # filter: payload dict
HOOK_PAGE_AFTER_PUBLISH = "cms.page.after_publish"  # action: page response
HOOK_PAGE_BODY_RENDER = "cms.page.body_render"      # filter: sanitized HTML out
HOOK_SEO_METADATA = "seo.metadata"                  # filter: SEO dict before persist

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
