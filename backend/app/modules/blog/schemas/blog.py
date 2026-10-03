"""Pydantic v2 schemas for the Blog module."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.modules.blog.domain.models import BlogPostStatus, PostVisibility, CommentStatus, PostFormat

# ============================================================================
# Category Schemas
# ============================================================================


class BlogCategoryCreate(BaseModel):
    """Schema for creating a blog category."""

    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(..., min_length=1, max_length=200, description="Category name")
    slug: str | None = Field(
        None,
        max_length=220,
        description="URL-friendly slug (auto-generated from name if omitted)",
    )
    description: str | None = Field(
        None, max_length=2000, description="Text shown on the category archive"
    )
    parent_id: uuid.UUID | None = Field(
        None, description="Parent category; null makes this a top-level category"
    )
    position: int = Field(0, ge=0, description="Order among its siblings")


class BlogCategoryResponse(BaseModel):
    """Response schema for a blog category."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    description: str | None = None
    parent_id: uuid.UUID | None = None
    position: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None
    post_count: int | None = Field(0, description="Number of published posts in this category")
    # Populated only by the tree endpoints; None on a flat row.
    children: list["BlogCategoryResponse"] | None = None
    # Full ancestor path ("لپ‌تاپ / گیمینگ"), for breadcrumbs on the archive.
    ancestors: list[dict[str, Any]] | None = None


# ============================================================================
# Tag Schemas
# ============================================================================


class BlogTagCreate(BaseModel):
    """Schema for creating a blog tag."""

    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(..., min_length=1, max_length=100, description="Tag name")
    slug: str | None = Field(
        None,
        max_length=120,
        description="URL-friendly slug (auto-generated from name if omitted)",
    )


class BlogTagResponse(BaseModel):
    """Response schema for a blog tag."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    # Carried on the response so the edit form can pre-fill it: without this
    # the field is write-only, and saving an unchanged tag would send an empty
    # string and silently clear whatever was there.
    description: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    post_count: int | None = Field(0, description="Number of published posts with this tag")


# ============================================================================
# Post Schemas
# ============================================================================


class BlogPostCreate(BaseModel):
    """Schema for creating a new blog post."""

    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(..., min_length=1, max_length=500, description="Article title")
    slug: str | None = Field(
        None,
        max_length=550,
        description="URL-friendly slug (auto-generated from title if omitted)",
    )
    content: str = Field(..., min_length=1, description="Article body in Markdown or HTML")
    excerpt: str | None = Field(None, max_length=1000, description="Brief summary or excerpt")
    cover_image_url: str | None = Field(None, max_length=500, description="Cover/header image URL")
    status: BlogPostStatus = Field(
        default=BlogPostStatus.DRAFT,
        description="Publication status: draft, pending_review, published, or archived",
    )
    locale: str = Field(
        default="fa",
        min_length=2,
        max_length=10,
        description="Content language code (fa, en, ar, …)",
    )
    published_at: datetime | None = Field(
        None,
        description="Publication timestamp; automatically set to now if status is published",
    )
    category_id: uuid.UUID | None = Field(None, description="Associated category UUID")
    tag_ids: list[uuid.UUID] | None = Field(
        None,
        description="Tags to attach to the post (replaces existing set when provided)",
    )
    scheduled_for: datetime | None = Field(
        None,
        description="Future timestamp at which the post should auto-publish",
    )
    author_id: uuid.UUID | None = Field(
        None,
        description="Author user UUID (automatically set from current user if omitted)",
    )
    is_featured: bool = Field(
        default=False,
        description="Featured/sticky posts appear at the top of lists",
    )
    visibility: PostVisibility = Field(
        default=PostVisibility.PUBLIC,
        description="Post visibility: public, private, or password-protected",
    )
    visibility_password: str | None = Field(
        None,
        max_length=255,
        description="Password for password-protected posts",
    )
    allow_comments: bool | None = Field(
        default=None,
        description=(
            "Allow comments on this post. Omit to take the site's "
            "default_comment_status setting; pass true/false to override it."
        ),
    )
    post_format: PostFormat = Field(
        default=PostFormat.STANDARD,
        description="Post format: standard, gallery, video, audio, quote, link, status, image",
    )
    gallery_image_ids: list[str] | None = Field(
        None,
        description="Ordered list of media asset UUIDs for gallery format posts",
    )


class BlogPostUpdate(BaseModel):
    """Schema for updating an existing blog post (all fields optional)."""

    model_config = ConfigDict(str_strip_whitespace=True)

    title: str | None = Field(None, min_length=1, max_length=500)
    slug: str | None = Field(None, max_length=550)
    content: str | None = Field(None, min_length=1)
    excerpt: str | None = Field(None, max_length=1000)
    cover_image_url: str | None = Field(None, max_length=500)
    status: BlogPostStatus | None = None
    locale: str | None = Field(None, min_length=2, max_length=10)
    published_at: datetime | None = None
    category_id: uuid.UUID | None = None
    tag_ids: list[uuid.UUID] | None = Field(
        None,
        description="Tags to attach to the post (replaces existing set when provided)",
    )
    scheduled_for: datetime | None = None
    # Reassigning the author is a legitimate editorial action (an editor taking
    # over a draft, a post written under someone else's name), so the update
    # schema carries it. It was create-only, which left no way to change it.
    author_id: uuid.UUID | None = Field(
        None,
        description="Move the post to another author (defaults to keeping the current one)",
    )
    is_featured: bool | None = None
    visibility: PostVisibility | None = None
    visibility_password: str | None = Field(None, max_length=255)
    allow_comments: bool | None = None
    post_format: PostFormat | None = None
    gallery_image_ids: list[str] | None = None


class BlogPostResponse(BaseModel):
    """List / summary view of a blog post."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    author_id: uuid.UUID
    # Public identity for /author/<slug> and the %author% permalink token.
    # Null for a user who has not been given one; the storefront falls back to
    # a plain link rather than building a broken URL.
    author_slug: str | None = None
    title: str
    slug: str
    excerpt: str | None = None
    cover_image_url: str | None = None
    status: BlogPostStatus
    locale: str = "fa"
    # i18n: posts sharing a group are translations of one another (None = not
    # translated). The storefront language switcher groups on this.
    translation_group: uuid.UUID | None = None
    published_at: datetime | None = None
    scheduled_for: datetime | None = None
    category_id: uuid.UUID | None = None
    category: BlogCategoryResponse | None = None
    tags: list[BlogTagResponse] = Field(
        default_factory=list,
        description="Tags attached to this post",
    )
    reading_time: int | None = Field(
        default=None,
        description="Estimated reading time in minutes (based on 200 wpm)",
    )
    view_count: int = Field(default=0, description="Total views")
    author_name: str | None = Field(default=None, description="Author full name")
    is_featured: bool = False
    visibility: PostVisibility = PostVisibility.PUBLIC
    allow_comments: bool = True
    post_format: PostFormat = PostFormat.STANDARD
    gallery_image_ids: list[str] | None = None
    comment_count: int = Field(default=0, description="Total approved comments")
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None


