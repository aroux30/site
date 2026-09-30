# Runbook: Backup and Restore

How backups are taken, where they go, how they are protected, and the exact
procedure to restore — including the **restore verification** that turns "we
have backup files" into "we proved a backup restores".

Scripts:

| Script | Purpose |
|---|---|
| `scripts/backup.sh` | Snapshot PostgreSQL + uploaded media (+ Elasticsearch if reachable) |
| `scripts/restore.sh` | Restore an artifact (checksum-verified, destructive-gated) |
| `scripts/verify_backup.sh` | Non-destructive proof: restore into a throwaway DB, count, drop |
| `scripts/cron.d/ecommerce-backup` | cron fragment (nightly backups + weekly verify) |
| `scripts/systemd/` | Equivalent systemd `.service`/`.timer` units |

---

## 1. What gets backed up

| Service | Method | Source of truth? |
|---|---|---|
| **PostgreSQL** | `pg_dump` inside the `postgres` container → `app_db_<YYYYmmdd_HHMMSS>.sql.gz` | **Yes** |
| **Uploaded media** | `tar czf` of `/app/uploads` from the `backend` container → `uploads_<ts>.tar.gz` | **Yes** |
| **MinIO** | `mc mirror` of bucket `ecommerce-media` (default) → `minio_<bucket>_<ts>.tar.gz` | No — see note |
| **Elasticsearch** | `_snapshot` API → `es_snapshots_<ts>.tar.gz`, **only if reachable** | No — derived index |

**Media note.** Uploaded files are written to `UPLOAD_DIR` on the
`uploads_data` volume; no code path in the application uses an S3 client
(`media_service` has none). The MinIO bucket is therefore empty, and this
runbook previously listed a MinIO mirror as *the* media backup — which meant
product images and bank receipts were not covered by any artifact. The
`uploads` archive above is the one that matters. MinIO is still snapshotted so
that a future S3 migration inherits a working backup path; if that path is
taken, this row becomes a real source again and the note should move with it.

Elasticsearch is a derived search index that can be rebuilt from PostgreSQL, so
its snapshot is best-effort: if ES is down, the repo `path.repo` is not
configured, or the API is unreachable, the backup **skips it with a clear
message** and still succeeds. PostgreSQL and uploaded media are the data that
would be lost, and both are mandatory (the media archive can be skipped only
explicitly with `--no-media`, which is discouraged).

Every artifact gets a `.sha256` sidecar. Each run writes
`backups/manifest_<timestamp>.txt` and appends one line to `backups/backup.log`
(timestamp, status, duration, db, artifact count, exit code).

---

## 2. Frequency

| Level | Frequency | Retention |
|---|---|---|
| Automated (cron/systemd) | Twice daily, 03:15 and 15:15 Tehran (IRST, UTC+03:30) | 7 by default (`--retain`) |
| Pre-deployment | Manually, before every deploy | — |
| Pre-maintenance | Manually, before reboot / migrations | — |
| Restore verification | Weekly — Sunday 05:00 Tehran | — |

The two daily slots give a "last 7 backups" window of ~3.5 days of coverage at
the default `--retain 7`; raise `--retain` (e.g. `-r 30`) if you need longer
on-disk history, and ship copies off-host for anything beyond that (see §4).

---

## 3. Encryption

Encryption is **conditional, not automatic**:

- It is applied only when a key is configured and encryption is requested.
- Turn it on per-run: `bash scripts/backup.sh --encrypt`
- Or persistently: set `BACKUP_REQUIRE_ENCRYPTION=1` in `.env`.
- The key lives in `BACKUP_ENCRYPTION_KEY` (`openssl` AES-256-CBC, PBKDF2, salted).

If encryption is requested but `BACKUP_ENCRYPTION_KEY` is unset, the script
**fails loudly** and writes nothing — it never writes a plaintext file and
reports it as encrypted. When no key is configured at all, artifacts are
written **unencrypted** but always checksummed. `restore.sh` decrypts `.enc`
artifacts transparently and requires the same key.

> Backup artifacts can contain PII (customer records, bank-card references) and
> secrets. Keep them off any host you would not trust with the database, and
> enable encryption in production.

---

## 4. Backup destination

Default: `backups/` at the repo root (`-o/--output` overrides it).

- `backups/` is listed in `.gitignore` and must never be committed.
- The MinIO portion needs the destination bind-mounted into Docker (uses
  `cygpath` on Windows / Docker Desktop); the PostgreSQL dump is written purely
  by the host shell piping out of the container, so it has no mount requirement.
- **Off-host copies are not automated.** For real durability, replicate
  `backups/` to separate storage (another host, object storage, off-site disk).
  A backup on the same disk as the database is not disaster recovery.

---

## 5. Restore procedure

### 5.1 Verify first (non-destructive) — always do this

```bash
cd /opt/app
bash scripts/verify_backup.sh                       # newest backup
bash scripts/verify_backup.sh -f backups/app_db_20260909_120000.sql.gz
```

