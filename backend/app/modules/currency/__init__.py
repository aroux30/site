"""USD → Toman automatic price updater (ported from the owner's
"Nobitex Price Updater Ultimate" WordPress plugin, v4.5.0).

The plugin watched the Nobitex USDT/IRT rate and rewrote every WooCommerce
product that carried a USD meta price. This module is the same feature inside
the modular monolith: a config row (``currency.usd_rate``), a fixed-endpoint
Nobitex client, a sweep that rewrites variant prices, a per-change log table,
and an admin API + page.

Deliberate difference from the plugin: a per-change log ROW in the database
(the plugin wrote a rotating text file inside the plugin directory), so the
history is queryable, filterable, and exportable like every other admin
surface in this project. The audit module's field-level capture additionally
records each variant price change with before/after values.
"""