class BlogPostDetailResponse(BlogPostResponse):
    """Full detail view of a single blog post."""

    content: str
    # True when the post is password-protected and no (or a wrong) password
    # was supplied: metadata renders, ``content`` is withheld. The storefront
    # shows a password form instead of the body (WordPress parity).
    content_locked: bool = Field(
        default=False,
        description="Body withheld because the post is password-protected",
    )
    related_posts: list[BlogPostResponse] = Field(
        default_factory=list,
        description="List of related published posts",
    )
    seo: dict[str, Any] | None = Field(
        default=None,
        description="Associated SEO metadata",
    )


class BlogListResponse(BaseModel):
    """Paginated list of blog posts."""

    model_config = ConfigDict(from_attributes=True)

    items: list[BlogPostResponse]
    total: int = Field(ge=0, description="Total matching blog posts")
    page: int = Field(ge=1, description="Current page number")
    page_size: int = Field(ge=1, description="Items per page")
    total_pages: int = Field(ge=0, description="Total number of pages")
    has_next: bool = False
    has_prev: bool = False


# ============================================================================
# Revision Schemas
# ============================================================================


class BlogPostRevisionResponse(BaseModel):
    """Summary view of a single stored post revision."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    post_id: uuid.UUID
    revision_number: int
    title: str
    slug: str
    status: str
    created_by: uuid.UUID | None = None
    created_at: datetime | None = None


class BlogPostRevisionDetailResponse(BlogPostRevisionResponse):
    """Full snapshot content for one revision."""

    content: str
    excerpt: str | None = None
    cover_image_url: str | None = None
    seo_title: str | None = None
    seo_description: str | None = None
    # The custom fields as of this revision, as a JSON object. The raw column is
    # a string so an unreadable snapshot can never break the response; it is
    # parsed here, and an unparseable value becomes an empty object rather than
    # a 500 on a route an editor is trying to open.
    meta: dict[str, str | None] = Field(default_factory=dict)


class RevisionDiffToken(BaseModel):
    """One word-level token of the inline diff for a changed field.

    ``equal``+``delete`` tokens joined with single spaces reconstruct the A
    text; ``equal``+``insert`` reconstructs B.
    """

    op: Literal["equal", "insert", "delete"]
    text: str


class RevisionFieldDiff(BaseModel):
    """Field-level change between two revisions."""

    field: str = Field(description="Stable field key (title, body, seo_title, …)")
    label: str = Field(description="Human-readable label")
    changed: bool
    a: str | None = Field(None, description="Value in revision A")
    b: str | None = Field(None, description="Value in revision B")
    inline_diff: list[RevisionDiffToken] | None = Field(
        None,
        description="Word-level tokens for long text fields (body); None otherwise",
    )


class RevisionSnapshotRef(BaseModel):
    """Identity of one compared revision."""

    id: uuid.UUID
    revision_number: int
    created_at: datetime | None = None
    created_by: uuid.UUID | None = None


class RevisionDiffResponse(BaseModel):
    """Field-level diff between two stored post revisions."""

    post_id: uuid.UUID
    rev_a: RevisionSnapshotRef
    rev_b: RevisionSnapshotRef
    fields: list[RevisionFieldDiff]
    changed: bool = Field(description="True when any compared field differs")


# ============================================================================
# Comment Schemas
# ============================================================================


class BlogCommentCreate(BaseModel):
    """Schema for creating a comment.

    Two addressing styles are accepted (WordPress parity — comments attach to
    posts and pages alike):

    - legacy: ``post_id`` (implies resource_type "blog_post")
    - generic: ``resource_type`` + ``resource_id`` for any commentable object
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    post_id: uuid.UUID | None = Field(
        None,
        description="Post UUID to comment on (legacy addressing; implies blog_post)",
    )
    resource_type: Literal["blog_post", "cms_page", "content_entry"] = Field(
        default="blog_post",
        description="Which CMS object type the comment attaches to. "
                    "'content_entry' is a custom post type entry, and is only "
                    "accepted when that type has supports_comments on.",
    )
    resource_id: uuid.UUID | None = Field(
        None,
        description="UUID of the target object (required when post_id is omitted)",
    )
    content: str = Field(..., min_length=1, max_length=5000, description="Comment text")
    parent_id: uuid.UUID | None = Field(None, description="Parent comment for threaded replies")
    # Guest fields (when not authenticated)
    author_name: str | None = Field(None, max_length=200)
    author_email: str | None = Field(None, max_length=255)
    author_url: str | None = Field(None, max_length=500)


