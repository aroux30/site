"""Blog/CMS domain models."""

import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database.base import BaseModel

# ---- Enums ----


class BlogPostStatus(str, enum.Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"
    # Submitted for editorial review. Previously this state was faked by writing
    # ARCHIVED, so every genuinely archived post showed up in the review queue.
    PENDING_REVIEW = "pending_review"


class PostVisibility(str, enum.Enum):
    """Post visibility control (WordPress parity)."""
    PUBLIC = "public"
    PRIVATE = "private"
    PASSWORD = "password"


class PostFormat(str, enum.Enum):
    """Post format (WordPress parity): controls how the post is displayed."""
    STANDARD = "standard"
    GALLERY = "gallery"
    VIDEO = "video"
    AUDIO = "audio"
    QUOTE = "quote"
    LINK = "link"
    STATUS = "status"
    IMAGE = "image"


class CommentStatus(str, enum.Enum):
    """Comment moderation status (WordPress parity)."""
    PENDING = "pending"
    APPROVED = "approved"
    SPAM = "spam"
    TRASH = "trash"


# Polymorphic comment targets (WordPress parity: wp_comments holds comments
# on posts AND pages, discriminated by the comment's target). Kept as plain
# strings to mirror SlugHistory.resource_type in wp_parity_models.py.
COMMENT_RESOURCE_BLOG_POST = "blog_post"
COMMENT_RESOURCE_CMS_PAGE = "cms_page"
#: A custom post type entry. The third target a comment can sit on, which is
#: what a type's ``supports_comments`` checkbox is asking for — without it the
#: checkbox has nothing to switch on.
COMMENT_RESOURCE_CONTENT_ENTRY = "content_entry"

# Comment types, mirroring wp_comments.comment_type. "comment" is the default and
# the only one a public reader may see; "note" is a private team note.
COMMENT_TYPE_COMMENT = "comment"
COMMENT_TYPE_NOTE = "note"
COMMENT_RESOURCE_TYPES = (
    COMMENT_RESOURCE_BLOG_POST,
    COMMENT_RESOURCE_CMS_PAGE,
    COMMENT_RESOURCE_CONTENT_ENTRY,
)


# ---- Models ----


class BlogCategory(BaseModel):
    """Blog post categories.

    Hierarchical (WordPress parity): ``parent_id`` makes a category a child of
    another, and ``description`` is the text shown on the category archive. The
    custom-taxonomy terms carry the same three fields, so the two hierarchies
    behave the same way rather than the built-in one being the odd case.

    Cycles are rejected at write time — a parent chain that loops would make
    "descendants of X" recurse forever.
    """

    __tablename__ = "blog_categories"
    __table_args__ = (
        Index("ix_blog_categories_slug", "slug"),
        Index("ix_blog_categories_parent_id", "parent_id"),
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(220), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Self-referencing: NULL means top level. ondelete=SET NULL so deleting a
    # parent promotes its children to top level rather than deleting them —
    # a child category is a thing the operator created, not an attachment.
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("blog_categories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # Sibling order within the parent; the admin list sorts by it.
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Relationships
    posts: Mapped[list["BlogPost"]] = relationship(
        "BlogPost", back_populates="category", lazy="select"
    )
    children: Mapped[list["BlogCategory"]] = relationship(
        "BlogCategory",
        back_populates="parent",
        lazy="select",
        cascade="save-update",
    )
    parent: Mapped["BlogCategory | None"] = relationship(
        "BlogCategory",
        back_populates="children",
        remote_side="BlogCategory.id",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<BlogCategory(id={self.id}, slug={self.slug})>"


class BlogPost(BaseModel):
    """Blog articles for content marketing and SEO."""

    __tablename__ = "blog_posts"
    __table_args__ = (
        Index("ix_blog_posts_slug", "slug"),
        Index("ix_blog_posts_author_id", "author_id"),
        Index("ix_blog_posts_status", "status"),
        Index("ix_blog_posts_published_at", "published_at"),
        Index("ix_blog_posts_category_id", "category_id"),
        Index("ix_blog_posts_is_featured", "is_featured"),
        Index("ix_blog_posts_deleted_at", "deleted_at"),
        Index("ix_blog_posts_translation_group", "translation_group"),
    )

    author_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=False,
    )
    locale: Mapped[str] = mapped_column(
        String(10),
        default="fa",
        nullable=False,
        server_default="fa",
    )
    # i18n: posts that are translations of one another share a group UUID.
    # None = not translated. Blog post translations additionally link through
    # the "translation" post relationship; the group makes page-level and
    # public lookups uniform.
    translation_group: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    slug: Mapped[str] = mapped_column(String(550), unique=True, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    excerpt: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    cover_image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[BlogPostStatus] = mapped_column(
        Enum(BlogPostStatus, name="blog_post_status_enum", native_enum=False),
        default=BlogPostStatus.DRAFT,
        nullable=False,
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scheduled_for: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("blog_categories.id", ondelete="SET NULL"),
        nullable=True,
    )
    # WordPress parity: featured/sticky posts appear at the top of lists
    is_featured: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        server_default=text("false"),
    )
    # Soft delete: trashed posts stay restorable until hard-deleted
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Visibility control: public (default), private (logged-in only), password-protected
    visibility: Mapped[PostVisibility] = mapped_column(
        Enum(PostVisibility, name="post_visibility_enum", native_enum=False),
        default=PostVisibility.PUBLIC,
        nullable=False,
        server_default=text("'PUBLIC'::character varying"),
    )
    # Password for password-protected posts (hashed if used)
    visibility_password: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Discussion: allow comments on this post (global setting can override)
    allow_comments: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        server_default=text("true"),
    )
    # Post format: standard, gallery, video, audio, quote, link, status, image
    post_format: Mapped[PostFormat] = mapped_column(
        Enum(PostFormat, name="post_format_enum", native_enum=False),
        default=PostFormat.STANDARD,
        nullable=False,
        server_default=text("'STANDARD'::character varying"),
    )
    # Gallery: ordered list of media asset UUIDs for gallery format posts
    gallery_image_ids: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    # Relationships
    category: Mapped[Optional["BlogCategory"]] = relationship(
        "BlogCategory", back_populates="posts"
    )
    post_tags: Mapped[list["BlogPostTag"]] = relationship(
        "BlogPostTag",
        back_populates="post",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    revisions: Mapped[list["BlogPostRevision"]] = relationship(
        "BlogPostRevision",
        back_populates="post",
        lazy="select",
        cascade="all, delete-orphan",
        order_by="BlogPostRevision.revision_number.desc()",
    )
    comments: Mapped[list["BlogComment"]] = relationship(
        "BlogComment",
        back_populates="post",
        lazy="select",
        cascade="all, delete-orphan",
    )
    meta: Mapped[list["BlogPostMeta"]] = relationship(
        "BlogPostMeta",
        back_populates="post",
        lazy="select",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<BlogPost(id={self.id}, slug={self.slug}, status={self.status})>"


class BlogTag(BaseModel):
    """Flat blog tags (taxonomy beyond categories)."""

    __tablename__ = "blog_tags"
    __table_args__ = (Index("ix_blog_tags_slug", "slug"),)

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    # Free text about the tag. Categories had this from the start; a tag could
    # not be described at all, so the editor had no field to show. Nullable
    # rather than defaulted, because "no description yet" and "an empty
    # description" are the same thing here and only one needs storing.
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    post_tags: Mapped[list["BlogPostTag"]] = relationship(
        "BlogPostTag",
        back_populates="tag",
        lazy="select",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<BlogTag(id={self.id}, slug={self.slug})>"


class BlogPostTag(BaseModel):
    """Many-to-many association between blog posts and tags."""

    __tablename__ = "blog_post_tags"
    __table_args__ = (
        UniqueConstraint("post_id", "tag_id", name="uq_blog_post_tags_post_tag"),
        # The blog tag archive lists posts BY tag — the reverse of the unique.
        Index("ix_blog_post_tags_tag_id", "tag_id"),
    )

    post_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("blog_posts.id", ondelete="CASCADE"),
        nullable=False,
    )
    tag_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("blog_tags.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Relationships
    post: Mapped["BlogPost"] = relationship("BlogPost", back_populates="post_tags")
    tag: Mapped["BlogTag"] = relationship("BlogTag", back_populates="post_tags")

    def __repr__(self) -> str:
        return f"<BlogPostTag(post_id={self.post_id}, tag_id={self.tag_id})>"


class BlogPostRevision(BaseModel):
    """Immutable snapshot of a blog post at a given revision number."""

    __tablename__ = "blog_post_revisions"
    __table_args__ = (
        UniqueConstraint("post_id", "revision_number", name="uq_blog_post_revisions_post_rev"),
        Index("ix_blog_post_revisions_post_id", "post_id"),
    )

    post_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("blog_posts.id", ondelete="CASCADE"),
        nullable=False,
    )
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    slug: Mapped[str] = mapped_column(String(550), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    excerpt: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    cover_image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    # SEO snapshot as of this revision (NULL for revisions created before the
    # columns existed — the diff treats NULL vs NULL as "unchanged").
    seo_title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    seo_description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # The post's custom fields (blog_post_meta) as of this revision, as JSON.
    # Same reasoning as the SEO columns above: a restore that silently dropped
    # the custom fields would leave a post that no longer matches the revision
    # the editor is looking at. NULL for revisions predating the column.
    meta_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    post: Mapped["BlogPost"] = relationship("BlogPost", back_populates="revisions")

    def __repr__(self) -> str:
        return f"<BlogPostRevision(post_id={self.post_id}, rev={self.revision_number})>"


class BlogPostMeta(BaseModel):
    """Key-value custom fields for blog posts (WordPress wp_postmeta parity).

    Stores arbitrary metadata per post: SEO overrides, custom display options,
    structured data, or any extension field without schema changes.
    """

    __tablename__ = "blog_post_meta"
    __table_args__ = (
        UniqueConstraint("post_id", "meta_key", name="uq_blog_post_meta_post_key"),
        Index("ix_blog_post_meta_post_id", "post_id"),
        Index("ix_blog_post_meta_meta_key", "meta_key"),
    )

    post_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("blog_posts.id", ondelete="CASCADE"),
        nullable=False,
    )
    meta_key: Mapped[str] = mapped_column(String(255), nullable=False)
    meta_value: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    post: Mapped["BlogPost"] = relationship("BlogPost", back_populates="meta")

    def __repr__(self) -> str:
        return f"<BlogPostMeta(post_id={self.post_id}, key={self.meta_key})>"


class BlogComment(BaseModel):
    """Comments on blog posts and CMS pages with threading and moderation.

    Polymorphic target (WordPress parity — wp_comments serves both posts and
    pages): ``resource_type``/``resource_id`` name the commented object while
    the legacy ``post_id`` column stays populated for post comments so every
    existing post-comment query keeps working unchanged. The check constraint
    keeps the two addressings mutually consistent.
    """

    __tablename__ = "blog_comments"
    __table_args__ = (
        Index("ix_blog_comments_post_id", "post_id"),
        Index("ix_blog_comments_author_id", "author_id"),
        Index("ix_blog_comments_parent_id", "parent_id"),
        Index("ix_blog_comments_status", "status"),
        Index("ix_blog_comments_created_at", "created_at"),
        Index("ix_blog_comments_resource", "resource_type", "resource_id"),
        # Every public read filters comment_type='comment' next to a post or a
        # status, so the index leads with the column that is always constant.
        Index("ix_blog_comments_type_post", "comment_type", "post_id", "status"),
        CheckConstraint(
            "("
            "(resource_type = 'blog_post' AND post_id IS NOT NULL AND resource_id = post_id)"
            " OR "
            "(resource_type = 'cms_page' AND post_id IS NULL AND resource_id IS NOT NULL)"
            ")",
            name="resource_consistency",
        ),
    )

    # Legacy addressing: set (and equal to resource_id) for post comments,
    # NULL for page comments.
    post_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("blog_posts.id", ondelete="CASCADE"),
        nullable=True,
    )
    # Polymorphic addressing: which CMS object the comment attaches to.
    resource_type: Mapped[str] = mapped_column(
        String(50),
        default=COMMENT_RESOURCE_BLOG_POST,
        nullable=False,
        server_default=text(f"'{COMMENT_RESOURCE_BLOG_POST}'"),
    )
    resource_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    author_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    # Guest comment fields (when author_id is NULL)
    author_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    author_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    author_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    author_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    author_user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # WordPress's ``wp_comments.comment_type``: "comment" for a real comment,
    # "note" for a private team note, "pingback"/"trackback" for linkbacks.
    # Only the first two are used here. A note is a row like any other, so the
    # moderation table can show it, but it must never reach a public read, so
    # the default "comment" keeps every existing query and every existing
    # public route correct without them having to learn about notes at all.
    comment_type: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'comment'"),
    )

    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[CommentStatus] = mapped_column(
        Enum(CommentStatus, name="comment_status_enum", native_enum=False),
        default=CommentStatus.PENDING,
        nullable=False,
        server_default=text("'PENDING'::character varying"),
    )
    # Threading: parent comment for replies (WordPress-style nested comments)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("blog_comments.id", ondelete="CASCADE"),
        nullable=True,
    )

    # Relationships
    post: Mapped["BlogPost"] = relationship("BlogPost", back_populates="comments")

    def __repr__(self) -> str:
        return (
            f"<BlogComment(id={self.id}, resource={self.resource_type}"
            f"/{self.resource_id}, status={self.status})>"
        )


class BlogLink(BaseModel):
    """A curated external link (WordPress parity: wp_links).

    The blog sidebar and "related reading" surfaces render these, and OPML
    import/export round-trips them — WordPress treats a link as a first-class
    post type, so a reader subscribed to a site's links expects the same
    import/export contract as for posts.
    """

    __tablename__ = "blog_links"
    __table_args__ = (
        Index("ix_blog_links_slug", "slug", unique=True),
        Index("ix_blog_links_visible", "is_visible"),
        Index("ix_blog_links_position", "position"),
    )

    title: Mapped[str] = mapped_column(String(300), nullable=False)
    url: Mapped[str] = mapped_column(String(2000), nullable=False)
    slug: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # OPML group: outlines[1] in the exported document, which readers show as
    # a folder. None means the link sits at the top level.
    category: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_visible: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Owner: NULL means a site-wide link, matching WordPress's link categories
    # being global rather than per-user.
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    # When this link was created. OPML export orders by it so a reader sees
    # the same order the operator does.
    link_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Click-through count, incremented on the public redirect.
    clicks: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    def __repr__(self) -> str:
        return f"<BlogLink(slug={self.slug}, url={self.url})>"
