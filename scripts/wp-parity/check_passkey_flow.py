"""Passkeys are real: verified registration, verified assertion, wired UI.

    python scripts/wp-parity/check_passkey_flow.py

P1 "کاربران: پاسکی". What existed was a challenge generator nothing verified
and a frontend hook calling endpoints that 404'd. The recurring failure this
guards against is "a stub that looks like a feature": a challenge endpoint
that returns JSON is not a passkey.

The source checks assert the real ceremony exists; the live fixture drives a
software ES256 authenticator through registration, login, and every refusal
path (replay, wrong key, wrong origin, sign-count regression).
"""

from __future__ import annotations

import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def _repo_root() -> str:
    d = HERE
    for _ in range(6):
        if os.path.isdir(os.path.join(d, ".p1-tests")):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    return os.path.normpath(os.path.join(HERE, "..", ".."))


ROOT = _repo_root()
FIXTURE = os.path.join(ROOT, ".p1-tests", "passkey_flow_test.py")
SERVICE = os.path.join(ROOT, "backend", "app", "modules", "auth", "application", "passkey_service.py")
ROUTES = os.path.join(ROOT, "backend", "app", "modules", "auth", "api", "routes.py")
MODELS = os.path.join(ROOT, "backend", "app", "modules", "users", "domain", "models.py")
SETTINGS = os.path.join(ROOT, "backend", "app", "core", "config", "settings.py")
HOOK = os.path.join(ROOT, "frontend", "hooks", "use-passkey.ts")
CARD = os.path.join(ROOT, "frontend", "components", "account", "passkey-card.tsx")
LOGIN = os.path.join(ROOT, "frontend", "app", "(store)", "login", "page.tsx")
DASHBOARD = os.path.join(ROOT, "frontend", "components", "account", "account-dashboard.tsx")
CHECK_LINE = re.compile(r"^\d+\.")


def _run_fixture(path: str) -> int:
    try:
        proc = subprocess.run(
            [sys.executable, "-B", path],
            capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=300,
        )
    except subprocess.TimeoutExpired:
        print(f"  {os.path.basename(path)}: timed out")
        return 1
    for ln in (proc.stdout or "").splitlines():
        if CHECK_LINE.match(ln.strip()):
            print(f"     {ln.strip()}")
    return proc.returncode


def main() -> int:
    failures: list[str] = []

    def check(label: str, ok: bool, detail: str = "") -> None:
        print(f"  {label}: {ok}")
        if not ok:
            failures.append(f"{label}: {detail}" if detail else detail)

    def read(path: str) -> str:
        return open(path, encoding="utf-8").read() if os.path.isfile(path) else ""

    service = read(SERVICE)
    routes = read(ROUTES)
    models = read(MODELS)
    settings = read(SETTINGS)
    hook = read(HOOK)
    card = read(CARD)
    login = read(LOGIN)
    dashboard = read(DASHBOARD)

    # ── Backend: a real ceremony, not a challenge generator ─────────────────
    check("the credential table exists",
          "class PasskeyCredential" in models, "no PasskeyCredential model")
    check("the RP id and origin are configurable",
          "WEBAUTHN_RP_ID" in settings and "WEBAUTHN_ORIGIN" in settings,
          "no WebAuthn relying-party config")
    check("registration verifies the attestation",
          "verify_attestation(" in service, "attestation is never verified")
    check("registration stores the public key",
          "PasskeyCredential(" in service and "public_key=" in service,
          "the credential is not persisted")
    # BOTH ceremonies must consume their challenge. The first version of this
    # check matched any `cache_delete(key)`, so removing only the registration
    # half still passed — a per-path count is the difference between "a delete
    # exists" and "each ceremony is single-use".
    check("the challenge is stored",
          service.count("cache_set(") >= 2, "a ceremony does not store its challenge")
    check("both ceremonies consume their challenge",
          service.count("cache_delete(key)") >= 2,
          "only one ceremony is single-use")
    check("authentication verifies the signature",
          "verify_signature(" in service, "assertion signature is never verified")
    check("the sign count is checked",
          "passkey_sign_count_regression" in service,
          "no cloned-authenticator check")
    # The library's origin check is a suffix match; the service must do its own
    # exact comparison or `https://evil-localhost` passes for rp_id localhost.
    check("the origin is compared exactly",
          "origin != _origin()" in service,
          "origin is not compared exactly (library suffix check is not enough)")
    check("raw WebAuthn signatures are converted to DER",
          "_signature_to_der" in service,
          "raw r||s signatures would fail verification")
    check("the routes exist",
          all(
              p in routes
              for p in (
                  '"/mfa/passkey/register/options"',
                  '"/mfa/passkey/register/verify"',
                  '"/mfa/passkey/login/options"',
                  '"/mfa/passkey/login/verify"',
                  '"/mfa/passkey/credentials"',
              )
          ),
          "one or more passkey routes are missing")
    check("the security-status no longer calls passkeys a stub",
          "not implemented (registration options" not in routes,
          "the status payload still says passkeys are not implemented")

    # ── Frontend: hook + consumers ──────────────────────────────────────────
    check("the hook calls the real verify endpoints",
          "/auth/mfa/passkey/register/verify" in hook
          and "/auth/mfa/passkey/login/verify" in hook,
          "the hook does not call the verify endpoints")
    check("the hook no longer treats 404 as expected",
          "404" not in hook or "not implemented" not in hook,
          "the hook still guards against endpoints it expects to be missing")
    check("the passkey card is a consumer",
          "usePasskey" in card and "registerPasskey(" in card,
          "no consumer for the hook")
    check("the card is mounted on the account screen",
          "<PasskeyCard" in dashboard, "the card is never rendered")
    check("the login page offers passkey sign-in",
          "authenticateWithPasskey(" in login and "handlePasskeyLogin" in login,
          "no passkey login affordance")

    # ── Live behaviour ───────────────────────────────────────────────────────
    if not os.path.isfile(FIXTURE):
        check("the passkey fixture exists", False, FIXTURE)
    else:
        rc = _run_fixture(FIXTURE)
        check("the passkey ceremony holds", rc == 0, f"exit {rc}")

    if failures:
        print("\nFAIL:")
        for f in failures:
            print(f"  {f}")
        return 1
    print("\nPASS: passkeys are a real ceremony — verified registration and "
          "assertion, with replay/wrong-key/wrong-origin/count checks.")
    return 0


if __name__ == "__main__":
    sys.exit(main())