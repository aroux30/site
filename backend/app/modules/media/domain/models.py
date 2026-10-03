"""Media asset management domain models."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.base import BaseModel


class MediaAsset(BaseModel):
    """Uploaded media files (images, documents, etc.)."""

    __tablename__ = "media_assets"
    __table_args__ = (
        Index("ix_media_assets_uploader_id", "uploader_id"),
        Index("ix_media_assets_mime_type", "mime_type"),
        Index("ix_media_assets_created_at", "created_at"),
    )

    uploader_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_url: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    alt_text: Mapped[str | None] = mapped_column(String(300), nullable=True)
    # WordPress's Title field — the fourth text field on an attachment, after
    # alt/caption/description. A gallery or lightbox shows it, and it is where
    # an operator writes "Red running shoe, side view" rather than renaming
    # the file. Nullable: NULL means "never titled" and every surface falls
    # back to file_name, exactly as before the column existed.
    title: Mapped[str | None] = mapped_column(String(300), nullable=True)
    caption: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    folder: Mapped[str | None] = mapped_column(String(300), nullable=True, index=True)
    # Focal point as relative coordinates (0..1) for smart cropping.
    focal_x: Mapped[float | None] = mapped_column(Float, nullable=True)
    focal_y: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Attachment to post: link media to a blog post (WordPress parity)
    post_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("blog_posts.id", ondelete="SET NULL"),
        nullable=True,
    )
    # Soft delete: a trashed asset keeps its row AND its bytes so it can be
    # restored. Deleting used to take both at once, so one mis-click destroyed an
    # image a product was using with no way back — which is why the delete first
    # asks what references the file and requires an explicit force.
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    # When the row was last trashed, so a retention job can purge by age the way
    # WordPress's EMPTY_TRASH_DAYS does. Set by the service, never by the client.
    trashed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Non-destructive editing produces a chain: crop the original, crop that
    # result, and every intermediate is its own asset. Without this link the
    # chain is untraceable, which is why there was no "restore the original" and
    # no undo: the editor could see the files but not where any of them came
    # from. Self-referential so a chain of any depth resolves in one hop.
    source_asset_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("media_assets.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # Which edit produced this file ("crop", "resize", "rotate", "flip"), so the
    # history can read as a list of steps rather than a list of names.
    edit_operation: Mapped[str | None] = mapped_column(String(20), nullable=True)

    def __repr__(self) -> str:
        return f"<MediaAsset(id={self.id}, file_name={self.file_name})>"
