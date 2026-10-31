#!/bin/sh
# Runs at container start (nginx's /docker-entrypoint.d). When STAGING_PASSWORD is set (Coolify sets it
# for staging only), every page and API call needs the ctrl_staging cookie, which the branded login
# page at /__gate/ sets from the password. Unset means the gate is off.
set -eu
http=/etc/nginx/gate-http.conf
server=/etc/nginx/gate-server.conf
if [ -n "${STAGING_PASSWORD:-}" ]; then
  token=$(printf '%s' "ctrl-academy-staging:$STAGING_PASSWORD" | sha256sum | cut -d' ' -f1)
  cat > "$http" <<CONF
# A regex key, because a 64-character literal overflows nginx's default map_hash_bucket_size.
map \$cookie_ctrl_staging \$ctrl_gate_ok {
    "~^$token\$" 1;
    default 0;
}
map "\$ctrl_gate_ok:\$uri" \$ctrl_gate_block {
    "~^1:" 0;
    "~^0:/(healthz|favicon\\.svg|favicon\\.ico)\$" 0;
    "~^0:/__gate/" 0;
    default 1;
}
CONF
  cat > "$server" <<'CONF'
if ($ctrl_gate_block) {
    return 401;
}
error_page 401 /__gate/index.html;
location ^~ /__gate/ {
    alias /usr/share/nginx/gate/;
    add_header Cache-Control "no-store" always;
}
CONF
  echo "staging-gate: on"
else
  : > "$http"
  : > "$server"
  echo "staging-gate: off"
fi
