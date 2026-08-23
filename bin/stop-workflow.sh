#!/usr/bin/env bash
set -u

TMP_ROOT="${VIDEOFUSION_TMP_ROOT:-/tmp/videofusion}"

stop_service() {
    local name="$1"
    local pid_file="$2"
    local pid=""

    if [ -f "$pid_file" ]; then
        pid=$(cat "$pid_file" 2>/dev/null || true)
    fi

    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
        echo "正在停止 $name，PID=$pid"
        kill -TERM "$pid" 2>/dev/null || true

        for i in $(seq 1 30); do
            kill -0 "$pid" 2>/dev/null || break
            sleep 1
        done

        if kill -0 "$pid" 2>/dev/null; then
            echo "$name 未及时退出，发送 KILL"
            kill -KILL "$pid" 2>/dev/null || true
        fi
    else
        echo "$name 未运行"
    fi

    rm -f "$pid_file"
}

stop_service \
"ComfyUI" \
"$TMP_ROOT/comfyui.pid"

stop_service \
"vLLM" \
"$TMP_ROOT/vllm.pid"

for pid in $(pgrep -f '[E]ngineCore' 2>/dev/null); do
    kill -TERM "$pid" 2>/dev/null || true
done

sync
echo "VideoFusion工作流服务已停止"
