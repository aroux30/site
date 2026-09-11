#!/usr/bin/env python3
"""Upload tarball to server, extract, sync to container, and run pytest."""

import os
import sys
import paramiko

def main():
    host = os.environ.get("DEPLOY_HOST")
    username = os.environ.get("DEPLOY_USER")
    if not host or not username:
        raise ValueError(
            "DEPLOY_HOST and DEPLOY_USER must be set "
            "(no defaults are provided for security)."
        )
    password = os.environ.get("DEPLOY_PASSWORD") or os.environ.get("SSH_PASSWORD")
    key_path = os.environ.get("DEPLOY_SSH_KEY")
    if not password and not key_path:
        raise ValueError(
            "Set DEPLOY_SSH_KEY (recommended) or DEPLOY_PASSWORD for auth."
        )

    client = paramiko.SSHClient()
    host_key_b64 = os.environ.get("DEPLOY_SSH_HOST_KEY")
    if host_key_b64:
        import base64

        import paramiko

        host_key = None
        for key_cls in (paramiko.Ed25519Key, paramiko.ECDSAKey, paramiko.RSAKey):
            try:
                host_key = key_cls(data=base64.b64decode(host_key_b64))
                break
            except Exception:
                continue
        if host_key is None:
            raise ValueError("DEPLOY_SSH_HOST_KEY could not be parsed.")
        client.set_missing_host_key_policy(paramiko.RejectPolicy())
    else:
        raise ValueError(
            "Host key verification is required: set DEPLOY_SSH_HOST_KEY to "
            "the base64 public host key (from `ssh-keyscan -t ed25519 <host>`)."
        )
    print(f"Connecting to {host}...", flush=True)
    client.connect(
        host, username=username, password=password, key_filename=key_path, pkey=host_key, timeout=30
    )
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
