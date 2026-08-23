# maoshqi-videoauto

猫十七 VideoAuto：基于 Qwen3-VL 的八帧视频片段分析与自动打标工作流。

功能：ComfyUI 八帧视频片段分析、详细提示词分析、结构化 JSON 输出和 API 工作流调用。

运行要求：建议使用 32GB 以上显存的 NVIDIA GPU。
模型默认路径：/models/qwen3-vl-30b-a3b-instruct-awq-v1

启动：bash bin/start-workflow.sh
停止：bash bin/stop-workflow.sh

工作流文件：workflows/猫十七videoauto.json 和 workflows/猫十七videoauto_api.json
