"""Analytics background Celery tasks.

Generates pre-aggregated daily performance metrics (sales totals, items sold,
new user registrations) and stores them in the ``daily_metrics`` table.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime, timedelta
from typing import Any

import structlog
from sqlalchemy import func, select

from app.core.database.session import async_session_factory
from app.modules.analytics.domain.models import DailyMetric
from app.modules.orders.domain.models import Order, OrderItem, OrderStatus
from app.modules.users.domain.models import User
from app.worker.celery_app import celery_app

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


async def _generate_daily_report_async(target_date: date | None = None) -> dict[str, Any]:
    """Aggregate metrics for yesterday (or specified target_date) and store in daily_metrics."""
    if target_date is None:
        target_date = (datetime.now(UTC) - timedelta(days=1)).date()

    day_start = datetime.combine(target_date, datetime.min.time()).replace(tzinfo=UTC)
    day_end = datetime.combine(target_date, datetime.max.time()).replace(tzinfo=UTC)

    valid_statuses = [
        OrderStatus.CONFIRMED,
        OrderStatus.PROCESSING,
        OrderStatus.PACKING,
        OrderStatus.SHIPPED,
        OrderStatus.DELIVERED,
        OrderStatus.COMPLETED,
    ]

    async with async_session_factory() as db:
        try:
            # 1. Order totals and count
            orders_stmt = select(
                func.coalesce(func.sum(Order.total), 0),
                func.count(Order.id),
            ).where(
                Order.created_at >= day_start,
                Order.created_at <= day_end,
                Order.status.in_(valid_statuses),
            )
            orders_row = (await db.execute(orders_stmt)).one()
            order_totals = float(orders_row[0])
            order_count = int(orders_row[1])

            # 2. Total items sold
            items_stmt = (
                select(func.coalesce(func.sum(OrderItem.quantity), 0))
                .join(Order, OrderItem.order_id == Order.id)
                .where(
                    Order.created_at >= day_start,
                    Order.created_at <= day_end,
                    Order.status.in_(valid_statuses),
                )
            )
            items_sold = float((await db.execute(items_stmt)).scalar_one())

            # 3. New user registrations
            users_stmt = select(func.count(User.id)).where(
                User.created_at >= day_start,
                User.created_at <= day_end,
            )
            new_users = float((await db.execute(users_stmt)).scalar_one())

            # 4. Upsert metrics into daily_metrics
            metrics_to_record = [
                ("order_totals", order_totals, None),
                ("items_sold", items_sold, None),
                ("new_user_registrations", new_users, None),
                ("order_count", float(order_count), None),
                (
                    "daily_summary",
                    order_totals,
                    {
                        "order_totals": int(order_totals),
                        "order_count": order_count,
                        "items_sold": int(items_sold),
                        "new_user_registrations": int(new_users),
                    },
                ),
            ]

            for metric_name, value, dims in metrics_to_record:
                # Check if metric already exists for this date and metric_name
                existing_stmt = select(DailyMetric).where(
                    DailyMetric.date == target_date,
                    DailyMetric.metric_name == metric_name,
                )
                if dims is not None:
                    existing_stmt = existing_stmt.where(DailyMetric.dimensions == dims)
                else:
                    existing_stmt = existing_stmt.where(DailyMetric.dimensions.is_(None))

                existing_metric = (await db.execute(existing_stmt)).scalar_one_or_none()

                if existing_metric:
                    existing_metric.metric_value = value
                    if dims is not None:
                        existing_metric.dimensions = dims
                else:
                    metric = DailyMetric(
                        date=target_date,
                        metric_name=metric_name,
                        metric_value=value,
                        dimensions=dims,
                    )
                    db.add(metric)

            await db.commit()
            await logger.ainfo(
                "daily_report_generated",
                date=target_date.isoformat(),
                order_totals=order_totals,
                items_sold=items_sold,
                new_users=new_users,
                order_count=order_count,
            )

            return {
                "status": "success",
                "date": target_date.isoformat(),
                "order_totals": order_totals,
                "order_count": order_count,
                "items_sold": items_sold,
                "new_user_registrations": new_users,
            }
        except Exception:
            await db.rollback()
            await logger.aexception("generate_daily_report_failed", date=target_date.isoformat())
            raise


@celery_app.task(name="app.modules.analytics.application.tasks.generate_daily_report")
def generate_daily_report(report_date: str | None = None) -> dict[str, Any]:
    """Aggregate order totals, items sold, new user registrations for yesterday,

    and store rows in 'daily_metrics'.
    """
    target = date.fromisoformat(report_date) if report_date else None
    return asyncio.run(_generate_daily_report_async(target))
