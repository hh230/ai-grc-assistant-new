#!/usr/bin/env bash
# Install the AI Organization as a permanent macOS LaunchAgent (per-user, starts at login,
# runs 24/7, auto-restarts on crash). It reuses the FROZEN Core + the existing observability and
# Dashboard: it writes the SAME journal the Dashboard already reads. It does NOT stand up a second
# Dashboard or a second Mission Engine implementation — it is a second worker process, exactly like
# the engineering-squad monitor already is.
#
# Idempotent: safe to re-run (it re-writes the plist and reloads the service).
set -euo pipefail

LABEL="com.rasheed.devteam-organization"
REPO="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel)"
PKG="$REPO/devteam/packages/devteam-organization"
PY="$PKG/.venv/bin/python"

# Org stdout/stderr live in their OWN dir so they never collide with the squad monitor's log (which
# the Dashboard parses for the squad's metrics). The JOURNAL is deliberately the SHARED file the
# Dashboard reads, so the organization shows up in the existing Dashboard with no change to it.
LOG_DIR="$HOME/Library/Logs/devteam-organization"
JOURNAL="$HOME/Library/Logs/devteam-monitor/runtime.jsonl"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
UID_NUM="$(id -u)"

# Tuning: supervise EVERY poll (continuous, read-only), record an observable heartbeat mission every
# 5th poll (bounded journal growth for a 24/7 service).
POLL_SECONDS="60"
HEARTBEAT_EVERY="5"
STALL_AFTER_S="900"

echo "repo    : $REPO"
echo "python  : $PY"
echo "journal : $JOURNAL  (the Dashboard's file — shared, not duplicated)"
echo "logs    : $LOG_DIR"
echo "plist   : $PLIST"

# The LaunchAgent runs the package venv's python directly (like the squad), so the venv must exist.
if [ ! -x "$PY" ]; then
  echo "venv missing — running 'uv sync' for the package…"
  ( cd "$PKG" && uv sync )
fi
"$PY" -c "import devteam_organization" || { echo "FATAL: package not importable in venv"; exit 1; }

mkdir -p "$LOG_DIR" "$(dirname "$JOURNAL")" "$HOME/Library/LaunchAgents"

cat > "$PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$LABEL</string>

    <key>ProgramArguments</key>
    <array>
        <string>$PY</string>
        <string>-m</string>
        <string>devteam_organization</string>
        <string>--repo-root</string>
        <string>$REPO</string>
        <string>--journal</string>
        <string>$JOURNAL</string>
        <string>--poll-seconds</string>
        <string>$POLL_SECONDS</string>
        <string>--heartbeat-every</string>
        <string>$HEARTBEAT_EVERY</string>
        <string>--stall-after-s</string>
        <string>$STALL_AFTER_S</string>
    </array>

    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>$HOME/.local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    </dict>

    <key>WorkingDirectory</key>
    <string>$REPO</string>

    <!-- Start automatically at login. -->
    <key>RunAtLoad</key>
    <true/>

    <!-- Run 24/7 and auto-recover: launchd restarts the process whenever it exits. -->
    <key>KeepAlive</key>
    <true/>

    <!-- Don't hot-loop if it crashes on start. -->
    <key>ThrottleInterval</key>
    <integer>30</integer>

    <key>ProcessType</key>
    <string>Background</string>

    <key>StandardOutPath</key>
    <string>$LOG_DIR/organization.out.log</string>

    <key>StandardErrorPath</key>
    <string>$LOG_DIR/organization.err.log</string>
</dict>
</plist>
PLIST

echo "wrote plist. (re)loading service…"
launchctl bootout "gui/$UID_NUM/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$UID_NUM" "$PLIST"
launchctl kickstart -k "gui/$UID_NUM/$LABEL"

echo "installed + started: $LABEL"
launchctl print "gui/$UID_NUM/$LABEL" 2>/dev/null | grep -E "state|pid|program|last exit" | head -8 || launchctl list | grep "$LABEL"
