#!/bin/sh
# Runs at container start (nginx's /docker-entrypoint.d). When BASIC_AUTH_USER and BASIC_AUTH_PASSWORD
# are both set, the whole site asks for them; Coolify sets them for staging only. Otherwise no auth.
set -eu
if [ -n "${BASIC_AUTH_USER:-}" ] && [ -n "${BASIC_AUTH_PASSWORD:-}" ]; then
  printf '%s:{PLAIN}%s\n' "$BASIC_AUTH_USER" "$BASIC_AUTH_PASSWORD" > /etc/nginx/htpasswd
  printf 'auth_basic "Ctrl Academy staging";\nauth_basic_user_file /etc/nginx/htpasswd;\n' > /etc/nginx/auth.conf
  echo "basic-auth: on for user $BASIC_AUTH_USER"
else
  : > /etc/nginx/auth.conf
  echo "basic-auth: off"
fi
