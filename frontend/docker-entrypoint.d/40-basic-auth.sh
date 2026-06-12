#!/bin/sh
# Runs automatically before nginx starts (nginx image executes /docker-entrypoint.d/*.sh).
# APP_PASSWORD set   -> generate /etc/nginx/.htpasswd and require a login for everything.
# APP_PASSWORD empty -> leave the server open (dev parity on localhost).
set -e

AUTH_SNIPPET=/etc/nginx/snippets/auth.conf

if [ -n "${APP_PASSWORD}" ]; then
    htpasswd -bc /etc/nginx/.htpasswd "${APP_USER:-onestatus}" "${APP_PASSWORD}" >/dev/null 2>&1
    cat > "$AUTH_SNIPPET" <<'CONF'
auth_basic "OneStatus";
auth_basic_user_file /etc/nginx/.htpasswd;
CONF
    echo "40-basic-auth: login required (user ${APP_USER:-onestatus})"
else
    : > "$AUTH_SNIPPET"
    echo "40-basic-auth: APP_PASSWORD not set, server is open"
fi
