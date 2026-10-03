"""The full WebAuthn passkey ceremony, driven by a software authenticator.

P1 "کاربران: پاسکی". Before this the backend returned a random challenge that
nothing verified and the frontend hook called endpoints that did not exist.
This fixture builds a real ES256 authenticator in-process (key pair, CBOR
attestation object, signed assertion) and drives the whole flow over HTTP:

  * register/options stores a challenge, register/verify stores the credential;
  * login/options → login/verify issues a session;
  * a replayed challenge is refused (single-use);
  * an assertion signed by the WRONG key is refused;
  * a sign-count that does not advance is refused (cloned-authenticator check);
  * a wrong origin in clientDataJSON is refused;
  * revocation removes the credential from the list and from login options.

Run:  python .p1-tests/passkey_flow_test.py
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import io
import json
import os
import struct
import sys
import uuid

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, "C:/Users/Administrator/Desktop/site/backend")

import app.main  # noqa: F401 — registers every model, as the app does

import cbor2
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

from app.core.database.session import _build_engine, async_sessionmaker
from app.core.security.jwt import create_access_token
from app.modules.rbac.domain.models import UserRole
from app.modules.users.domain.models import PasskeyCredential, User, UserProfile

bad: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  {label}: {ok}")
    if not ok:
        bad.append(f"{label}: {detail}" if detail else label)


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


class SoftAuthenticator:
    """A minimal ES256 platform authenticator, enough for the ceremony."""

    def __init__(self) -> None:
        self.key = ec.generate_private_key(ec.SECP256R1())
        self.credential_id = os.urandom(32)
        self.sign_count = 0
        self.aaguid = bytes(16)

    def cose_public_key(self) -> bytes:
        """The COSE_Key CBOR blob for the public half (ES256, EC2, P-256)."""
        numbers = self.key.public_key().public_numbers()
        cose = {
            1: 2,  # kty: EC2
            3: -7,  # alg: ES256
            -1: 1,  # crv: P-256
            -2: numbers.x.to_bytes(32, "big"),
            -3: numbers.y.to_bytes(32, "big"),
        }
        return cbor2.dumps(cose)

    def _auth_data(self, rp_id: str, *, attested: bool) -> bytes:
        rp_hash = hashlib.sha256(rp_id.encode()).digest()
        flags = 0b00000001  # UP
        if attested:
            flags |= 0b01000000  # AT
        out = rp_hash + bytes([flags]) + struct.pack("!I", self.sign_count)
        if attested:
            out += self.aaguid
            out += struct.pack("!H", len(self.credential_id))
            out += self.credential_id
            out += self.cose_public_key()
        return out

    def attestation_object(self, rp_id: str, challenge_b64: str, origin: str) -> dict:
        client_data = {
            "type": "webauthn.create",
            "challenge": challenge_b64,
            "origin": origin,
        }
        client_data_json = json.dumps(client_data).encode()
        auth_data = self._auth_data(rp_id, attested=True)
        attestation = cbor2.dumps(
            {
                "fmt": "none",
                "attStmt": {},
                "authData": auth_data,
            }
        )
        return {
            "id": b64url(self.credential_id),
            "rawId": b64url(self.credential_id),
            "type": "public-key",
            "response": {
                "clientDataJSON": base64.b64encode(client_data_json).decode(),
                "attestationObject": base64.b64encode(attestation).decode(),
            },
        }

    def assertion(
        self,
        rp_id: str,
        challenge_b64: str,
        origin: str,
        *,
        advance_count: bool = True,
        signing_key: ec.EllipticCurvePrivateKey | None = None,
    ) -> dict:
        if advance_count:
            self.sign_count += 1
        client_data = {
            "type": "webauthn.get",
            "challenge": challenge_b64,
            "origin": origin,
        }
        client_data_json = json.dumps(client_data).encode()
        auth_data = self._auth_data(rp_id, attested=False)
        signed = auth_data + hashlib.sha256(client_data_json).digest()
        der_sig = (signing_key or self.key).sign(signed, ec.ECDSA(hashes.SHA256()))
        r, s = decode_dss_signature(der_sig)
        # WebAuthn wants the raw r||s form, not DER.
        raw_sig = r.to_bytes(32, "big") + s.to_bytes(32, "big")
        return {
            "id": b64url(self.credential_id),
            "rawId": b64url(self.credential_id),
            "type": "public-key",
            "response": {
                "clientDataJSON": base64.b64encode(client_data_json).decode(),
                "authenticatorData": base64.b64encode(auth_data).decode(),
                "signature": base64.b64encode(raw_sig).decode(),
            },
        }


async def main() -> int:
    eng = _build_engine()
    Session = async_sessionmaker(eng, expire_on_commit=False)
    marker = uuid.uuid4().hex[:8]
    phone = "09" + "".join(str(int(c, 16) % 10) for c in uuid.uuid4().hex[:9])

    from app.core.config.settings import get_settings

    settings = get_settings()
    rp_id = settings.WEBAUTHN_RP_ID
    origin = settings.WEBAUTHN_ORIGIN

    created_user_ids: list[uuid.UUID] = []

    try:
        async with Session() as db:
            u = User(
                phone=phone, is_active=True, is_verified=True,
                author_slug=f"p1pk{marker}",
            )
            db.add(u)
            await db.flush()
            db.add(UserProfile(user_id=u.id, first_name=f"PK{marker}"))
            await db.commit()
            user_id = u.id
            created_user_ids.append(u.id)

        token = create_access_token(str(user_id), {"roles": ["customer"]})
        headers = {"Authorization": f"Bearer {token}"}
        auth = SoftAuthenticator()

        async with AsyncClient(
            transport=ASGITransport(app=app.main.app), base_url="http://test"
        ) as client:
            # 1. Registration options.
            r = await client.post(
                "/api/v1/auth/mfa/passkey/register/options", headers=headers
            )
            check("1. register options answers 200",
                  r.status_code == 200, f"status {r.status_code} {r.text[:200]}")
            options = r.json()
            challenge = options.get("challenge")
            check("1b. options carry a challenge",
                  bool(challenge), f"challenge={challenge!r}")

            # 2. Verify the attestation.
            attestation = auth.attestation_object(rp_id, challenge, origin)
            r = await client.post(
                "/api/v1/auth/mfa/passkey/register/verify",
                headers=headers,
                json={**attestation, "name": "دستگاه آزمایشی"},
            )
            check("2. register verify answers 200",
                  r.status_code == 200, f"status {r.status_code} {r.text[:220]}")

            async with Session() as db:
                row = (
                    await db.execute(
                        select(PasskeyCredential).where(
                            PasskeyCredential.user_id == user_id
                        )
                    )
                ).scalars().first()
                check("2b. the credential was stored",
                      row is not None, "no passkey row")
                check("2c. with the ES256 algorithm",
                      bool(row and row.public_key_alg == -7),
                      f"alg={row.public_key_alg if row else None}")
                cred_pk = row.id if row else None

            # 2d. Replaying the SAME attestation is refused: the registration
            #     challenge is single-use too, and without this the check above
            #     would only cover the login half.
            r = await client.post(
                "/api/v1/auth/mfa/passkey/register/verify",
                headers=headers,
                json={**attestation, "name": "replay"},
            )
            check("2d. a replayed registration attestation is refused",
                  r.status_code in (400, 422), f"status {r.status_code} {r.text[:160]}")

            # 3. Login: options then assertion.
            r = await client.post(
                "/api/v1/auth/mfa/passkey/login/options", json={"phone": phone}
            )
            check("3. login options answer 200",
                  r.status_code == 200, f"status {r.status_code} {r.text[:200]}")
            login_challenge = r.json().get("challenge")

            assertion = auth.assertion(rp_id, login_challenge, origin)
            r = await client.post(
                "/api/v1/auth/mfa/passkey/login/verify",
                json={"phone": phone, "credential": assertion},
            )
            check("4. login verify answers 200",
                  r.status_code == 200, f"status {r.status_code} {r.text[:220]}")
            check("4b. it issues a refresh token",
                  bool(r.json().get("refresh_token")), f"body={r.text[:160]}")

            # 5. Replay the same assertion — the challenge is single-use.
            r = await client.post(
                "/api/v1/auth/mfa/passkey/login/options", json={"phone": phone}
            )
            login_challenge2 = r.json().get("challenge")
            old_assertion = auth.assertion(rp_id, login_challenge, origin)
            r = await client.post(
                "/api/v1/auth/mfa/passkey/login/verify",
                json={"phone": phone, "credential": old_assertion},
            )
            check("5. an assertion for a stale challenge is refused",
                  r.status_code in (400, 422), f"status {r.status_code} {r.text[:160]}")

            # 6. Wrong signing key is refused.
            other = ec.generate_private_key(ec.SECP256R1())
            bad_assertion = auth.assertion(
                rp_id, login_challenge2, origin, advance_count=False, signing_key=other
            )
            r = await client.post(
                "/api/v1/auth/mfa/passkey/login/verify",
                json={"phone": phone, "credential": bad_assertion},
            )
            check("6. an assertion signed by the wrong key is refused",
                  r.status_code in (400, 422), f"status {r.status_code} {r.text[:160]}")

            # 7. Sign-count regression is refused. Stored count is now 1; send
            #    a valid signature with count 1 again (no advance).
            r = await client.post(
                "/api/v1/auth/mfa/passkey/login/options", json={"phone": phone}
            )
            challenge3 = r.json().get("challenge")
            # Force a non-advancing counter: set it back so the assertion
            # carries the same value the row already holds.
            auth.sign_count = 0
            replay_count = auth.assertion(rp_id, challenge3, origin)
            auth.sign_count = 1  # restore for later steps
            r = await client.post(
                "/api/v1/auth/mfa/passkey/login/verify",
                json={"phone": phone, "credential": replay_count},
            )
            check("7. a non-advancing sign count is refused",
                  r.status_code in (400, 422), f"status {r.status_code} {r.text[:160]}")

            # 8. Wrong origin is refused.
            r = await client.post(
                "/api/v1/auth/mfa/passkey/login/options", json={"phone": phone}
            )
            challenge4 = r.json().get("challenge")
            wrong_origin = auth.assertion(rp_id, challenge4, "https://evil-localhost")
            r = await client.post(
                "/api/v1/auth/mfa/passkey/login/verify",
                json={"phone": phone, "credential": wrong_origin},
            )
            check("8. an assertion from the wrong origin is refused",
                  r.status_code in (400, 422), f"status {r.status_code} {r.text[:160]}")

            # 9. The credential is listed.
            r = await client.get(
                "/api/v1/auth/mfa/passkey/credentials", headers=headers
            )
            check("9. credentials list answers 200",
                  r.status_code == 200, f"status {r.status_code}")
            listed = [c["id"] for c in r.json()]
            check("9b. the credential is listed",
                  str(cred_pk) in listed, f"listed={listed}")

            # 10. Revoke it; it leaves the list and the login options.
            r = await client.delete(
                f"/api/v1/auth/mfa/passkey/credentials/{cred_pk}", headers=headers
            )
            check("10. revoke answers 204",
                  r.status_code == 204, f"status {r.status_code}")
            r = await client.get(
                "/api/v1/auth/mfa/passkey/credentials", headers=headers
            )
            listed = [c["id"] for c in r.json()]
            check("10b. the revoked credential left the list",
                  str(cred_pk) not in listed, f"listed={listed}")
            r = await client.post(
                "/api/v1/auth/mfa/passkey/login/options", json={"phone": phone}
            )
            check("10c. login options are refused once no credential remains",
                  r.status_code == 404, f"status {r.status_code} {r.text[:160]}")
    finally:
        async with Session() as db:
            for uid in created_user_ids:
                await db.execute(delete(PasskeyCredential).where(PasskeyCredential.user_id == uid))
                await db.execute(delete(UserRole).where(UserRole.user_id == uid))
                await db.execute(delete(UserProfile).where(UserProfile.user_id == uid))
                await db.execute(delete(User).where(User.id == uid))
            await db.commit()
        async with Session() as db:
            left = (
                await db.execute(select(User.id).where(User.phone == phone))
            ).scalars().all()
            check("11. the probe rows were cleaned up", not left)

    await eng.dispose()
    if bad:
        print("\nPASSKEY GAPS:")
        for item in bad:
            print("  " + item)
        return 1
    print("\nPASS: the full passkey ceremony works — registration verifies and "
          "stores, login verifies the signature, and replay/wrong-key/"
          "wrong-origin/count-regression are all refused.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))