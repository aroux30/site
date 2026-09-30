"""Recurring order subscriptions (ERP benchmark feature #30, P1).

A subscription is a plan (what to buy, how often, paid how) plus a schedule.
Each billing cycle creates a real ``orders`` row through the existing order
pipeline and charges the customer's tokenized saved card — the same
``charge_saved_method`` path the checkout uses, so a recurring charge is
auditable exactly like a one-time one.

Reference design: metasfresh's contract module (flat-rate / subscription +
invoice-candidate engine).
"""
