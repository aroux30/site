#!/usr/bin/env python3
"""Upload tarball to server, extract, sync to container, and run pytest."""

import os
import sys
import paramiko

def main():
    host = os.environ.get("DEPLOY_HOST", "91.107.144.136")
    username = os.environ.get("DEPLOY_USER", "root")
    password = os.environ.get("DEPLOY_PASSWORD")
    if not password and os.path.exists(".env"):
        with open(".env", "r") as f:
            for line in f:
                if line.startswith("DEPLOY_SSH_PASSWORD="):
                    password = line.split("=", 1)[1].strip().strip('"').strip("'")
                elif line.startswith("POSTGRES_PASSWORD=") and not password:
                    # fallback to server root password if configured
                    pass
    if not password:
        password = os.environ.get("SSH_PASSWORD")
    if not password:
        raise ValueError("Deployment password not found. Please set SSH_PASSWORD or DEPLOY_SSH_PASSWORD.")

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"Connecting to {host}...", flush=True)
    client.connect(host, username=username, password=password, timeout=30)
    print("Connected.", flush=True)

    sftp = client.open_sftp()
    print("Uploading backend_sync.tar.gz...", flush=True)
    sftp.put("backend_sync.tar.gz", "/root/site/backend_sync.tar.gz")
    sftp.close()
    print("Uploaded tarball.", flush=True)

    commands = [
        ("Extracting tarball on server...", "cd /root/site && tar -xzf backend_sync.tar.gz"),
        ("Copying into ecommerce-backend container...", "docker cp /root/site/backend/app ecommerce-backend:/app/ && docker cp /root/site/backend/tests ecommerce-backend:/app/"),
        ("Running full test suite in ecommerce-backend...", "docker exec -e ENVIRONMENT=development ecommerce-backend pytest tests/ -v -o cache_dir=/tmp/.pytest_cache")
    ]

    for title, cmd in commands:
        print(f"\n>>> {title}", flush=True)
        stdin, stdout, stderr = client.exec_command(cmd, timeout=300)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        if out:
            print(out, flush=True)
        if err:
            print("STDERR:", err, flush=True)

    client.close()

if __name__ == "__main__":
    main()
