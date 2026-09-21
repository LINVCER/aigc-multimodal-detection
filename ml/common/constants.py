"""训练 / 推理共用的口径常量（推理镜像只 COPY ml/common，因此不能放在 ml/datasets 里）。"""

# Fraser 2025 §5.3：约 120 词即可让微调检测器发挥完整潜力；中文按字符取同量级门槛。
# 训练集过滤与推理侧 warning 都用这一个值。
MIN_CHARS: int = 120

# 与 backend TextProcessor 段落切分上限一致，超长段落截断后再入库
MAX_CHARS: int = 1600
