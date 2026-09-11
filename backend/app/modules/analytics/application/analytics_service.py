"""Analytics application service – event tracking, aggregation, and reporting."""

from __future__ import annotations

import uuid
from datetime import date
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import Date, cast, func, select

from app.modules.analytics.domain.models import AnalyticsEvent, DailyMetric
from app.modules.orders.domain.models import Order, OrderItem, OrderStatus

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
logger: structlog.stdlib.BoundLogger = structlog.get_logger()


class AnalyticsService:
    """Tracks events and provides analytical queries."""

    # ── Event Tracking ────────────────────────────────────────────────

    @staticmethod
    async def track_event(
        db: AsyncSession,
        *,
        event_type: str,
        event_data: dict[str, Any] | None = None,
        user_id: uuid.UUID | None = None,
        session_id: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> AnalyticsEvent:
        """Record a single analytics event."""
        event = AnalyticsEvent(
            user_id=user_id,
            session_id=session_id,
            event_type=event_type,
            event_data=event_data,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        db.add(event)
        await db.flush()
        await logger.ainfo(
            "analytics_event_tracked",
            event_id=str(event.id),
            event_type=event_type,
        )
        return event

    # ── Sales Analytics ───────────────────────────────────────────────

    @staticmethod
    async def get_sales_analytics(
        db: AsyncSession,
        period_start: date,
        period_end: date,
    ) -> dict[str, Any]:
        """Calculate sales analytics over a date range."""
        completed_statuses = [
            OrderStatus.COMPLETED,
            OrderStatus.DELIVERED,
        ]

        # Overall aggregation
        agg_stmt = select(
            func.coalesce(func.sum(Order.total), 0).label("total_sales"),
            func.count().label("order_count"),
        ).where(
            cast(Order.created_at, Date) >= period_start,
            cast(Order.created_at, Date) <= period_end,
            Order.status.in_(completed_statuses),
        )
        row = (await db.execute(agg_stmt)).one()
        total_sales = row.total_sales
        order_count = row.order_count
        avg_value = total_sales / order_count if order_count > 0 else 0.0

        # Daily breakdown
        daily_stmt = (
            select(
                cast(Order.created_at, Date).label("day"),
                func.coalesce(func.sum(Order.total), 0).label("daily_sales"),
                func.count().label("daily_count"),
            )
            .where(
                cast(Order.created_at, Date) >= period_start,
                cast(Order.created_at, Date) <= period_end,
                Order.status.in_(completed_statuses),
            )
            .group_by(cast(Order.created_at, Date))
            .order_by(cast(Order.created_at, Date))
        )
        daily_rows = (await db.execute(daily_stmt)).all()

        return {
            "total_sales": total_sales,
            "order_count": order_count,
            "average_order_value": round(avg_value, 2),
            "period_start": period_start,
            "period_end": period_end,
            "daily_breakdown": [
                {
                    "date": r.day,
                    "total_sales": r.daily_sales,
                    "order_count": r.daily_count,
                }
                for r in daily_rows
            ],
        }

    # ── Order Analytics ───────────────────────────────────────────────

    @staticmethod
    async def get_order_analytics(
        db: AsyncSession,
        period_start: date,
        period_end: date,
    ) -> dict[str, Any]:
        """Get order analytics with status breakdown."""
        total_stmt = (
            select(func.count())
            .select_from(Order)
            .where(
                cast(Order.created_at, Date) >= period_start,
                cast(Order.created_at, Date) <= period_end,
            )
        )
        total = (await db.execute(total_stmt)).scalar_one()

        status_stmt = (
            select(
                Order.status,
                func.count().label("count"),
            )
            .where(
                cast(Order.created_at, Date) >= period_start,
                cast(Order.created_at, Date) <= period_end,
            )
            .group_by(Order.status)
        )
        status_rows = (await db.execute(status_stmt)).all()

        return {
            "total_orders": total,
            "status_breakdown": {r.status.value: r.count for r in status_rows},
            "period_start": period_start,
            "period_end": period_end,
        }

    # ── Product Analytics ─────────────────────────────────────────────

    @staticmethod
    async def get_product_analytics(
        db: AsyncSession,
        period_start: date,
        period_end: date,
        top_n: int = 10,
    ) -> dict[str, Any]:
        """Get product analytics – best sellers, views, conversion rates."""
        completed_statuses = [
            OrderStatus.COMPLETED,
            OrderStatus.DELIVERED,
        ]

        # Best sellers
        best_sellers_stmt = (
            select(
                OrderItem.product_name,
                OrderItem.variant_id,
                func.sum(OrderItem.quantity).label("total_sold"),
                func.sum(OrderItem.total_price).label("total_revenue"),
            )
            .join(Order, Order.id == OrderItem.order_id)
            .where(
                cast(Order.created_at, Date) >= period_start,
                cast(Order.created_at, Date) <= period_end,
                Order.status.in_(completed_statuses),
            )
            .group_by(OrderItem.product_name, OrderItem.variant_id)
            .order_by(func.sum(OrderItem.quantity).desc())
            .limit(top_n)
        )
        seller_rows = (await db.execute(best_sellers_stmt)).all()

        # Product views from analytics events
        best_sellers = []
        for r in seller_rows:
            view_stmt = (
                select(func.count())
                .select_from(AnalyticsEvent)
                .where(
                    AnalyticsEvent.event_type == "product_view",
                    cast(AnalyticsEvent.created_at, Date) >= period_start,
                    cast(AnalyticsEvent.created_at, Date) <= period_end,
                )
            )
            view_count = (await db.execute(view_stmt)).scalar_one()

            conversion = (r.total_sold / view_count * 100) if view_count > 0 else 0.0

            best_sellers.append(
                {
                    "product_name": r.product_name,
                    "variant_id": r.variant_id,
                    "total_sold": r.total_sold,
                    "total_revenue": r.total_revenue,
                    "view_count": view_count,
                    "conversion_rate": round(conversion, 2),
                }
            )

        return {
            "best_sellers": best_sellers,
            "period_start": period_start,
            "period_end": period_end,
        }

    # ── Customer Analytics ────────────────────────────────────────────

    @staticmethod
    async def get_customer_analytics(
        db: AsyncSession,
        period_start: date,
        period_end: date,
        top_n: int = 10,
    ) -> dict[str, Any]:
        """Get customer analytics – new vs returning, top customers."""
        # Total unique customers in period
        total_stmt = select(func.count(func.distinct(Order.user_id))).where(
            cast(Order.created_at, Date) >= period_start,
            cast(Order.created_at, Date) <= period_end,
        )
        total_customers = (await db.execute(total_stmt)).scalar_one()

        # New customers: first order is within the period
        new_customers_stmt = select(func.count()).select_from(
            select(Order.user_id)
            .group_by(Order.user_id)
            .having(func.min(cast(Order.created_at, Date)) >= period_start)
            .having(func.min(cast(Order.created_at, Date)) <= period_end)
            .subquery()
        )
        new_customers = (await db.execute(new_customers_stmt)).scalar_one()
        returning_customers = total_customers - new_customers

        # Top customers by spend
        top_stmt = (
            select(
                Order.user_id,
                func.count().label("order_count"),
                func.sum(Order.total).label("total_spent"),
            )
            .where(
                cast(Order.created_at, Date) >= period_start,
                cast(Order.created_at, Date) <= period_end,
            )
            .group_by(Order.user_id)
            .order_by(func.sum(Order.total).desc())
            .limit(top_n)
        )
        top_rows = (await db.execute(top_stmt)).all()

        return {
            "total_customers": total_customers,
            "new_customers": new_customers,
            "returning_customers": returning_customers,
            "top_customers": [
                {
                    "user_id": r.user_id,
                    "order_count": r.order_count,
                    "total_spent": r.total_spent,
                }
                for r in top_rows
            ],
            "period_start": period_start,
            "period_end": period_end,
        }

    # ── Daily Metric Aggregation ──────────────────────────────────────

    @staticmethod
    async def aggregate_daily_metrics(db: AsyncSession, target_date: date) -> list[DailyMetric]:
        """Aggregate and store daily metrics for the given date."""
        metrics: list[DailyMetric] = []

        # Total sales for the day
        completed_statuses = [OrderStatus.COMPLETED, OrderStatus.DELIVERED]
        sales_stmt = select(func.coalesce(func.sum(Order.total), 0)).where(
            cast(Order.created_at, Date) == target_date,
            Order.status.in_(completed_statuses),
        )
        total_sales = (await db.execute(sales_stmt)).scalar_one()

        sales_metric = DailyMetric(
            date=target_date,
            metric_name="total_sales",
            metric_value=float(total_sales),
        )
        db.add(sales_metric)
        metrics.append(sales_metric)

        # Order count
        count_stmt = (
            select(func.count())
            .select_from(Order)
            .where(cast(Order.created_at, Date) == target_date)
        )
        order_count = (await db.execute(count_stmt)).scalar_one()

        count_metric = DailyMetric(
            date=target_date,
            metric_name="order_count",
            metric_value=float(order_count),
        )
        db.add(count_metric)
        metrics.append(count_metric)

        # Event counts by type
        event_stmt = (
            select(
                AnalyticsEvent.event_type,
                func.count().label("count"),
            )
            .where(cast(AnalyticsEvent.created_at, Date) == target_date)
            .group_by(AnalyticsEvent.event_type)
        )
        event_rows = (await db.execute(event_stmt)).all()

        for row in event_rows:
            event_metric = DailyMetric(
                date=target_date,
                metric_name=f"event_{row.event_type}",
                metric_value=float(row.count),
                dimensions={"event_type": row.event_type},
            )
            db.add(event_metric)
            metrics.append(event_metric)

        await db.flush()
        await logger.ainfo(
            "daily_metrics_aggregated",
            date=str(target_date),
            metric_count=len(metrics),
        )
        return metrics
