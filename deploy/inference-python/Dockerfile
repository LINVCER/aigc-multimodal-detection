# Python 推理服务（论文 AIGC 文本检测）
# build context 必须是仓库根目录，因为要把 ml/common（模型定义 / 表层特征 / checkpoint 契约）一起打进去：
#   docker build -f deploy/inference-python/Dockerfile -t paperaigc-inference .
# 运行时挂 checkpoint 与 backbone：
#   docker run -p 18000:8000 -v ./ml/checkpoints:/app/ml/checkpoints -v ./models:/app/models \
#     -e TEXT_CHECKPOINT_PATH=/app/ml/checkpoints/text/v0.2.0-fusion-mdeberta/best.pth paperaigc-inference
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY deploy/inference-python/requirements.txt .
RUN pip install --no-cache-dir -i https://mirrors.aliyun.com/pypi/simple/ -r requirements.txt

# 与训练侧共用的模型 / 特征 / checkpoint 契约（detectors/text.py 通过 sys.path 找到 /app/ml）
COPY ml/__init__.py ml/__init__.py
COPY ml/common ml/common
COPY deploy/inference-python/detectors detectors
COPY deploy/inference-python/main.py .

ENV PYTHONPATH=/app

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=5s --retries=5 \
  CMD curl -fsS http://localhost:8000/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