class BlogCommentUpdate(BaseModel):
    """Schema for updating a comment.

    Beyond content and status this carries the author's own fields, which a
    moderator correcting a mistyped name or a spam address needs. They are all
    optional and only the ones actually sent are applied, so an edit that only
    fixes a typo in the body does not blank the email that was there.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    content: str | None = Field(None, min_length=1, max_length=5000)
    status: CommentStatus | None = None
    author_name: str | None = Field(None, max_length=200)
    author_email: str | None = Field(None, max_length=320)
    # Free text a moderator may type; validated as a URL shape by the client
    # and escaped on render, so this is not a way to inject markup.
    author_url: str | None = Field(None, max_length=500)
    author_date: datetime | None = None


class BlogNoteCreate(BaseModel):
    """A private team note on a post or page (wp_comments.comment_type='note')."""

    model_config = ConfigDict(str_strip_whitespace=True)

    resource_type: Literal["blog_post", "cms_page"] = "blog_post"
    resource_id: uuid.UUID
    content: str = Field(..., min_length=1, max_length=5000)
    parent_id: uuid.UUID | None = None


class BlogCommentResponse(BaseModel):
    """Public response schema for a comment.

    Deliberately omits ``author_email``: this schema is returned by the
    unauthenticated ``GET /blog/comments`` and ``GET /blog/posts/{id}/comments``
    routes, so exposing the field handed every anonymous visitor the address of
    every commenter who left one. ``status`` is likewise withheld — a public
    reader has no business knowing a comment is pending. Both live on
    ``BlogCommentAdminResponse``, which only the guarded admin routes return.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    # Legacy addressing: set for post comments, None for page comments.
    post_id: uuid.UUID | None = None
    # Polymorphic addressing: which object this comment belongs to.
    resource_type: str = "blog_post"
    resource_id: uuid.UUID | None = None
    author_id: uuid.UUID | None = None
    author_name: str | None = None
    # Publicly rendered as a mailto link, so it is not PII the way an email is.
    author_url: str | None = None
    # Uploaded avatar if the author has one, else their Gravatar. Unset for
    # guests who gave no email — the UI falls back to initials.
    author_avatar_url: str | None = None
    content: str
    parent_id: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime
    # Computed fields
    replies: list["BlogCommentResponse"] = Field(
        default_factory=list,
        description="Child comments (threaded replies)",
    )


