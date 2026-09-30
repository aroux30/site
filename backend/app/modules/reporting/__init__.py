"""Reporting module — parameterized date-range reports, CSV export, and
scheduled report delivery (ERP benchmark gap-analysis feature 3, P0).

Permission model: reports are admin-only and use ``reports:read`` (data and
downloads) / ``reports:write`` (saved-report CRUD, scheduling, manual runs).
These are deliberately separate from ``analytics:read`` so the existing
dashboard consumers keep their current semantics untouched.

Money rule: every monetary field is an integer number of Iranian Rials
(BigInteger columns end to end). The frontend formats values in Toman with
the existing ``formatPrice`` utility; no floats are ever used for money here.

PDF export is intentionally deferred: no PDF library is installed (the
project ships no reportlab/weasyprint dependency). The module provides the
:class:`ReportRenderer` protocol and an HTML fallback renderer instead —
HTML artifacts are archived under the report-run download endpoints and can
be printed to PDF from the browser.
"""
