#!/usr/bin/env bash
set -Eeuo pipefail

PYTHON="${PYTHON:-python}"
VLLM="${VLLM:-vllm}"
CLOUD_ROOT="${VIDEOFUSION_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
COMFY_ROOT=$CLOUD_ROOT/ComfyUI
TMP_ROOT="${VIDEOFUSION_TMP_ROOT:-/tmp/videofusion}"

if [ -f "$CLOUD_ROOT/env.sh" ]; then
    source "$CLOUD_ROOT/env.sh"
fi

if [ -f "$CLOUD_ROOT/config/service.env" ]; then
    source "$CLOUD_ROOT/config/service.env"
fi

hash -r

mkdir -p \
"$TMP_ROOT/logs" \
"$TMP_ROOT/jobs" \
"$TMP_ROOT/comfyui/input" \
"$TMP_ROOT/comfyui/output" \
"$TMP_ROOT/comfyui/temp"

MODEL_PATH="${VIDEOFUSION_MODEL_PATH:-/models/qwen3-vl-30b-a3b-instruct-awq-v1}"
SHARD_COUNT=$(find "$MODEL_PATH" -maxdepth 1 \
-name 'model-*-of-00006.safetensors' -type f | wc -l)

if [ "$SHARD_COUNT" -ne 6 ]; then
    echo "错误：模型分片数量为 $SHARD_COUNT，应为6"
    exit 1
fi

if pgrep -f '[v]llm serve|[E]ngineCore' >/dev/null; then
    echo "错误：vLLM已经运行，请勿重复启动"
    exit 1
fi

if pgrep -f '[C]omfyUI/main.py|python main.py.*--port 6006' >/dev/null; then
    echo "错误：ComfyUI已经运行，请勿重复启动"
    exit 1
fi

GPU_NAME=$(nvidia-smi --query-gpu=name \
--format=csv,noheader | head -n 1)
GPU_MEMORY=$(nvidia-smi --query-gpu=memory.total \
--format=csv,noheader,nounits | head -n 1 | tr -d ' ')

if [ "$GPU_MEMORY" -le 40000 ]; then
    GPU_UTILIZATION=0.88
else
    GPU_UTILIZATION=0.70
fi

echo "GPU：$GPU_NAME"
echo "显存：${GPU_MEMORY} MiB"
echo "vLLM显存利用率：$GPU_UTILIZATION"

nohup env VLLM_USE_FLASHINFER_SAMPLER=0 \
"$VLLM" serve "$MODEL_PATH" \
--served-model-name "$VIDEOFUSION_MODEL_NAME" \
--host 127.0.0.1 \
--port 8000 \
--dtype auto \
--gpu-memory-utilization "$GPU_UTILIZATION" \
--max-model-len 8192 \
--max-num-seqs 1 \
--limit-mm-per-prompt '{"image":8,"video":1}' \
--trust-remote-code \
> "$TMP_ROOT/logs/vllm-workflow.log" 2>&1 &

VLLM_PID=$!
echo "$VLLM_PID" > "$TMP_ROOT/vllm.pid"
echo "vLLM启动中，PID=$VLLM_PID"

VLLM_READY=0
for i in $(seq 1 600); do
    if ! kill -0 "$VLLM_PID" 2>/dev/null; then
        echo "错误：vLLM进程提前退出"
        tail -n 40 "$TMP_ROOT/logs/vllm-workflow.log"
        exit 1
    fi

    if curl -fsS --max-time 2 \
    http://127.0.0.1:8000/health >/dev/null 2>&1; then
        VLLM_READY=1
        break
    fi
    sleep 1
done

if [ "$VLLM_READY" -ne 1 ]; then
    echo "错误：vLLM在600秒内未就绪"
    kill -TERM "$VLLM_PID" 2>/dev/null || true
    exit 1
fi

echo "vLLM已经就绪"

cd "$COMFY_ROOT"
nohup env PYTHONPATH="$CLOUD_ROOT" \
"$PYTHON" main.py \
--listen 0.0.0.0 \
--port 6006 \
--disable-auto-launch \
--input-directory "$TMP_ROOT/comfyui/input" \
--output-directory "$TMP_ROOT/comfyui/output" \
--temp-directory "$TMP_ROOT/comfyui/temp" \
> "$TMP_ROOT/logs/comfyui-workflow.log" 2>&1 &

COMFY_PID=$!
echo "$COMFY_PID" > "$TMP_ROOT/comfyui.pid"
echo "ComfyUI启动中，PID=$COMFY_PID"

for i in $(seq 1 120); do
    if ! kill -0 "$COMFY_PID" 2>/dev/null; then
        echo "错误：ComfyUI进程提前退出"
        tail -n 40 "$TMP_ROOT/logs/comfyui-workflow.log"
        kill -TERM "$VLLM_PID" 2>/dev/null || true
        exit 1
    fi

    if curl -fsS --max-time 2 \
    http://127.0.0.1:6006/system_stats >/dev/null 2>&1; then
        echo "VideoFusion ComfyUI工作流服务已经就绪"
        echo "ComfyUI：http://0.0.0.0:6006"
        echo "vLLM：http://127.0.0.1:8000"
        exit 0
    fi
    sleep 1
done

echo "错误：ComfyUI在120秒内未就绪"
kill -TERM "$COMFY_PID" "$VLLM_PID" 2>/dev/null || true
exit 1
