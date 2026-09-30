"""Accounting feed module (ERP benchmark feature #20, scoped IMPLEMENT).

A *posted-journal event stream*, not a full in-house GL: chart of accounts,
double-entry journal entries chained to the money events the platform already
publishes (order / payment / refund / wallet / settlement), Jalali period
close, and CSV + JSON export for external accounting software
(هلو / سپیدار / محک). Iranian businesses run dedicated accounting packages;
this module's job is to get GL-grade data *out*, not to replace them.
"""
