# Security Documentation

## Overview

This document outlines the security measures, best practices, and configurations applied to this project.

## Infrastructure Security

### Firewall (UFW)

The server firewall is configured to allow only essential traffic:

| Port | Protocol | Purpose         |
|------|----------|-----------------|
| 22   | TCP      | SSH access      |
| 80   | TCP      | HTTP (redirect) |
| 443  | TCP      | HTTPS           |

All other inbound traffic is denied by default.

```bash
# Check firewall status
sudo ufw status verbose

# Add a rule
sudo ufw allow <port>/tcp comment "Description"

# Remove a rule
sudo ufw delete allow <port>/tcp
```

### Fail2Ban

Fail2Ban is configured to protect against brute-force SSH attacks:

- **Ban time:** 2 hours for SSH, 1 hour for other services
- **Max retries:** 3 for SSH, 5 for other services
- **Find time:** 10 minutes

```bash
# Check banned IPs
sudo fail2ban-client status sshd

# Unban an IP
sudo fail2ban-client set sshd unbanip <ip-address>
```

### SSH Hardening

Recommended SSH configuration (`/etc/ssh/sshd_config`):

```
PermitRootLogin no
PasswordAuthentication no
PubkeyAuthentication yes
MaxAuthTries 3
LoginGraceTime 30
AllowUsers deploy
ClientAliveInterval 300
ClientAliveCountMax 2
```

## Application Security

### Environment Variables

- All secrets are stored in `.env` files, never committed to version control.
- `.env` files have `600` permissions (owner read/write only).
- Production secrets are managed through GitHub Actions secrets.

### Secret Key Management

Generate strong secret keys:
```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

### Database Security

- PostgreSQL is not exposed to the public network (Docker internal network only).
- Database credentials use strong, unique passwords.
- Database backups are encrypted and checksummed.
- Connection to the database is restricted to application containers.

### HTTPS / TLS

- All HTTP traffic is redirected to HTTPS.
- TLS certificates are managed via Let's Encrypt / Certbot.
- Minimum TLS version: 1.2.
- Strong cipher suites configured in Nginx.

### CORS Configuration

Configure allowed origins in your application settings:
```python
CORS_ALLOWED_ORIGINS = [
    "https://your-domain.com",
    "https://www.your-domain.com",
]
CORS_ALLOW_CREDENTIALS = True
```

### Content Security Policy

Recommended CSP headers (configured in Nginx or application):
```
Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-ancestors 'none';
```

### Additional Security Headers

```
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Strict-Transport-Security: max-age=31536000; includeSubDomains; preload
Referrer-Policy: strict-origin-when-cross-origin
Permissions-Policy: camera=(), microphone=(), geolocation=()
```

## Docker Security

### Container Isolation

- Containers run with non-root users where possible.
- Read-only filesystems are used where applicable.
- Resource limits (CPU, memory) are set per container.
- No `--privileged` flag is used.

### Image Security

- Base images are pinned to specific versions (no `latest` tag).
- Images are regularly updated for security patches.
- Multi-stage builds minimize attack surface.

### Network Security

- Internal services communicate over Docker bridge networks.
- Only Nginx is exposed to the host network.
- Database and Redis ports are not published to the host.

## Dependency Management

### Backend (Python)

- Dependencies are pinned to exact versions in `requirements.txt`.
- Regular security audits with `pip-audit`:
  ```bash
  pip install pip-audit
  pip-audit -r requirements.txt
  ```

### Frontend (Node.js)

- Dependencies are locked via `package-lock.json`.
- Regular security audits with `npm audit`:
  ```bash
  npm audit
  npm audit fix
  ```

## Incident Response

### If a Security Breach Is Suspected

1. **Contain:** Isolate the affected system from the network if necessary.
2. **Assess:** Review logs to determine scope and impact.
3. **Rotate:** Change all credentials, API keys, and secrets immediately.
4. **Patch:** Apply fixes for the identified vulnerability.
5. **Notify:** Inform stakeholders and affected users as required.
6. **Review:** Conduct a post-incident review and update procedures.

### Log Locations

| Log                    | Location                          |
|------------------------|-----------------------------------|
| Application logs       | `docker compose logs backend`     |
| Nginx access logs      | `docker compose logs nginx`       |
| PostgreSQL logs        | `docker compose logs postgres`    |
| System auth logs       | `/var/log/auth.log`               |
| Fail2Ban logs          | `/var/log/fail2ban.log`           |
| Deployment logs        | `./logs/deploy_*.log`             |

## Security Checklist

Before going to production, verify:

- [ ] All default passwords have been changed
- [ ] `.env` file permissions are set to `600`
- [ ] SSH password authentication is disabled
- [ ] Firewall is enabled with minimal open ports
- [ ] HTTPS is configured with valid certificates
- [ ] Database is not publicly accessible
- [ ] Security headers are configured
- [ ] Dependencies are up to date
- [ ] Backup encryption is enabled
- [ ] Fail2Ban is active
- [ ] Application runs as non-root user
- [ ] Debug mode is disabled in production
- [ ] Logging and monitoring are configured
