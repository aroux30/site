# ADR-010: S3-Compatible Object Storage with MinIO for Development

**Date:** 2026-09-09

**Status:** Accepted

## Context

The platform needs to store and serve binary assets: product images, category banners, user avatars, uploaded documents, and generated reports. These files vary in size, require efficient serving (ideally via CDN), and must be durable and available.

Storing files on the application server's local filesystem creates deployment complications (sticky sessions, shared volumes), limits horizontal scaling, and provides no built-in redundancy.

The Iranian market has limited access to major cloud providers (AWS, GCP, Azure) due to sanctions. However, several Iranian cloud providers offer S3-compatible object storage APIs (e.g., ArvanCloud, IranServer). Designing around the S3 API ensures portability across providers.

## Decision

We will use **S3-compatible object storage** for all file storage, with **MinIO** as the local development and testing backend.

### Design

#### Application Interface

- All file operations use the `boto3` S3 client library through a `StorageService` abstraction.
- The abstraction provides methods for upload, download, delete, and pre-signed URL generation.
- Bucket names and endpoints are configurable via environment variables, making provider switching a configuration change.

#### Bucket Organization

| Bucket | Purpose | Access |
|--------|---------|--------|
| `products` | Product images and thumbnails | Public read |
| `avatars` | User profile images | Public read |
| `documents` | Invoices, reports, exports | Private (pre-signed URLs) |
| `temp` | Upload staging, processing intermediaries | Private, auto-expiring |

#### Development Environment

- MinIO runs as a Docker container in the development compose stack, providing a fully S3-compatible API locally.
- Developers do not need cloud credentials or internet access for file storage operations during development.
- Test fixtures use MinIO with ephemeral buckets that are created and destroyed per test run.

#### Production Environment

- An S3-compatible service from an accessible cloud provider serves as the production storage backend.
- A CDN is placed in front of public buckets for edge caching and optimized delivery.

## Consequences

### Positive

- S3 API compatibility ensures portability across storage providers without code changes.
- MinIO provides a production-parity local development experience for file storage.
- Object storage scales independently of the application; storage capacity is virtually unlimited.
- Pre-signed URLs enable secure, time-limited access to private files without proxying through the application.
- CDN integration for public assets reduces application server load and improves global delivery performance.

### Negative

- S3 is eventually consistent for certain operations (e.g., overwrite PUT followed by immediate GET may return stale data on some providers), though most modern implementations provide read-after-write consistency.
- MinIO in development and a different provider in production may have subtle behavioral differences in edge cases (multipart upload limits, metadata handling).
- Application must handle upload failures, retries, and cleanup of orphaned files.

### Mitigations

- We use unique file keys (UUID-based) for all uploads, avoiding overwrite consistency issues entirely.
- Integration tests run against MinIO to catch S3 API usage errors early.
- We implement a periodic cleanup job that identifies and removes orphaned files (uploaded but not referenced by any database record).
- The `StorageService` abstraction includes retry logic with exponential backoff for transient upload/download failures.
