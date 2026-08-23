#!/usr/bin/env bash
set -u

TMP_ROOT="${VIDEOFUSION_TMP_ROOT:-/tmp/videofusion}"

echo "=== 模型 ==="
MODEL="${VIDEOFUSION_MODEL_PATH:-/models/qwen3-vl-30b-a3b-instruct-awq-v1}"
echo "分片数量：$(find "$MODEL" -maxdepth 1 -name 'model-*-of-00006.safetensors' -type f 2>/dev/null | wc -l)"
du -sh "$MODEL" 2>/dev/null || echo "模型目录不存在"

echo "=== 进程 ==="
pgrep -af "vllm|EngineCore|main.py.*--port 6006" || \
echo "服务进程未运行"

echo "=== 接口 ==="
curl -sS --max-time 5 -o /dev/null \
-w "vLLM=%{http_code}\n" \
http://127.0.0.1:8000/health 2>/dev/null || \
echo "vLLM=000"

curl -sS --max-time 5 -o /dev/null \
-w "ComfyUI=%{http_code}\n" \
http://127.0.0.1:6006/system_stats 2>/dev/null || \
echo "ComfyUI=000"

echo "=== 自定义节点 ==="
NODE_STATUS=$(curl -sS --max-time 5 \
http://127.0.0.1:6006/object_info/VideoFusionSixFrameAnalyzer \
2>/dev/null || true)

if printf '%s' "$NODE_STATUS" | grep -q \
'VideoFusionSixFrameAnalyzer'; then
    echo "VideoFusion八帧节点=已注册"
else
    echo "VideoFusion八帧节点=不可用"
fi

echo "=== GPU ==="
nvidia-smi --query-gpu=name,memory.total,memory.used,memory.free \
--format=csv

echo "=== 磁盘 ==="
df -h / "$TMP_ROOT" "$MODEL"
