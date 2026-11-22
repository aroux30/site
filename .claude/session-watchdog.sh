#!/usr/bin/env bash
# Shutdown watchdog: reports when the three monitored sessions have finished.
#
# Matching is by session NAME, not id. The desktop app's "local_*" ids and the
# claude CLI's sessionIds are different namespaces, and two of the three target
# sessions share the exact same name, so name prefix + state file is what makes
# this reliable.
#
# "status" is the real completion signal, not process existence: a finished
# session stays alive in the desktop app waiting for input, so it never exits.
#   busy  -> a turn is in flight, work is not done
#   other -> turn complete, work is done
#
# Exit codes:
#   0  -> all monitored sessions finished; caller may shut down
#   10 -> at least one still working; caller must NOT shut down
#   11 -> cannot tell yet; caller must NOT shut down (fail-safe: no false shutdown)

set -uo pipefail

CLAUDE_BIN="C:/Users/Administrator/AppData/Local/Claude-3p/claude-code/2.1.281/claude.exe"
STATE_FILE="C:/Users/Administrator/Desktop/site/.claude/watchdog-seen.txt"
PREFIX="Study the following CMS repositories"
EXPECTED=3

if [[ ! -x "$CLAUDE_BIN" && ! -f "$CLAUDE_BIN" ]]; then
  echo "UNDETERMINED: claude binary not found at $CLAUDE_BIN" >&2
  exit 11
fi

RAW=$("$CLAUDE_BIN" agents --json 2>/dev/null)
# Test hook: WATCHDOG_FAKE_JSON lets the fixture-based tests exercise all three
# outcomes without waiting for real sessions to finish.
if [[ -n "${WATCHDOG_FAKE_JSON:-}" && -f "${WATCHDOG_FAKE_JSON}" ]]; then
  RAW=$(cat "$WATCHDOG_FAKE_JSON")
fi
if [[ -z "$RAW" ]]; then
  echo "UNDETERMINED: 'claude agents --json' returned nothing" >&2
  exit 11
fi

# Parse with node; emit "sessionId<TAB>status<TAB>name" for the tracked sessions.
PARSED=$(printf '%s' "$RAW" | PREFIX="$PREFIX" node -e '
let s="";process.stdin.on("data",d=>s+=d).on("end",()=>{
  let a;try{a=JSON.parse(s)}catch(e){process.exit(3)}
  if(!Array.isArray(a))process.exit(3);
  const p=process.env.PREFIX;
  for(const x of a){
    if(typeof x.name==="string" && x.name.startsWith(p))
      process.stdout.write([x.sessionId,x.status,x.name].join("\t")+"\n");
  }
});' 2>/dev/null)
rc=$?

if [[ $rc -ne 0 ]]; then
  echo "UNDETERMINED: could not parse session list (node rc=$rc)" >&2
  exit 11
fi

# Record every tracked session we have ever seen, so a session that has since
# exited is still known to have existed.
touch "$STATE_FILE"
BUSY_COUNT=0
SEEN_COUNT=0
while IFS=$'\t' read -r sid status name; do
  [[ -z "${sid:-}" ]] && continue
  SEEN_COUNT=$((SEEN_COUNT+1))
  grep -qxF "$sid" "$STATE_FILE" 2>/dev/null || echo "$sid" >>"$STATE_FILE"
  if [[ "$status" == "busy" ]]; then
    BUSY_COUNT=$((BUSY_COUNT+1))
    echo "  still working ($status): $name [$sid]" >&2
  fi
done <<<"$PARSED"

SEEN_COUNT=$(sort -u "$STATE_FILE" 2>/dev/null | grep -c . | tr -d '[:space:]')
[[ -z "$SEEN_COUNT" ]] && SEEN_COUNT=0

if [[ "$BUSY_COUNT" -gt 0 ]]; then
  echo "STILL WORKING: $BUSY_COUNT tracked session(s) busy" >&2
  exit 10
fi

if [[ "$SEEN_COUNT" -ge "$EXPECTED" ]]; then
  echo "ALL DONE: all $SEEN_COUNT tracked sessions finished their work"
  exit 0
fi

echo "UNDETERMINED: only $SEEN_COUNT of $EXPECTED tracked sessions seen so far" >&2
exit 11
