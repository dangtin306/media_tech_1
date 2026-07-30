#!/usr/bin/env bash
set -euo pipefail

mkdir -p /run/sshd
ssh-keygen -A >/dev/null 2>&1 || true

if [[ -n "${ROOT_PASSWORD:-}" ]]; then
  echo "root:${ROOT_PASSWORD}" | chpasswd
fi

if grep -q '^#\?PermitRootLogin' /etc/ssh/sshd_config; then
  sed -i 's/^#\?PermitRootLogin.*/PermitRootLogin yes/' /etc/ssh/sshd_config
else
  printf '\nPermitRootLogin yes\n' >> /etc/ssh/sshd_config
fi

if grep -q '^#\?PasswordAuthentication' /etc/ssh/sshd_config; then
  sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication yes/' /etc/ssh/sshd_config
else
  printf 'PasswordAuthentication yes\n' >> /etc/ssh/sshd_config
fi

exec "$@"
