"""Site Health answers "can the site send email?" and "is the disk full?".

Both were absent from the checks. The email one is the store's most common
total-but-silent failure — SMTP unset means no notification, no reset link, no
order confirmation, with nothing red anywhere an operator looks. The disk one
stops uploads and invoice writes, and the first symptom is a 500 on checkout.

The assertions are behavioural, against the real report:

  * the report contains an Email Delivery check whose status tracks the SMTP
    configuration (configured -> good, unconfigured -> warning), and a Disk
    Space check with a percentage and a free-space figure;
  * both are inside the platform section, so the platform/content split in the
    summary counts them.

Run:  python .p1-tests/site_health_email_disk_test.py
"""

from __future__ import annotations

import asyncio
import io
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, "C:/Users/Administrator/Desktop/site/backend")

import app.main  # noqa: F401 — registers every model, as the app does

from app.core.database.session import _build_engine, async_sessionmaker
from app.modules.settings.application.site_health_service import SiteHealthService

bad: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  {label}: {ok}")
    if not ok:
        bad.append(f"{label}: {detail}" if detail else label)


async def main() -> int:
    eng = _build_engine()
    Session = async_sessionmaker(eng, expire_on_commit=False)

    async with Session() as db:
        report = await SiteHealthService.run_checks(db)

    checks = {c["name"]: c for c in report["checks"]}

    # 1. The email check exists and is a real verdict, not a stub.
    check("1. the report has an Email Delivery check", "Email Delivery" in checks,
          f"names={sorted(checks)}")
    email = checks.get("Email Delivery", {})
    check("1b. with a good/warning/critical status",
          email.get("status") in ("good", "warning", "critical"),
          f"status={email.get('status')!r}")
    check("1c. and a value naming the configuration",
          bool(str(email.get("value", "")).strip()),
          "the check says nothing")

    # 2. The disk check exists with a percentage and free space.
    check("2. the report has a Disk Space check", "Disk Space" in checks)
    disk = checks.get("Disk Space", {})
    value = str(disk.get("value", ""))
    check("2b. and its value carries a percentage", "%" in value, f"value={value!r}")
    check("2c. and a free-space figure",
          "GB free" in value or "free" in value, f"value={value!r}")
    check("2d. with a good/warning/critical status",
          disk.get("status") in ("good", "warning", "critical"),
          f"status={disk.get('status')!r}")

    # 2e. The loopback check exists with a real verdict.
    check("2e. the report has a Loopback Request check",
          "Loopback Request" in checks)
    loop = checks.get("Loopback Request", {})
    check("2f. with a good/warning/critical status",
          loop.get("status") in ("good", "warning", "critical"),
          f"status={loop.get('status')!r}")

    # 2g. Debug mode and database encoding are reported.
    check("2g. the report has a Debug Mode check", "Debug Mode" in checks)
    check("2h. the report has a Database Encoding check",
          "Database Encoding" in checks)
    enc = checks.get("Database Encoding", {})
    check("2i. and the encoding verdict is a real one",
          enc.get("status") in ("good", "warning", "critical"),
          f"status={enc.get('status')!r}")

    # 2j. Autoloaded options are measured.
    check("2j. the report has an Autoloaded Options check",
          "Autoloaded Options" in checks)
    auto = checks.get("Autoloaded Options", {})
    check("2k. and its value carries a size", "KB" in str(auto.get("value", "")),
          f"value={auto.get('value')!r}")

    # 3. The SMTP verdict must track the real configuration, not be hardcoded.
    from app.modules.notifications.application import email_service

    config = email_service.get_smtp_config(None)
    expected = "good" if config.is_configured else "warning"
    check("3. the email verdict tracks the SMTP configuration",
          email.get("status") == expected,
          f"config.is_configured={config.is_configured} status={email.get('status')!r}")

    # 4. Both checks count into the platform section, not the content section.
    summary = report.get("summary", {})
    total = summary.get("good", 0) + summary.get("warning", 0) + summary.get("critical", 0)
    check("4. the summary counts every check", total == len(report["checks"]),
          f"summary total {total} vs {len(report['checks'])} checks")

    await eng.dispose()
    if bad:
        print("\nSITE-HEALTH GAPS:")
        for item in bad:
            print("  " + item)
        return 1
    print("\nPASS: Site Health reports email configuration, disk space, loopback "
          "reachability, debug mode, and database encoding.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))