#!/usr/bin/env bash
#
# Build this public repository tree from the private working copy.
#
#     bash tools/export.sh [source-dir]     # default source: /d/mqtt-py
#
# Source files are copied, then every deployment-specific value is replaced by a
# neutral placeholder: the broker host, its IP address, the broker password and
# the CA folder name. Nothing that identifies the author's own network ever
# reaches this tree, and the values to strip are READ OUT OF THE SOURCE at run
# time rather than stored here, so this script is safe to publish alongside the
# code it sanitizes.
#
# It only ever writes inside this repository. The working copy is never touched.

set -euo pipefail

SRC="${1:-/d/mqtt-py}"
DST="$(cd "$(dirname "$0")/.." && pwd)"

for f in cli/mqtt-cli.py web/mqtt-web.py; do
    if [ ! -f "$SRC/$f" ]; then
        echo "export.sh: cannot find $SRC/$f" >&2
        exit 1
    fi
done

# --- what has to be hidden, discovered from the source --------------------- #

# The hard-coded broker password, e.g. os.getenv("MQTT_PASS", "hunter2").
SECRET_PASS="$(grep -ho 'os\.getenv("MQTT_PASS", "[^"]*")' "$SRC/cli/mqtt-cli.py" \
    | head -n1 | sed 's/^.*, "//; s/")$//')"

# The hard-coded broker host.
SECRET_HOST="$(grep -ho 'os\.getenv("MQTT_HOST", "[^"]*")' "$SRC/cli/mqtt-cli.py" \
    | head -n1 | sed 's/^.*, "//; s/")$//')"

# The CA folder, whose name embeds the broker's address ("server-10.0.0.1").
SECRET_CA="$(grep -hoE 'os\.path\.join\("[^"]*", "certs", "ca\.crt"\)' "$SRC/cli/mqtt-cli.py" \
    | head -n1 | sed 's/^os\.path\.join("//; s/", "certs", "ca\.crt")$//')"
SECRET_IP="${SECRET_CA#server-}"

# Placeholders. 203.0.113.0/24 is RFC 5737 TEST-NET-3, reserved for examples.
NEW_HOST="broker.example.com"
NEW_IP="203.0.113.10"

echo "export.sh: hiding host '$SECRET_HOST', ip '$SECRET_IP', CA dir '$SECRET_CA',"
echo "           and a ${#SECRET_PASS}-character password"

# --- copy + sanitize ------------------------------------------------------- #

esc() { printf '%s' "$1" | sed 's/[][\\.*^$()+?{}|]/\\&/g'; }

sanitize() {
    local in="$1" out="$2"
    sed \
        -e "s|$(esc "$SECRET_CA")|broker-ca|g" \
        -e "s|$(esc "$SECRET_IP")|$NEW_IP|g" \
        -e "s|$(esc "$SECRET_HOST")|$NEW_HOST|g" \
        -e "s|$(esc "$SECRET_PASS")||g" \
        "$in" > "$out"
}

mkdir -p "$DST/cli" "$DST/web/examples"

sanitize "$SRC/cli/mqtt-cli.py" "$DST/cli/mqtt-cli.py"
sanitize "$SRC/web/mqtt-web.py" "$DST/web/mqtt-web.py"
chmod +x "$DST/cli/mqtt-cli.py" "$DST/web/mqtt-web.py"

# The eleven shortcut scripts are byte-identical by construction: device and
# action are read from the FILE NAME, so one script body serves every name.
for f in "$SRC"/cli/mqtt-*.py; do
    [ "$(basename "$f")" = "mqtt-cli.py" ] && continue    # handled above
    sanitize "$f" "$DST/cli/$(basename "$f")"
    chmod +x "$DST/cli/$(basename "$f")"
done

# The two PDF manuals: Chinese usage guides, no credentials inside.
cp "$SRC/cli/mqtt-CLI-使用说明.pdf"   "$DST/cli/" 2>/dev/null || true
cp "$SRC/web/mqtt-web-使用说明.pdf"   "$DST/web/" 2>/dev/null || true

# --- verify ---------------------------------------------------------------- #

fail=0
for needle in "$SECRET_PASS" "$SECRET_CA" "$SECRET_IP" "$SECRET_HOST"; do
    [ -z "$needle" ] && continue
    if grep -rqF "$needle" "$DST" --exclude-dir=.git 2>/dev/null; then
        echo "export.sh: FAIL -- '$needle' survived sanitizing" >&2
        fail=1
    fi
done

if [ "$fail" -ne 0 ]; then
    echo "export.sh: refused to produce a clean tree." >&2
    exit 1
fi

echo "export.sh: OK -- exported to $DST"
