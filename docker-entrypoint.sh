#!/bin/sh
set -eu

Xvfb :99 -screen 0 1280x1024x24 -nolisten tcp &
xvfb_pid=$!
export DISPLAY=:99

until [ -S /tmp/.X11-unix/X99 ]; do
    if ! kill -0 "$xvfb_pid" 2>/dev/null; then
        echo "Xvfb failed to start" >&2
        exit 1
    fi
    sleep 0.1
done

exec "$@"
