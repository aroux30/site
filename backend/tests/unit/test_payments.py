"""Unit tests for Cryptocurrency and Card-to-Card payment providers."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.modules.payments.domain.models import (
    Payment,
    PaymentProvider,
    PaymentStatus,
    PaymentTransactionType,
)
from app.modules.payments.infrastructure.provider_factory import get_payment_provider
from app.modules.payments.infrastructure.providers.card_to_card import (
    CardToCardProvider,
    format_card_pan,
)
from app.modules.payments.infrastructure.providers.crypto import (
    NowPaymentsProvider,
    SUPPORTED_CURRENCIES,
    normalize_crypto_currency,
)
from app.modules.payments.application import payment_service
from app.modules.payments.schemas.payment import (
    CardReceiptSubmitRequest,
    PaymentRejectRequest,
)


# ── Provider Factory Tests ────────────────────────────────────────────────


def test_provider_factory_resolution():
    crypto = get_payment_provider("crypto")
    assert isinstance(crypto, NowPaymentsProvider)
    assert crypto.provider_name == "crypto"

    nowpayments = get_payment_provider("nowpayments")
    assert isinstance(nowpayments, NowPaymentsProvider)

    c2c = get_payment_provider("card_transfer")
    assert isinstance(c2c, CardToCardProvider)
    assert c2c.provider_name == "card_transfer"

    c2c_alias = get_payment_provider("card_to_card")
    assert isinstance(c2c_alias, CardToCardProvider)

    wallet = get_payment_provider("wallet")
    assert wallet.provider_name == "wallet"

    mock_prov = get_payment_provider("mock")
    assert mock_prov.provider_name == "mock"

    zarinpal = get_payment_provider("zarinpal")
    assert zarinpal.provider_name == "zarinpal"

    idpay = get_payment_provider("idpay")
    assert idpay.provider_name == "idpay"

    with pytest.raises(ValueError, match="Unknown payment provider"):
        get_payment_provider("non_existent_provider")


# ── Crypto Provider Tests ─────────────────────────────────────────────────


def test_crypto_normalize_currencies():
    assert normalize_crypto_currency("usdt") == "usdttrc20"
    assert normalize_crypto_currency("USDT_TRC20") == "usdttrc20"
    assert normalize_crypto_currency("usdt_erc20") == "usdterc20"
    assert normalize_crypto_currency("erc20") == "usdterc20"
    assert normalize_crypto_currency("btc") == "btc"
    assert normalize_crypto_currency("bitcoin") == "btc"
    assert normalize_crypto_currency("eth") == "eth"
    assert normalize_crypto_currency("ethereum") == "eth"
    assert normalize_crypto_currency(None) == "usdttrc20"
    assert normalize_crypto_currency("unknown") == "usdttrc20"


@pytest.mark.asyncio
async def test_crypto_create_payment_sandbox():
    provider = NowPaymentsProvider(api_key="", sandbox=True)
    order_id = uuid.uuid4()
    result = await provider.create_payment(
        amount=60_000_000,  # 60 million IRR = ~100 USD
        order_id=order_id,
        callback_url="http://localhost:3000/callback",
        pay_currency="usdttrc20",
    )

    assert result.success is True
    assert result.authority is not None
    assert result.authority.startswith("NP-")
    assert result.gateway_url is not None
    assert "sandbox.nowpayments.io" in result.gateway_url

    raw = result.raw_response
    assert raw["pay_address"] is not None
    assert raw["qr_code_url"] is not None
    assert "api.qrserver.com" in raw["qr_code_url"]
    assert raw["pay_currency"] == "usdttrc20"
    assert raw["price_currency"] == "usd"
    assert raw["price_amount"] == 100.0


@pytest.mark.asyncio
async def test_crypto_create_payment_all_currencies():
    provider = NowPaymentsProvider(api_key="", sandbox=True)
    currencies = ["usdttrc20", "usdterc20", "btc", "eth"]

    for curr in currencies:
        result = await provider.create_payment(
            amount=30_000_000,
            order_id=uuid.uuid4(),
            callback_url="http://localhost:3000/callback",
            pay_currency=curr,
        )
        assert result.success is True
        assert result.raw_response["pay_currency"] == curr
        assert result.raw_response["pay_address"] is not None
        assert result.raw_response["qr_code_url"] is not None


@pytest.mark.asyncio
async def test_crypto_create_payment_real_api_call():
    provider = NowPaymentsProvider(api_key="live-key-123", sandbox=False)
    order_id = uuid.uuid4()

    mock_invoice_response = MagicMock()
    mock_invoice_response.status_code = 200
    mock_invoice_response.json.return_value = {
        "id": "5000000001",
        "order_id": str(order_id),
        "invoice_url": "https://nowpayments.io/payment/?iid=5000000001",
    }
    mock_invoice_response.raise_for_status = MagicMock()

    mock_payment_response = MagicMock()
    mock_payment_response.status_code = 200
    mock_payment_response.json.return_value = {
        "payment_id": "5077125051",
        "payment_status": "waiting",
        "pay_address": "TYDzsYUEpvnYmQk4zGP9sWWcTEd36d57nR",
        "price_amount": 50.0,
        "price_currency": "usd",
        "pay_amount": 50.0,
        "pay_currency": "usdttrc20",
    }

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.side_effect = [mock_invoice_response, mock_payment_response]
        result = await provider.create_payment(
            amount=30_000_000,
            order_id=order_id,
            callback_url="https://site.com/ipn",
            pay_currency="usdttrc20",
        )

        assert result.success is True
        assert result.authority == "5077125051"
        assert result.gateway_url == "https://nowpayments.io/payment/?iid=5000000001"
        assert result.raw_response["pay_address"] == "TYDzsYUEpvnYmQk4zGP9sWWcTEd36d57nR"
        assert "api.qrserver.com" in result.raw_response["qr_code_url"]


@pytest.mark.asyncio
async def test_crypto_verify_payment_sandbox():
    provider = NowPaymentsProvider(api_key="", sandbox=True)

    # Normal success
    res_success = await provider.verify_payment(
        authority="NP-TEST12345",
        amount=10_000_000,
    )
    assert res_success.success is True
    assert res_success.ref_id is not None
    assert res_success.raw_response["payment_status"] == "finished"

    # Simulated failure
    res_fail = await provider.verify_payment(
        authority="NP-TEST-FAIL",
        amount=10_000_000,
    )
    assert res_fail.success is False
    assert res_fail.error_code == "CRYPTO_PAYMENT_FAILED"


@pytest.mark.asyncio
async def test_crypto_verify_payment_real_api():
    provider = NowPaymentsProvider(api_key="live-key-123", sandbox=False)

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "payment_id": 5077125051,
        "payment_status": "finished",
        "actually_paid": 50.0,
        "pay_currency": "usdttrc20",
    }
    mock_resp.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.get", return_value=mock_resp):
        result = await provider.verify_payment(
            authority="5077125051",
            amount=30_000_000,
        )
        assert result.success is True
        assert result.ref_id == "5077125051"


@pytest.mark.asyncio
async def test_crypto_refund_wallet_credit():
    provider = NowPaymentsProvider(api_key="", sandbox=True)
    user_id = uuid.uuid4()
    mock_db = MagicMock()

    with patch(
        "app.modules.wallet.application.wallet_service.credit",
        new=AsyncMock(return_value=MagicMock(id=uuid.uuid4())),
    ):
        result = await provider.refund(
            authority="NP-REFUND123",
            amount=500_000,
            user_id=user_id,
            db=mock_db,
        )
        assert result.success is True
        assert result.raw_response["method"] == "internal_wallet_credit"


def test_crypto_ipn_signature_verification():
    secret = "my-secret-key-123"
    provider = NowPaymentsProvider(ipn_secret=secret)

    raw_body = b'{"payment_id":5077125051,"payment_status":"finished"}'
    # Compute signature manually
    import hashlib
    import hmac
    import json

    payload = json.loads(raw_body)
    sorted_payload = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    valid_sig = hmac.new(
        secret.encode("utf-8"), sorted_payload.encode("utf-8"), hashlib.sha512
    ).hexdigest()

    assert provider.verify_ipn_signature(raw_body, valid_sig) is True
    assert provider.verify_ipn_signature(raw_body, "wrong-signature") is False


# ── Card-to-Card Provider Tests ───────────────────────────────────────────


def test_format_card_pan():
    assert format_card_pan("6219861012345678") == "6219-8610-1234-5678"
    assert format_card_pan("6219-8610-1234-5678") == "6219-8610-1234-5678"
    assert format_card_pan("123") == "123"


@pytest.mark.asyncio
async def test_card_to_card_create_payment():
    provider = CardToCardProvider(
        card_number="6219-8610-9999-8888",
        card_holder="فروشگاه آزمایشی",
        bank_name="بانک سامان",
    )
    order_id = uuid.uuid4()

    result = await provider.create_payment(
        amount=5_000_000,
        order_id=order_id,
        callback_url="http://localhost:3000/callback",
    )

    assert result.success is True
    assert result.authority.startswith("C2C-")
    assert result.card_pan == "6219-8610-9999-8888"
    assert result.gateway_url is not None
    assert "checkout/card-transfer" in result.gateway_url

    raw = result.raw_response
    assert raw["card_number"] == "6219-8610-9999-8888"
    assert raw["card_holder"] == "فروشگاه آزمایشی"
    assert raw["bank_name"] == "بانک سامان"
    assert raw["requires_admin_approval"] is True
    assert raw["status"] == "pending_receipt"


@pytest.mark.asyncio
async def test_card_to_card_verify_requires_admin():
    provider = CardToCardProvider()

    # Regular check returns WAITING_ADMIN_APPROVAL
    result = await provider.verify_payment(
        authority="C2C-ABC12345",
        amount=5_000_000,
    )
    assert result.success is False
    assert result.error_code == "WAITING_ADMIN_APPROVAL"

    # Pre-approved test check succeeds
    result_approved = await provider.verify_payment(
        authority="C2C-ABC12345-APPROVED",
        amount=5_000_000,
    )
    assert result_approved.success is True
    assert result_approved.ref_id == "REF-C2C-ABC12345-APPROVED"


@pytest.mark.asyncio
async def test_card_to_card_refund():
    provider = CardToCardProvider()

    # Manual bank refund fallback
    result = await provider.refund(
        authority="C2C-12345",
        amount=1_000_000,
    )
    assert result.success is True
    assert result.ref_id.startswith("C2CREFUND-")

    # Internal wallet credit
    user_id = uuid.uuid4()
    mock_db = MagicMock()
    with patch(
        "app.modules.wallet.application.wallet_service.credit",
        new=AsyncMock(return_value=MagicMock(id=uuid.uuid4())),
    ):
        res_wallet = await provider.refund(
            authority="C2C-12345",
            amount=1_000_000,
            user_id=user_id,
            db=mock_db,
        )
        assert res_wallet.success is True
        assert res_wallet.raw_response["method"] == "internal_wallet_credit"


# ── Payment Methods Listing Test ──────────────────────────────────────────


def test_get_payment_methods_includes_crypto_and_card():
    methods_response = payment_service.get_payment_methods()
    method_providers = {m.provider: m for m in methods_response.methods}

    # Verify Crypto presence and properties
    assert PaymentProvider.CRYPTO in method_providers
    crypto = method_providers[PaymentProvider.CRYPTO]
    assert crypto.is_enabled is True
    assert "ارز دیجیتال" in crypto.name_fa
    assert "تتر" in crypto.name_fa or "NowPayments" in crypto.name
    assert crypto.icon == "crypto"
    assert crypto.instructions is not None
    assert "تتر" in crypto.instructions

    # Verify Card-to-Card presence and properties
    assert PaymentProvider.CARD_TRANSFER in method_providers
    c2c = method_providers[PaymentProvider.CARD_TRANSFER]
    assert c2c.is_enabled is True
    assert c2c.name_fa == "کارت به کارت"
    assert c2c.icon == "credit-card"
    assert c2c.instructions is not None
    assert "۶۲۱۹-۸۶۱۰" in c2c.instructions or "سامان" in c2c.instructions

    # Verify Wallet presence
    assert PaymentProvider.WALLET in method_providers
    wallet = method_providers[PaymentProvider.WALLET]
    assert wallet.name_fa == "کیف پول"
    assert wallet.icon == "wallet"


# ── Service Admin & Receipt Submission Tests ──────────────────────────────


@pytest.mark.asyncio
async def test_submit_card_receipt_logic():
    payment_id = uuid.uuid4()
    order_id = uuid.uuid4()
    user_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    mock_payment = Payment(
        id=payment_id,
        order_id=order_id,
        amount=1_000_000,
        currency="IRR",
        provider=PaymentProvider.CARD_TRANSFER,
        status=PaymentStatus.PENDING,
        authority="C2C-TESTAUTH",
        created_at=now,
        updated_at=now,
    )

    mock_db = MagicMock()
    mock_db.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=mock_payment))
    )
    mock_db.flush = AsyncMock()
    mock_db.add = MagicMock()

    response = await payment_service.submit_card_receipt(
        mock_db,
        payment_id=payment_id,
        user_id=user_id,
        tracking_code="TRK-987654321",
        card_pan="6037-9911-2233-4455",
        receipt_image_url="https://minio/bucket/receipt.jpg",
        notes="واریز از طریق همراه بانک",
    )

    assert response.status == PaymentStatus.PENDING
    assert mock_payment.extra_data["tracking_code"] == "TRK-987654321"
    assert mock_payment.extra_data["customer_card_pan"] == "6037-9911-2233-4455"
    assert mock_payment.extra_data["receipt_image_url"] == "https://minio/bucket/receipt.jpg"


@pytest.mark.asyncio
async def test_admin_approve_card_payment():
    payment_id = uuid.uuid4()
    order_id = uuid.uuid4()
    admin_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    mock_payment = Payment(
        id=payment_id,
        order_id=order_id,
        amount=1_000_000,
        currency="IRR",
        provider=PaymentProvider.CARD_TRANSFER,
        status=PaymentStatus.PENDING,
        authority="C2C-TESTAUTH",
        extra_data={"tracking_code": "TRK-987654321"},
        created_at=now,
        updated_at=now,
    )

    mock_db = MagicMock()
    mock_db.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=mock_payment))
    )
    mock_db.flush = AsyncMock()
    mock_db.add = MagicMock()

    response = await payment_service.approve_payment(
        mock_db,
        payment_id=payment_id,
        admin_user_id=admin_id,
    )

    assert response.status == PaymentStatus.COMPLETED
    assert mock_payment.status == PaymentStatus.COMPLETED
    assert mock_payment.extra_data["approved_by"] == str(admin_id)
    assert mock_payment.provider_transaction_id == "TRK-987654321"


@pytest.mark.asyncio
async def test_admin_reject_card_payment():
    payment_id = uuid.uuid4()
    order_id = uuid.uuid4()
    admin_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    mock_payment = Payment(
        id=payment_id,
        order_id=order_id,
        amount=1_000_000,
        currency="IRR",
        provider=PaymentProvider.CARD_TRANSFER,
        status=PaymentStatus.PENDING,
        authority="C2C-TESTAUTH",
        created_at=now,
        updated_at=now,
    )

    mock_db = MagicMock()
    mock_db.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=mock_payment))
    )
    mock_db.flush = AsyncMock()
    mock_db.add = MagicMock()

    response = await payment_service.reject_payment(
        mock_db,
        payment_id=payment_id,
        admin_user_id=admin_id,
        reason="شماره پیگیری نامعتبر است",
    )

    assert response.status == PaymentStatus.FAILED
    assert mock_payment.status == PaymentStatus.FAILED
    assert mock_payment.extra_data["rejected_by"] == str(admin_id)
    assert mock_payment.extra_data["rejection_reason"] == "شماره پیگیری نامعتبر است"
