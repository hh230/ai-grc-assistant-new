#!/usr/bin/env bash
# Stop and remove the AI Organization LaunchAgent. Leaves the logs and the shared journal in place.
set -euo pipefail
LABEL="com.rasheed.devteam-organization"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
UID_NUM="$(id -u)"

launchctl bootout "gui/$UID_NUM/$LABEL" 2>/dev/null || true
rm -f "$PLIST"
echo "removed $LABEL (plist deleted, logs + journal kept)"
launchctl list | grep "$LABEL" || echo "confirmed: service no longer loaded"
