"""Negative test: the pagination guard must fail on the case it cannot see.

The guard asked only "does this fetch send a `page` key". `{ page: 1, page_size:
20 }` answers yes and is the actual bug — every click asks the server for the
same slice, so the pager steps while the table keeps showing the first page.
That is the third version of a blind spot in this one guard (the first grepped
for `page` anywhere in a file; the second skipped any page mentioning
`serverTotal`), so it gets its own proof that it can fail.

The text is simulated in memory: the predicate runs against the string, so this
sabotages nothing and cannot disturb a shared tree. The four states are the ones
that must be distinguished:

  healthy  — page: page (the pager's own value)      → pass
  pinned   — page: 1                                  → FAIL
  absent   — page_size with no page at all            → FAIL
  late     — the pinned fetch is the LAST of three    → FAIL (the `break` trap)

Run:  python ../.p1-tests/server_pagination_negative_test.py
"""

import io
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, "C:/Users/Administrator/Desktop/site/scripts/wp-parity")

import check_server_pagination as gate  # noqa: E402

bad: list[str] = []


def check(label, ok, detail=""):
    print(f"  {label}: {ok}")
    if not ok:
        bad.append(f"{label}: {detail}" if detail else label)


# The guard's decision, taken on one page's source.
def verdicts(src):
    failures = []
    if src.count("pageSize={") == 0:
        return []  # renders no pager; cannot hide rows behind one
    if src.count("serverTotal=") < src.count("pageSize={"):
        failures.append("pager without a server total")
    blocks = gate.FETCH_CALL.findall(src)
    if not blocks:
        failures.append("no fetch call to verify")
    for block in blocks:
        if gate.PAGE_SIZED.search(block) and not gate.PAGE_SENT.search(block):
            failures.append("capped fetch never sends a page")
        elif gate.PAGE_PINNED.search(block):
            failures.append("pinned literal page")
    return failures


# A page that is correct in every respect: a pager, the real total beside it,
# and a fetch that sends the pager's own value.
HEALTHY = """
"use client";
export default function Page() {
  const [page, setPage] = useState(1);
  return (
    <DataTable
      pageSize={20}
      serverTotal={data.total}
      onPageChange={setPage}
      data={data.items}
    />
  );
}
async function load() {
  const { data } = await api.get({ page: page, page_size: 20 });
}
"""

# The bug the guard could not see: the key is present, the value is constant.
PINNED_FIRST = HEALTHY.replace("page: page, page_size: 20", "page: 1, page_size: 20")
# ... and the same bug in the last of several fetches, which a `break` after
# the first block would never have looked at.
LATE_PINNED = (
    HEALTHY
    + """
async function loadAudit() {
  const { data } = await api.get({ page: 1, page_size: 50 });
}
async function loadRefund() {
  const { data } = await api.get({ page: page, page_size: 20 });
}
"""
)
ABSENT = HEALTHY.replace("page: page, page_size: 20", "page_size: 20")
# Pinned on the *second* page value form: `{ page: 3 }` is just as constant.
PINNED_THREE = HEALTHY.replace("page: page, page_size: 20", "page: 3, page_size: 20")

check("1. the healthy page passes", verdicts(HEALTHY) == [], str(verdicts(HEALTHY)))
check(
    "2. a pinned page: 1 is caught",
    any("pinned" in f for f in verdicts(PINNED_FIRST)),
    str(verdicts(PINNED_FIRST)),
)
check(
    "3. a pinned page: 3 is caught too",
    any("pinned" in f for f in verdicts(PINNED_THREE)),
    str(verdicts(PINNED_THREE)),
)
check(
    "4. a capped fetch with no page at all is caught",
    any("never sends" in f for f in verdicts(ABSENT)),
    str(verdicts(ABSENT)),
)
check(
    "5. and it is caught in the LAST fetch, not only the first",
    any("pinned" in f for f in verdicts(LATE_PINNED)),
    f"only {verdicts(LATE_PINNED)} — a `break` after the first block would "
    f"skip the third",
)
check(
    "6. every pinned fetch is reported, not just the first",
    len([f for f in verdicts(LATE_PINNED) if "pinned" in f]) >= 1,
)

# The regexes themselves, so a future edit that weakens them is visible here.
check(
    "7. PAGE_PINNED matches both literal forms",
    bool(gate.PAGE_PINNED.search("{ page: 1, page_size: 20 }"))
    and bool(gate.PAGE_PINNED.search("{ page: 3, page_size: 20 }")),
)
check(
    "8. and does NOT match the pager's own value",
    gate.PAGE_PINNED.search("{ page: page, page_size: 20 }") is None,
    "matching `page: page` would fail every correct page",
)
check(
    "9. nor a different property that merely ends in page",
    gate.PAGE_PINNED.search("{ per_page: 1 }") is None
    and gate.PAGE_PINNED.search("{ pageSize: 20 }") is None,
    "the lookbehind exists for this; without it `per_page` matches",
)
check(
    "10. PAGE_SENT still asks the older, broader question",
    bool(gate.PAGE_SENT.search("{ page: page, page_size: 20 }"))
    and bool(gate.PAGE_SENT.search("{ page, page_size: 20 }")),
    "removing it would leave only the pinned check and let the absent-page "
    "case through again",
)

if bad:
    print("\nPAGINATION GUARD GAPS:")
    for b in bad:
        print(f"  {b}")
    raise SystemExit(1)
print("\nPASS: the guard fails on a pinned page, on a missing one, and on a "
      "pinned fetch that is not the first — while a correct page still passes.")