class BlogCommentAdminResponse(BlogCommentResponse):
    """Comment schema for the moderation surface.

    Adds back the fields the public schema withholds, plus ``status`` so a
    moderator can filter on it, plus ``comment_type`` so the table can style a
    private note apart and filter to one kind. That last one is withheld from the
    public schema for the same reason as the email: a note's existence is itself
    private. Used only by routes behind ``blog:write`` or
    ``blog:moderate_comments``.
    """

    author_email: str | None = None
    # The address the comment came from. It is stored (see the privacy policy
    # and its retention setting) but was never returned, so a moderator
    # moderating spam had no way to see two comments from the same address —
    # the single most useful signal when deciding what is spam. Admin-gated for
    # the same reason `author_email` is.
    author_ip: str | None = None
    # The commenter's website. Already on the public schema (it is rendered as
    # a link), restated here so the moderation table can read it off the admin
    # type without narrowing to the public one.
    author_url: str | None = None
    status: CommentStatus
    comment_type: Literal["comment", "note"] = "comment"


class BlogCommentListResponse(BaseModel):
    """Paginated list of comments."""

    items: list[BlogCommentResponse]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    total_pages: int = Field(ge=0)
    has_next: bool = False
    has_prev: bool = False


class BlogCommentAdminListResponse(BlogCommentListResponse):
    """Pagination envelope for the moderation surface.

    Narrowing ``items`` is what actually changes the wire format: FastAPI
    validates the handler's return value against ``response_model``, so
    declaring the admin item schema on the route while leaving the envelope on
    the public one silently dropped ``author_email`` and ``status`` again —
    which is exactly what the moderation table renders.
    """

    items: list[BlogCommentAdminResponse]  # type: ignore[assignment]


# ============================================================================
# Post Meta (Custom Fields) Schemas
# ============================================================================


class BlogPostMetaCreate(BaseModel):
    """Schema for creating/updating a custom field."""

    model_config = ConfigDict(str_strip_whitespace=True)

    meta_key: str = Field(..., min_length=1, max_length=255, description="Meta key name")
    meta_value: str | None = Field(None, description="Meta value (text)")


class BlogPostMetaResponse(BaseModel):
    """Response schema for a custom field."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    post_id: uuid.UUID
    meta_key: str
    meta_value: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


# ============================================================================
# Author archive (WordPress parity: /author/<slug>)
# ============================================================================


class BlogAuthorResponse(BaseModel):
    """Public identity of a post author."""

    model_config = ConfigDict(from_attributes=True)

    slug: str = Field(..., description="Stable public slug; the archive URL is /author/<slug>")
    name: str = Field(..., description="Display name")
    bio: str | None = Field(None, description="Author biography, when the profile has one")
    avatar_url: str | None = None
    post_count: int = Field(default=0, ge=0)


class BlogAuthorArchiveResponse(BaseModel):
    """One author plus their published posts."""

    author: BlogAuthorResponse
    posts: BlogListResponse


# ── Category / tag editing (only create existed) ───────────────────────────


class BlogCategoryUpdate(BaseModel):
    """Rename a category or change its slug.

    Every field is optional so a caller can send only what changed. A changed
    slug is a public URL: the caller is expected to have created a redirect (or
    recorded a slug_history row) first, which is why this does not reject an
    in-use category the way a delete would.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    name: str | None = Field(None, min_length=1, max_length=200)
    slug: str | None = Field(None, max_length=220, min_length=1)
    description: str | None = Field(None, max_length=2000)
    # None means "move to top level", so the field is distinguished from
    # "not supplied" by model_fields_set rather than by its value.
    parent_id: uuid.UUID | None = None
    position: int | None = Field(None, ge=0)


class BlogTagUpdate(BaseModel):
    """Rename a tag, change its slug, or describe it.

    ``description`` was added with the column: a tag could be renamed and
    re-slugged and nothing else about it could be said, because the column did
    not exist.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    name: str | None = Field(None, min_length=1, max_length=200)
    slug: str | None = Field(None, max_length=220, min_length=1)
    # None clears the description, which is the same as never having set one.
    description: str | None = Field(None, max_length=2000)


class BlogCategoryDeleteResult(BaseModel):
    """What a category delete did to the posts that were in it.

    Deleting a category cannot simply fail when it has posts — the operator
    has no other way to remove a category they stopped using. Orphaning the
    posts is the WordPress behaviour, and the count is returned so the admin
    can say what happened.
    """

    deleted: bool
    orphaned_posts: int
