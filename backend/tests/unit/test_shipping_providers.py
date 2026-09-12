"""Unit tests for Phase 14 / SHIP-001 Shipping Carrier Provider Abstraction and Adapters."""

import uuid
from unittest.mock import patch

import pytest

from app.core.exceptions.handlers import ValidationError
from app.modules.shipping.infrastructure.carrier_provider import (
    InternalRateCarrierProvider,
    PostIranCarrierProvider,
    ShippingProviderFactory,
    TipaxCarrierProvider,
)


@pytest.mark.asyncio
async def test_shipping_provider_factory_resolution():
    """Verify factory resolves known carriers and rejects unknown names."""
    internal = ShippingProviderFactory.get_provider("internal")
    assert isinstance(internal, InternalRateCarrierProvider)
    assert internal.provider_name == "internal"

    tipax = ShippingProviderFactory.get_provider("tipax")
    assert isinstance(tipax, TipaxCarrierProvider)
    assert tipax.provider_name == "tipax"

    post = ShippingProviderFactory.get_provider("post_iran")
    assert isinstance(post, PostIranCarrierProvider)

    pishtaz = ShippingProviderFactory.get_provider("pishtaz")
    assert isinstance(pishtaz, PostIranCarrierProvider)

    with pytest.raises(ValidationError) as exc_info:
        ShippingProviderFactory.get_provider("dhl_express")
    assert "Unknown or unsupported shipping provider" in exc_info.value.detail
    assert exc_info.value.error_code == "UNSUPPORTED_SHIPPING_PROVIDER"


@pytest.mark.asyncio
async def test_internal_carrier_pricing_and_dispatch():
    """Verify default internal rate calculation and tracking generation."""
    provider = InternalRateCarrierProvider()
    tehran_rate = await provider.calculate_rate(
        "تهران", weight_kg=1.0, order_amount_rials=1_000_000
    )
    assert tehran_rate == 450_000

    province_rate = await provider.calculate_rate(
        "اصفهان", weight_kg=2.0, order_amount_rials=1_000_000
    )
    # 450_000 + 50_000 (1kg extra) + 150_000 (provincial) = 650_000
    assert province_rate == 650_000

    order_id = uuid.uuid4()
    dispatch = await provider.create_shipment(
        order_id=order_id,
        recipient_name="سارا رضایی",
        recipient_phone="09121112233",
        full_address="تهران، خ آزادی",
        postal_code="1458796521",
        weight_kg=1.5,
    )
    assert dispatch.tracking_code.startswith("IRN-")
    assert dispatch.cost_rials > 0

    tracking = await provider.track_shipment(dispatch.tracking_code)
    assert tracking.tracking_code == dispatch.tracking_code
    assert tracking.status == "in_transit"
    assert len(tracking.events) >= 1

    canceled = await provider.cancel_shipment(dispatch.tracking_code)
    assert canceled is True


@pytest.mark.asyncio
async def test_tipax_carrier_dispatch_and_fail_closed():
    """Verify Tipax adapter dispatch and fail-closed behavior in production."""
    provider = TipaxCarrierProvider(api_key=f"test-key-{uuid.uuid4().hex[:12]}")
    assert provider.provider_name == "tipax"

    rate = await provider.calculate_rate("تهران", weight_kg=2.5, order_amount_rials=0)
    assert rate == 650_000 + int(1.5 * 80_000)

    dispatch = await provider.create_shipment(
        order_id=uuid.uuid4(),
        recipient_name="علی محمدی",
        recipient_phone="09351112233",
        full_address="تهران، خ انقلاب",
        postal_code="1122334455",
        weight_kg=1.0,
    )
    assert dispatch.tracking_code.startswith("TPX")
    assert dispatch.estimated_delivery_days == 1

    # In production without api_key, must fail closed
    prod_provider = TipaxCarrierProvider(api_key=None)
    mock_settings = type("MockSettings", (), {"ENVIRONMENT": "production"})()
    with patch(
        "app.modules.shipping.infrastructure.carrier_provider.get_settings",
        return_value=mock_settings,
    ):
        with pytest.raises(ValidationError) as exc:
            await prod_provider.calculate_rate("تهران", weight_kg=1.0, order_amount_rials=0)
        assert exc.value.error_code == "CARRIER_UNCONFIGURED"

        with pytest.raises(RuntimeError):
            await prod_provider.create_shipment(
                order_id=uuid.uuid4(),
                recipient_name="test",
                recipient_phone="09120000000",
                full_address="addr",
                postal_code="1234567890",
                weight_kg=1.0,
            )


@pytest.mark.asyncio
async def test_post_iran_carrier_dispatch():
    """Verify Post Iran provider produces valid Iranian postal barcode tracking numbers."""
    provider = PostIranCarrierProvider(service_id="PST-9988")
    assert provider.provider_name == "post_iran"

    dispatch = await provider.create_shipment(
        order_id=uuid.uuid4(),
        recipient_name="مریم کاظمی",
        recipient_phone="09129998877",
        full_address="شیراز، خ زند",
        postal_code="7134567890",
        weight_kg=1.0,
    )
    assert dispatch.tracking_code.startswith("1987654321")
    assert len(dispatch.tracking_code) == 20
    assert dispatch.estimated_delivery_days == 3


@pytest.mark.asyncio
async def test_api_track_shipment_endpoint():
    """Verify GET /api/v1/shipping/track/{tracking_code} carrier tracking endpoint."""
    from unittest.mock import AsyncMock, MagicMock

    from httpx import ASGITransport, AsyncClient

    from app.core.database.session import get_db
    from app.main import create_app
    from app.modules.shipping.domain.models import Shipment, ShipmentStatus

    mock_db = AsyncMock()
    mock_db.add = MagicMock()

    shipment = Shipment(
        id=uuid.uuid4(),
        order_id=uuid.uuid4(),
        method_id=uuid.uuid4(),
        tracking_code="IRN-20260911-ABCD",
        status=ShipmentStatus.IN_TRANSIT,
    )
    shipment.method = None

    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = shipment
    mock_db.execute.return_value = mock_res

    app = create_app()
    app.dependency_overrides[get_db] = lambda: mock_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/v1/shipping/track/IRN-20260911-ABCD")
        assert resp.status_code == 200
        data = resp.json()
        assert data["tracking_code"] == "IRN-20260911-ABCD"
        assert data["carrier"] == "internal"
        assert data["status"] == "in_transit"
        assert len(data["events"]) >= 1

    app.dependency_overrides.clear()
