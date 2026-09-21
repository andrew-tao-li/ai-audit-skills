#!/bin/bash
# 安装 launchd 任务
# 用法：./install_launchd.sh install | uninstall | status

LABEL="com.audit.skill.box"
PLIST_SRC="$(cd "$(dirname "$0")" && pwd)/com.audit.skill.box.plist"
PLIST_DST="$HOME/Library/LaunchAgents/${LABEL}.plist"

case "$1" in
    install)
        cp "$PLIST_SRC" "$PLIST_DST"
        launchctl load "$PLIST_DST"
        echo "Installed: $PLIST_DST"
        echo "Run 'launchctl list | grep audit' to verify"
        ;;
    uninstall)
        launchctl unload "$PLIST_DST" 2>/dev/null
        rm -f "$PLIST_DST"
        echo "Uninstalled: $LABEL"
        ;;
    status)
        launchctl list | grep audit || echo "Not loaded"
        ;;
    run-now)
        launchctl start "${LABEL}"
        echo "Triggered immediate run"
        ;;
    *)
        echo "Usage: $0 {install|uninstall|status|run-now}"
        exit 1
        ;;
esac