This restores the dump into a throwaway database (`restore_verify_<timestamp>`),
prints row counts for `users, orders, payments, wallets, wallet_transactions,
products`, and **drops the throwaway database**. The live database is untouched.
Exit code 0 means the backup is genuinely restorable.

### 5.2 Restore for real (destructive)

```bash
cd /opt/app

# Confirm the artifact — checksum is verified automatically before any restore.
bash scripts/restore.sh -f backups/app_db_<timestamp>.sql.gz      # prompts "yes"
bash scripts/restore.sh -f backups/app_db_<timestamp>.sql.gz -y   # no prompt

# If the target DB already holds data, the script refuses unless you insist:
bash scripts/restore.sh -f backups/app_db_<timestamp>.sql.gz -y --force

# Include uploaded media (archive from backup.sh):
bash scripts/restore.sh -f backups/app_db_<timestamp>.sql.gz -y \
  -u backups/uploads_<timestamp>.tar.gz
```

The script will:

1. Verify the sha256 checksum and **abort on mismatch** (or if no `.sha256` is present).
2. Decrypt transparently if the artifact is `.enc`.
3. Refuse to restore into a database containing live data unless `--force` is given.
4. Drop and recreate the target DB, load the dump (`psql`, or `pg_restore` for
   custom-format dumps), optionally mirror MinIO back, then print key-table counts.

### 5.3 After restoring

- Run migrations if the dump predates the current schema:
  `docker compose exec backend alembic upgrade head`
- Check the app: `curl -s http://localhost:8000/api/health/ && docker compose ps`
- If Elasticsearch was restored or is stale, reindex from PostgreSQL (ES is
  derived) rather than relying on its snapshot.

---

## 6. RPO / RTO targets

| Metric | Target | Notes |
|---|---|---|
| **RPO** (max data loss) | ≤ 12 hours | Two automated runs/day. Tighten by increasing frequency or enabling PostgreSQL WAL archiving (continuous). |
| **RTO** (time to restore) | ≤ 2 hours | Depends on dump size and disk speed; verify against a real artifact, not a guess. |

These are **targets, not measured figures for this environment** — see §7.

---

## 7. Last successful restore verification

> **Status: NOT YET VERIFIED in this environment.**
>
> Docker is not installed on the machine where these scripts were authored, so
> the end-to-end backup/restore path could **not** be executed here. What *was*
> verified: `bash -n` on both scripts, `--help` output, argument parsing, the
> checksum-mismatch and missing-checksum refusals, the "encryption required but
> no key" hard failure, and decrypt-with-wrong-key failure. The Docker-driving
> paths (pg_dump, pg_restore/psql, mc mirror, ES snapshot) are implemented but
> **untested on this host**. No restore has been performed and none is claimed.

Fill this in the first time you run `verify_backup.sh` on the production host,
and update it weekly (a template row is shown filled as an example format):

| Date (Tehran) | Artifact verified | Row counts (users/orders/payments/wallets/wallet_transactions/products) | Verified by | Result |
|---|---|---|---|---|
| _example: 2026-09-20 05:00_ | _app_db_20260920_031500.sql.gz_ | _1 / 1 / 1 / 1 / 4 / 1_ | _ops_ | _PASS_ |
| | | | | |

Record the exact command used and paste the row-count table it printed. If a
run fails, record the failure and its error — a failed verification is the most
important line in this table.

To produce a row:

```bash
cd /root/site && bash scripts/verify_backup.sh
```

---

## 8. Scheduling

### Option A — cron

```bash
sudo cp scripts/cron.d/ecommerce-backup /etc/cron.d/ecommerce-backup
sudo chown root:root /etc/cron.d/ecommerce-backup
sudo chmod 0644 /etc/cron.d/ecommerce-backup
```

`cron.d` files must be root-owned, not group/other-writable, and end with a
newline, or cron silently ignores them. Logs go to
`/var/log/ecommerce-backup.cron.log`. Confirm the server timezone
(`timedatectl`) matches the Tehran assumption in the comments.

### Option B — systemd timers

```bash
sudo cp scripts/systemd/ecommerce-backup.service /etc/systemd/system/
sudo cp scripts/systemd/ecommerce-backup.timer   /etc/systemd/system/
sudo cp scripts/systemd/ecommerce-verify.service /etc/systemd/system/
sudo cp scripts/systemd/ecommerce-verify.timer   /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now ecommerce-backup.timer ecommerce-verify.timer
systemctl list-timers 'ecommerce-*'
```

Adjust `WorkingDirectory`/`ExecStart` in the units if the repo is not at
`/root/site`. Logs: `journalctl -u ecommerce-backup.service`.

---

## 9. Failure handling

`backup.sh` exits non-zero on **any** failure, including: Docker unavailable,
`postgres`/`backend`/`minio` not running, an empty `pg_dump`, an empty uploads
archive, a failed MinIO mirror, or
encryption requested without a key. Wire this into alerting (cron `MAILTO`,
systemd `OnFailure=`, or your monitoring stack) so a silently failing backup
does not go unnoticed. A backup you only discover is broken during a restore is
not a backup.