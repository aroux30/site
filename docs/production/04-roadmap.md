# 04 — POST-LAUNCH ROADMAP & EVOLUTION PLAN
## Enterprise-Grade Iranian Headless E-Commerce Platform
**Date:** 2026-09-10  

---

## 1. Phase 19: Commercial Activation & Pre-Flight (Weeks 1–2)

- [ ] **DNS & TLS Transition:** Point primary domain (e.g., `shop.domain.ir`) to `91.107.144.136`, configure Let's Encrypt certificate auto-renewal via Certbot Nginx plugin.
- [ ] **Payment Gateway Verification:** Transition Zarinpal and IDPay from sandbox credentials to production Merchant IDs.
- [ ] **SMS Gateway Connectivity:** Activate Kavenegar / Ghasedak SMS API keys for live Iranian mobile OTP delivery.
- [ ] **Production Secrets Vaulting:** Generate cryptographic random strings for `JWT_SECRET_KEY` and rotate PostgreSQL passwords.

---

## 2. Phase 20: Scale & Infrastructure Enhancements (Weeks 3–6)

- [ ] **PgBouncer Connection Pooling:** Deploy dedicated PgBouncer pooler between FastAPI and PostgreSQL to support 5,000+ concurrent database connections.
- [ ] **PostgreSQL Read Replicas:** Configure asynchronous streaming replication for catalog and search read queries.
- [ ] **Automated Daily Backups:** Configure `pg_dump` cron script with compression, AES-256 encryption, and offsite upload to secondary MinIO/S3 bucket with automated restore test in CI.
- [ ] **CDN Edge Caching:** Enable Cloudflare / ArvanCloud CDN caching for static assets (`/_next/static/`, `/uploads/`).

---

## 3. Phase 21: Advanced AI & Merchandising (Weeks 7–12)

- [ ] **Semantic Natural Language Search:** Integrate embedding-based vector search in Elasticsearch for conversational queries (e.g., "گوشی تا ۲۰ میلیون با دوربین خوب").
- [ ] **Automated AI Product Description & SEO Meta Generation:** Background worker generating Iranian Persian descriptions from specs using LLM APIs.
- [ ] **Real-Time Carrier Integration:** Direct API integration with Tipax and SnappBox for automatic courier booking and live GPS tracking links.
