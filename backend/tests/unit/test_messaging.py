"""Unit tests for Broadcast Messaging & User Segmentation module."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.security.jwt import create_access_token
from app.main import create_app
from app.modules.messaging.application import broadcast_service
from app.modules.messaging.domain.models import (
    BroadcastCampaign,
    BroadcastRecipient,
    CampaignChannel,
    CampaignStatus,
    RecipientStatus,
    TargetSegment,
)
from app.modules.messaging.schemas.campaign import (
    BroadcastCampaignCreate,
    BroadcastCampaignUpdate,
    SegmentEstimateResponse,
)
from app.modules.users.domain.models import User

# ── Domain Model Tests ───────────────────────────────────────────────────


def test_broadcast_campaign_model_creation():
    """Verify BroadcastCampaign instantiation and attributes."""
    campaign = BroadcastCampaign(
        id=uuid.uuid4(),
        title="Norouz Special Promotion",
        channel=CampaignChannel.SMS,
        target_segment=TargetSegment.ACTIVE_BUYERS,
        message_template="Happy Norouz! Use code NOROUZ1403 for 15% discount.",
        status=CampaignStatus.DRAFT,
        ab_test_enabled=False,
    )
    assert campaign.title == "Norouz Special Promotion"
    assert campaign.channel == CampaignChannel.SMS
    assert campaign.target_segment == TargetSegment.ACTIVE_BUYERS
    assert campaign.status == CampaignStatus.DRAFT
    assert campaign.total_recipients == 0
    assert campaign.success_count == 0
    assert campaign.fail_count == 0
    assert campaign.ab_test_enabled is False
    assert campaign.variant_b_template is None


def test_broadcast_recipient_model_creation():
    """Verify BroadcastRecipient instantiation and relationships."""
    c_id = uuid.uuid4()
    u_id = uuid.uuid4()
    recipient = BroadcastRecipient(
        id=uuid.uuid4(),
        campaign_id=c_id,
        user_id=u_id,
        status=RecipientStatus.PENDING,
        variant_used="A",
    )
    assert recipient.campaign_id == c_id
    assert recipient.user_id == u_id
    assert recipient.status == RecipientStatus.PENDING
    assert recipient.variant_used == "A"
    assert recipient.sent_at is None
    assert recipient.error_message is None


def test_enums_values():
    """Verify enum string representations match specifications."""
    assert [c.value for c in CampaignChannel] == ["sms", "email", "push", "in_app"]
    assert [s.value for s in TargetSegment] == [
        "all_users",
        "active_buyers",
        "inactive_users",
        "abandoned_carts",
        "wishlist_users",
    ]
    assert [cs.value for cs in CampaignStatus] == [
        "draft",
        "scheduled",
        "processing",
        "sent",
        "failed",
        "cancelled",
    ]
    assert [rs.value for rs in RecipientStatus] == ["pending", "sent", "failed"]


# ── Schema Tests ─────────────────────────────────────────────────────────


def test_campaign_create_schema_valid():
    """Verify valid campaign creation schema."""
    data = BroadcastCampaignCreate(
        title="Flash Sale Alert",
        channel=CampaignChannel.PUSH,
        target_segment=TargetSegment.ALL_USERS,
        message_template="Up to 50% off on all electronics!",
        ab_test_enabled=False,
    )
    assert data.title == "Flash Sale Alert"
    assert data.channel == CampaignChannel.PUSH
    assert data.target_segment == TargetSegment.ALL_USERS
    assert data.status == CampaignStatus.DRAFT


def test_campaign_create_schema_ab_test():
    """Verify A/B testing fields in creation schema."""
    data = BroadcastCampaignCreate(
        title="A/B Discount Test",
        channel=CampaignChannel.EMAIL,
        target_segment=TargetSegment.INACTIVE_USERS,
        message_template="Variant A: We miss you! Here is 10% off.",
        ab_test_enabled=True,
        variant_b_template="Variant B: Come back today for free shipping!",
    )
    assert data.ab_test_enabled is True
    assert data.variant_b_template is not None


def test_segment_estimate_response_schema():
    """Verify segment estimation response schema."""
    resp = SegmentEstimateResponse(
        target_segment=TargetSegment.ABANDONED_CARTS,
        estimated_count=142,
        description="Users with active carts older than 2 hours",
    )
    assert resp.target_segment == TargetSegment.ABANDONED_CARTS
    assert resp.estimated_count == 142


# ── Service Unit Tests ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_campaign_service():
    """Test broadcast_service.create_campaign."""
    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.flush = AsyncMock()
    mock_db.refresh = AsyncMock()

    data = BroadcastCampaignCreate(
        title="Spring Collection Launch",
        channel=CampaignChannel.IN_APP,
        target_segment=TargetSegment.ALL_USERS,
        message_template="Check out new spring arrivals!",
    )

    campaign = await broadcast_service.create_campaign(mock_db, data)
    assert campaign.title == "Spring Collection Launch"
    assert campaign.channel == CampaignChannel.IN_APP
    assert campaign.status == CampaignStatus.DRAFT
    mock_db.add.assert_called_once()
    mock_db.flush.assert_called_once()


@pytest.mark.asyncio
async def test_get_campaign_service():
    """Test broadcast_service.get_campaign."""
    mock_db = AsyncMock()
    camp_id = uuid.uuid4()
    mock_campaign = BroadcastCampaign(
        id=camp_id,
        title="Test Campaign",
        channel=CampaignChannel.SMS,
        target_segment=TargetSegment.ACTIVE_BUYERS,
        message_template="Hello",
        status=CampaignStatus.DRAFT,
    )
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_campaign
    mock_db.execute.return_value = mock_result

    result = await broadcast_service.get_campaign(mock_db, camp_id)
    assert result is not None
    assert result.id == camp_id
    assert result.title == "Test Campaign"


@pytest.mark.asyncio
async def test_list_campaigns_service():
    """Test broadcast_service.list_campaigns."""
    mock_db = AsyncMock()
    camp = BroadcastCampaign(
        id=uuid.uuid4(),
        title="Campaign 1",
        channel=CampaignChannel.EMAIL,
        target_segment=TargetSegment.ALL_USERS,
        message_template="Body",
        status=CampaignStatus.DRAFT,
    )

    # count scalar return
    count_result = MagicMock()
    count_result.scalar.return_value = 1

    # items scalars return
    items_result = MagicMock()
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = [camp]
    items_result.scalars.return_value = scalars_mock

    mock_db.execute.side_effect = [count_result, items_result]

    items, total = await broadcast_service.list_campaigns(mock_db, page=1, page_size=10)
    assert total == 1
    assert len(items) == 1
    assert items[0].title == "Campaign 1"


@pytest.mark.asyncio
async def test_update_campaign_service():
    """Test broadcast_service.update_campaign."""
    mock_db = AsyncMock()
    camp_id = uuid.uuid4()
    camp = BroadcastCampaign(
        id=camp_id,
        title="Initial Title",
        channel=CampaignChannel.SMS,
        target_segment=TargetSegment.ALL_USERS,
        message_template="Initial message",
        status=CampaignStatus.DRAFT,
    )

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = camp
    mock_db.execute.return_value = mock_result

    update_data = BroadcastCampaignUpdate(title="Updated Title")
    updated = await broadcast_service.update_campaign(mock_db, camp_id, update_data)
    assert updated.title == "Updated Title"


@pytest.mark.asyncio
async def test_estimate_segment_size_service():
    """Test broadcast_service.estimate_segment_size for each segment."""
    mock_db = AsyncMock()

    for seg in TargetSegment:
        count_mock = MagicMock()
        count_mock.scalar.return_value = 42
        mock_db.execute.return_value = count_mock

        count = await broadcast_service.estimate_segment_size(mock_db, seg)
        assert count == 42


@pytest.mark.asyncio
async def test_estimate_segment_size_invalid():
    """Test broadcast_service.estimate_segment_size raises on invalid segment name."""
    mock_db = AsyncMock()
    with pytest.raises(ValueError, match="Invalid segment name"):
        await broadcast_service.estimate_segment_size(mock_db, "invalid_segment_xyz")


@pytest.mark.asyncio
async def test_send_campaign_service_success():
    """Test broadcast_service.send_campaign execution and metrics update."""
    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    camp_id = uuid.uuid4()
    u1_id = uuid.uuid4()
    u2_id = uuid.uuid4()

    camp = BroadcastCampaign(
        id=camp_id,
        title="Weekend Promotion",
        channel=CampaignChannel.IN_APP,
        target_segment=TargetSegment.ALL_USERS,
        message_template="Enjoy 10% off today!",
        status=CampaignStatus.DRAFT,
        ab_test_enabled=False,
    )

    # 1. get_campaign call
    res_get = MagicMock()
    res_get.scalar_one_or_none.return_value = camp

    # 2. segment user IDs
    res_users_ids = MagicMock()
    res_users_ids.scalars.return_value.all.return_value = [u1_id, u2_id]

    # 3. users objects query
    user1 = User(id=u1_id, phone="09121111111", email="u1@example.com", is_active=True)
    user2 = User(id=u2_id, phone="09122222222", email="u2@example.com", is_active=True)
    res_users = MagicMock()
    res_users.scalars.return_value.all.return_value = [user1, user2]

    mock_db.execute.side_effect = [res_get, res_users_ids, res_users]

    notif_target = (
        "app.modules.notifications.application.notification_service."
        "NotificationService.create_notification"
    )
    with patch(notif_target, new_callable=AsyncMock) as mock_create_notif:
        mock_create_notif.return_value = MagicMock()
        result = await broadcast_service.send_campaign(mock_db, camp_id)

        assert result.status == CampaignStatus.SENT
        assert result.total_recipients == 2
        assert result.success_count == 2
        assert result.fail_count == 0
        assert result.sent_at is not None
        assert mock_create_notif.call_count == 2


@pytest.mark.asyncio
async def test_send_campaign_service_ab_testing():
    """Test A/B testing variant alternation in send_campaign."""
    mock_db = AsyncMock()
    camp_id = uuid.uuid4()
    u1_id = uuid.uuid4()
    u2_id = uuid.uuid4()

    camp = BroadcastCampaign(
        id=camp_id,
        title="A/B Promotion",
        channel=CampaignChannel.PUSH,
        target_segment=TargetSegment.ACTIVE_BUYERS,
        message_template="Template A",
        ab_test_enabled=True,
        variant_b_template="Template B",
        status=CampaignStatus.DRAFT,
    )

    res_get = MagicMock()
    res_get.scalar_one_or_none.return_value = camp

    res_users_ids = MagicMock()
    res_users_ids.scalars.return_value.all.return_value = [u1_id, u2_id]

    user1 = User(id=u1_id, phone="09121111111", email="u1@example.com", is_active=True)
    user2 = User(id=u2_id, phone="09122222222", email="u2@example.com", is_active=True)
    res_users = MagicMock()
    res_users.scalars.return_value.all.return_value = [user1, user2]

    mock_db.execute.side_effect = [res_get, res_users_ids, res_users]

    added_recipients: list[BroadcastRecipient] = []

    def mock_add(obj):
        if isinstance(obj, BroadcastRecipient):
            added_recipients.append(obj)

    mock_db.add = MagicMock(side_effect=mock_add)

    result = await broadcast_service.send_campaign(mock_db, camp_id)
    assert result.status == CampaignStatus.SENT
    assert len(added_recipients) == 2
    assert added_recipients[0].variant_used == "A"
    assert added_recipients[1].variant_used == "B"


@pytest.mark.asyncio
async def test_send_campaign_already_sent_raises():
    """Test sending an already-sent campaign raises ValueError."""
    mock_db = AsyncMock()
    camp_id = uuid.uuid4()
    camp = BroadcastCampaign(
        id=camp_id,
        title="Completed Campaign",
        channel=CampaignChannel.SMS,
        target_segment=TargetSegment.ALL_USERS,
        message_template="Msg",
        status=CampaignStatus.SENT,
    )
    res = MagicMock()
    res.scalar_one_or_none.return_value = camp
    mock_db.execute.return_value = res

    with pytest.raises(ValueError, match="already in 'sent' state"):
        await broadcast_service.send_campaign(mock_db, camp_id)


@pytest.mark.asyncio
async def test_send_campaign_empty_audience():
    """Test send_campaign when no target users exist in the segment."""
    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    camp_id = uuid.uuid4()
    camp = BroadcastCampaign(
        id=camp_id,
        title="Empty Audience Campaign",
        channel=CampaignChannel.SMS,
        target_segment=TargetSegment.ABANDONED_CARTS,
        message_template="Your cart is waiting",
        status=CampaignStatus.DRAFT,
    )

    res_get = MagicMock()
    res_get.scalar_one_or_none.return_value = camp

    res_empty_users = MagicMock()
    res_empty_users.scalars.return_value.all.return_value = []

    mock_db.execute.side_effect = [res_get, res_empty_users]

    result = await broadcast_service.send_campaign(mock_db, camp_id)
    assert result.status == CampaignStatus.SENT
    assert result.total_recipients == 0
    assert result.success_count == 0
    assert result.fail_count == 0


@pytest.mark.asyncio
async def test_dispatch_channels():
    """Test individual recipient dispatch across SMS, Email, Push with missing details."""
    mock_db = AsyncMock()
    user_no_phone = User(id=uuid.uuid4(), phone="", email="u@example.com", is_active=True)
    user_no_email = User(id=uuid.uuid4(), phone="09121111111", email=None, is_active=True)

    # SMS missing phone
    ok, err = await broadcast_service._dispatch_single_recipient(
        mock_db, CampaignChannel.SMS, "Title", "Body", user_no_phone
    )
    assert ok is False
    assert "no phone" in err.lower()

    # Email missing email
    ok, err = await broadcast_service._dispatch_single_recipient(
        mock_db, CampaignChannel.EMAIL, "Title", "Body", user_no_email
    )
    assert ok is False
    assert "no email" in err.lower()

    # Push with valid user
    ok, err = await broadcast_service._dispatch_single_recipient(
        mock_db, CampaignChannel.PUSH, "Title", "Body", user_no_email
    )
    assert ok is True
    assert err is None


# ── API Route Integration Tests ──────────────────────────────────────────


@pytest.fixture
def test_admin_headers():
    token = create_access_token(
        subject=str(uuid.uuid4()),
        extra_claims={"roles": ["super_admin"], "permissions": ["*"]},
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def test_user_headers():
    token = create_access_token(
        subject=str(uuid.uuid4()),
        extra_claims={"roles": ["customer"], "permissions": ["orders:read"]},
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_route_unauthorized_access():
    """Verify unauthorized users cannot access messaging routes."""
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/messaging/campaigns")
        assert resp.status_code == 401


@pytest.mark.asyncio
async def test_route_forbidden_for_regular_user(test_user_headers):
    """Verify regular customers without messaging permission are forbidden."""
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/messaging/campaigns", headers=test_user_headers)
        assert resp.status_code == 403


@pytest.mark.asyncio
async def test_route_list_campaigns(test_admin_headers):
    """Verify GET /api/v1/messaging/campaigns returns campaign list."""
    app = create_app()
    camp_id = uuid.uuid4()
    fake_campaign = BroadcastCampaign(
        id=camp_id,
        title="Admin List Campaign",
        channel=CampaignChannel.PUSH,
        target_segment=TargetSegment.ALL_USERS,
        message_template="Notification message",
        status=CampaignStatus.DRAFT,
        total_recipients=0,
        success_count=0,
        fail_count=0,
        ab_test_enabled=False,
    )
    fake_campaign.created_at = datetime.now(UTC)
    fake_campaign.updated_at = datetime.now(UTC)

    with patch(
        "app.modules.messaging.application.broadcast_service.list_campaigns",
        new_callable=AsyncMock,
    ) as mock_list:
        mock_list.return_value = ([fake_campaign], 1)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/v1/messaging/campaigns", headers=test_admin_headers)
            assert resp.status_code == 200
            data = resp.json()
            assert data["total"] == 1
            assert len(data["items"]) == 1
            assert data["items"][0]["title"] == "Admin List Campaign"


@pytest.mark.asyncio
async def test_route_create_campaign(test_admin_headers):
    """Verify POST /api/v1/messaging/campaigns creates a campaign."""
    app = create_app()
    camp_id = uuid.uuid4()
    fake_campaign = BroadcastCampaign(
        id=camp_id,
        title="New API Campaign",
        channel=CampaignChannel.SMS,
        target_segment=TargetSegment.ACTIVE_BUYERS,
        message_template="Special offer for buyers",
        status=CampaignStatus.DRAFT,
        total_recipients=0,
        success_count=0,
        fail_count=0,
        ab_test_enabled=False,
    )
    fake_campaign.created_at = datetime.now(UTC)
    fake_campaign.updated_at = datetime.now(UTC)

    with patch(
        "app.modules.messaging.application.broadcast_service.create_campaign",
        new_callable=AsyncMock,
    ) as mock_create:
        mock_create.return_value = fake_campaign

        payload = {
            "title": "New API Campaign",
            "channel": "sms",
            "target_segment": "active_buyers",
            "message_template": "Special offer for buyers",
            "ab_test_enabled": False,
        }

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/messaging/campaigns",
                json=payload,
                headers=test_admin_headers,
            )
            assert resp.status_code == 201
            data = resp.json()
            assert data["id"] == str(camp_id)
            assert data["title"] == "New API Campaign"
            assert data["channel"] == "sms"
            assert data["target_segment"] == "active_buyers"


@pytest.mark.asyncio
async def test_route_create_campaign_ab_test_validation(test_admin_headers):
    """Verify validation error when A/B test is enabled but variant B is missing."""
    app = create_app()
    payload = {
        "title": "Invalid A/B Campaign",
        "channel": "email",
        "target_segment": "all_users",
        "message_template": "Template A",
        "ab_test_enabled": True,
        # missing variant_b_template
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/messaging/campaigns",
            json=payload,
            headers=test_admin_headers,
        )
        assert resp.status_code == 422


@pytest.mark.asyncio
async def test_route_get_campaign_detail(test_admin_headers):
    """Verify GET /api/v1/messaging/campaigns/{id}."""
    app = create_app()
    camp_id = uuid.uuid4()
    fake_campaign = BroadcastCampaign(
        id=camp_id,
        title="Detail Campaign",
        channel=CampaignChannel.PUSH,
        target_segment=TargetSegment.WISHLIST_USERS,
        message_template="Your wishlist items are on sale!",
        status=CampaignStatus.DRAFT,
        total_recipients=0,
        success_count=0,
        fail_count=0,
        ab_test_enabled=False,
    )
    fake_campaign.created_at = datetime.now(UTC)
    fake_campaign.updated_at = datetime.now(UTC)

    with patch(
        "app.modules.messaging.application.broadcast_service.get_campaign",
        new_callable=AsyncMock,
    ) as mock_get:
        mock_get.return_value = fake_campaign

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(
                f"/api/v1/messaging/campaigns/{camp_id}",
                headers=test_admin_headers,
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["id"] == str(camp_id)
            assert data["target_segment"] == "wishlist_users"


@pytest.mark.asyncio
async def test_route_get_campaign_not_found(test_admin_headers):
    """Verify 404 for non-existent campaign."""
    app = create_app()
    camp_id = uuid.uuid4()

    with patch(
        "app.modules.messaging.application.broadcast_service.get_campaign",
        new_callable=AsyncMock,
    ) as mock_get:
        mock_get.return_value = None

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(
                f"/api/v1/messaging/campaigns/{camp_id}",
                headers=test_admin_headers,
            )
            assert resp.status_code == 404


@pytest.mark.asyncio
async def test_route_send_campaign(test_admin_headers):
    """Verify POST /api/v1/messaging/campaigns/{id}/send triggers execution."""
    app = create_app()
    camp_id = uuid.uuid4()
    draft_campaign = BroadcastCampaign(
        id=camp_id,
        title="Send Test Campaign",
        channel=CampaignChannel.IN_APP,
        target_segment=TargetSegment.ALL_USERS,
        message_template="Dispatched message",
        status=CampaignStatus.DRAFT,
        total_recipients=0,
        success_count=0,
        fail_count=0,
        ab_test_enabled=False,
    )
    sent_campaign = BroadcastCampaign(
        id=camp_id,
        title="Send Test Campaign",
        channel=CampaignChannel.IN_APP,
        target_segment=TargetSegment.ALL_USERS,
        message_template="Dispatched message",
        status=CampaignStatus.SENT,
        total_recipients=10,
        success_count=10,
        fail_count=0,
        ab_test_enabled=False,
    )
    draft_campaign.created_at = datetime.now(UTC)
    draft_campaign.updated_at = datetime.now(UTC)
    sent_campaign.created_at = datetime.now(UTC)
    sent_campaign.updated_at = datetime.now(UTC)
    sent_campaign.sent_at = datetime.now(UTC)

    with patch(
        "app.modules.messaging.application.broadcast_service.get_campaign",
        new_callable=AsyncMock,
    ) as mock_get, patch(
        "app.modules.messaging.application.broadcast_service.send_campaign",
        new_callable=AsyncMock,
    ) as mock_send:
        mock_get.return_value = draft_campaign
        mock_send.return_value = sent_campaign

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                f"/api/v1/messaging/campaigns/{camp_id}/send",
                headers=test_admin_headers,
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["id"] == str(camp_id)
            assert data["status"] == "sent"
            assert data["total_recipients"] == 10
            assert data["success_count"] == 10


@pytest.mark.asyncio
async def test_route_estimate_segment(test_admin_headers):
    """Verify GET /api/v1/messaging/estimate/{segment} returns count."""
    app = create_app()

    with patch(
        "app.modules.messaging.application.broadcast_service.estimate_segment_size",
        new_callable=AsyncMock,
    ) as mock_estimate:
        mock_estimate.return_value = 85

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(
                "/api/v1/messaging/estimate/abandoned_carts",
                headers=test_admin_headers,
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["target_segment"] == "abandoned_carts"
            assert data["estimated_count"] == 85
            assert "description" in data


@pytest.mark.asyncio
async def test_route_estimate_invalid_segment(test_admin_headers):
    """Verify GET /api/v1/messaging/estimate/{segment} with unknown segment returns 400."""
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            "/api/v1/messaging/estimate/unknown_segment",
            headers=test_admin_headers,
        )
        assert resp.status_code == 400
        assert "Invalid segment" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_route_patch_campaign(test_admin_headers):
    """Verify PATCH /api/v1/messaging/campaigns/{id} updates campaign."""
    app = create_app()
    camp_id = uuid.uuid4()
    updated_campaign = BroadcastCampaign(
        id=camp_id,
        title="Patched Title",
        channel=CampaignChannel.PUSH,
        target_segment=TargetSegment.ALL_USERS,
        message_template="New message",
        status=CampaignStatus.DRAFT,
        total_recipients=0,
        success_count=0,
        fail_count=0,
        ab_test_enabled=False,
    )
    updated_campaign.created_at = datetime.now(UTC)
    updated_campaign.updated_at = datetime.now(UTC)

    with patch(
        "app.modules.messaging.application.broadcast_service.update_campaign",
        new_callable=AsyncMock,
    ) as mock_update:
        mock_update.return_value = updated_campaign

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.patch(
                f"/api/v1/messaging/campaigns/{camp_id}",
                json={"title": "Patched Title", "message_template": "New message"},
                headers=test_admin_headers,
            )
            assert resp.status_code == 200
            assert resp.json()["title"] == "Patched Title"


@pytest.mark.asyncio
async def test_celery_task_async_send_campaign():
    """Verify Celery background task _async_send_campaign execution."""
    from app.modules.messaging.application.tasks import _async_send_campaign

    camp_id = uuid.uuid4()
    mock_campaign = BroadcastCampaign(
        id=camp_id,
        title="Celery Task Campaign",
        channel=CampaignChannel.SMS,
        target_segment=TargetSegment.ALL_USERS,
        message_template="Msg",
        status=CampaignStatus.SENT,
        total_recipients=5,
        success_count=5,
        fail_count=0,
    )

    with (
        patch(
            "app.modules.messaging.application.tasks.async_session_factory"
        ) as mock_session_factory,
        patch(
            "app.modules.messaging.application.tasks.send_campaign",
            new_callable=AsyncMock,
        ) as mock_send,
    ):
        mock_session = AsyncMock()
        mock_session_factory.return_value.__aenter__.return_value = mock_session
        mock_send.return_value = mock_campaign

        result = await _async_send_campaign(str(camp_id))
        assert result["status"] == "success"
        assert result["campaign_id"] == str(camp_id)
        assert result["campaign_status"] == "sent"
        assert result["total_recipients"] == 5
        assert result["success_count"] == 5

