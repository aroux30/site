#!/usr/bin/env python3
"""SSH deployment script for the e-commerce platform."""

import paramiko
import sys
import time


def ssh_exec(client, command, timeout=300):
    """Execute command on remote server and return output."""
    print(f"\n>>> {command}")
    stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
    exit_code = stdout.channel.recv_exit_status()
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    if out.strip():
        print(out.strip()[-2000:])  # Last 2000 chars
    if err.strip():
        print(f"STDERR: {err.strip()[-1000:]}")
    print(f"Exit code: {exit_code}")
    return exit_code, out, err


def main():
    import os
    host = os.environ.get("DEPLOY_HOST", "91.107.144.136")
    username = os.environ.get("DEPLOY_USER", "root")
    password = os.environ.get("DEPLOY_PASSWORD") or os.environ.get("SSH_PASSWORD")
    if not password and os.path.exists(".env"):
        with open(".env", "r") as f:
            for line in f:
                if line.startswith("DEPLOY_SSH_PASSWORD="):
                    password = line.split("=", 1)[1].strip().strip('"').strip("'")
    if not password:
        raise ValueError("Deployment password not found. Please set SSH_PASSWORD or DEPLOY_SSH_PASSWORD.")
    project_dir = "/root/site"

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    print(f"Connecting to {host}...")
    client.connect(host, username=username, password=password, timeout=30)
    print("Connected!")

    # Step 1: Check server
    print("\n=== Step 1: Server Info ===")
    ssh_exec(client, "uname -a && free -h | head -3 && df -h / | tail -1")

    # Step 2: Install Docker if not present
    print("\n=== Step 2: Install Docker ===")
    code, out, _ = ssh_exec(client, "docker --version 2>/dev/null")
    if code != 0:
        print("Installing Docker...")
        ssh_exec(client, "apt-get update -y && apt-get install -y ca-certificates curl gnupg", timeout=120)
        ssh_exec(client, "install -m 0755 -d /etc/apt/keyrings", timeout=30)
        ssh_exec(client, "curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg --yes", timeout=60)
        ssh_exec(client, "chmod a+r /etc/apt/keyrings/docker.gpg", timeout=10)
        ssh_exec(client, 'echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null', timeout=30)
        ssh_exec(client, "apt-get update -y", timeout=120)
        ssh_exec(client, "apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin", timeout=300)
        ssh_exec(client, "systemctl enable docker && systemctl start docker", timeout=30)
    else:
        print(f"Docker already installed: {out.strip()}")

    ssh_exec(client, "docker compose version")

    # Step 3: Install git if not present
    print("\n=== Step 3: Install Git ===")
    code, _, _ = ssh_exec(client, "git --version")
    if code != 0:
        ssh_exec(client, "apt-get install -y git", timeout=120)

    # Step 4: Clone or update repository
    print("\n=== Step 4: Clone/Update Repository ===")
    code, _, _ = ssh_exec(client, f"test -d {project_dir}/.git && echo 'exists'")
    if code == 0:
        print("Repository exists, pulling latest...")
        ssh_exec(client, f"cd {project_dir} && git pull origin main", timeout=120)
    else:
        print("Cloning repository...")
        ssh_exec(client, f"rm -rf {project_dir}", timeout=30)
        ssh_exec(client, f"git clone https://github.com/aroux30/site.git {project_dir}", timeout=120)

    # Step 5: Create .env file
    print("\n=== Step 5: Create .env ===")
    env_content = """# ============================================
# E-Commerce Platform - Production Environment
# ============================================

# App
APP_NAME=iranian-ecommerce
ENVIRONMENT=production
DEBUG=false

# PostgreSQL
POSTGRES_DB=ecommerce
POSTGRES_USER=ecommerce
POSTGRES_PASSWORD=Xk9m2Pq7vR4nL8wB
DATABASE_URL=postgresql+asyncpg://ecommerce:Xk9m2Pq7vR4nL8wB@postgres:5432/ecommerce

# Redis
REDIS_PASSWORD=Yt5hN3jK8mW2vQ9p
REDIS_URL=redis://:Yt5hN3jK8mW2vQ9p@redis:6379/0
CELERY_BROKER_URL=redis://:Yt5hN3jK8mW2vQ9p@redis:6379/1
CELERY_RESULT_BACKEND=redis://:Yt5hN3jK8mW2vQ9p@redis:6379/2

# Elasticsearch
ELASTICSEARCH_URL=http://elasticsearch:9200

# JWT
JWT_SECRET_KEY=Zm4kR8pN2wX7vQ3hL9tB5jY6mC1dF8gA
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# MinIO
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=Hp7mK2nR9wL4vX8q
MINIO_BUCKET=ecommerce
MINIO_USE_SSL=false

# CORS
CORS_ORIGINS=["http://localhost","http://91.107.144.136"]

# Sentry (optional)
SENTRY_DSN=

# Frontend
NEXT_PUBLIC_API_URL=http://91.107.144.136/api/v1
NEXT_PUBLIC_SITE_URL=http://91.107.144.136

# Grafana
GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=Wn3kP8mR5vL7xQ2h

# SMS Provider
SMS_PROVIDER=mock
KAVENEGAR_API_KEY=

# Payment
PAYMENT_PROVIDER=mock
ZARINPAL_MERCHANT_ID=
"""
    # Write env file
    ssh_exec(client, f"cat > {project_dir}/.env << 'ENVEOF'\n{env_content}\nENVEOF", timeout=30)
    ssh_exec(client, f"chmod 600 {project_dir}/.env", timeout=10)

    # Step 6: Fix line endings for shell scripts
    print("\n=== Step 6: Fix line endings ===")
    ssh_exec(client, f"cd {project_dir} && find . -name '*.sh' -exec sed -i 's/\\r$//' {{}} \\; && chmod +x scripts/*.sh backend/scripts/*.sh", timeout=30)

    # Step 7: Set vm.max_map_count for Elasticsearch
    print("\n=== Step 7: System tuning ===")
    ssh_exec(client, "sysctl -w vm.max_map_count=262144 && echo 'vm.max_map_count=262144' >> /etc/sysctl.conf 2>/dev/null", timeout=10)

    # Step 8: Build and start Docker services
    print("\n=== Step 8: Build and Start Services ===")
    # Start infrastructure services first
    print("Starting infrastructure services...")
    ssh_exec(client, f"cd {project_dir} && docker compose up -d postgres redis elasticsearch minio", timeout=300)

    print("Waiting for infrastructure to be ready...")
    time.sleep(15)

    # Check infrastructure health
    ssh_exec(client, f"cd {project_dir} && docker compose ps", timeout=30)

    # Build and start app services
    print("Building and starting application services...")
    ssh_exec(client, f"cd {project_dir} && docker compose up -d --build", timeout=600)

    print("Waiting for services to start...")
    time.sleep(20)

    # Step 9: Check status
    print("\n=== Step 9: Check Status ===")
    ssh_exec(client, f"cd {project_dir} && docker compose ps", timeout=30)
    ssh_exec(client, f"cd {project_dir} && docker compose logs --tail=30 backend 2>&1 | tail -30", timeout=30)
    ssh_exec(client, f"cd {project_dir} && docker compose logs --tail=30 frontend 2>&1 | tail -30", timeout=30)
    ssh_exec(client, f"cd {project_dir} && docker compose logs --tail=20 nginx 2>&1 | tail -20", timeout=30)

    # Step 10: Health check
    print("\n=== Step 10: Health Check ===")
    for i in range(5):
        code, out, _ = ssh_exec(client, "curl -s -o /dev/null -w '%{http_code}' http://localhost/healthz 2>/dev/null || echo 'failed'", timeout=15)
        if "200" in out:
            print("Health check PASSED!")
            break
        print(f"Attempt {i+1}/5 - waiting...")
        time.sleep(10)

    print("\n=== Deployment Complete ===")
    print(f"Application URL: http://{host}")
    print(f"API URL: http://{host}/api/v1")
    print(f"API Docs: http://{host}/docs")
    print(f"MinIO Console: http://{host}:9001")
    print(f"Grafana: http://{host}:3001")

    client.close()


if __name__ == "__main__":
    main()
