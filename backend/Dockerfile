FROM python:3.11-slim

# 构建参数：选择依赖文件（requirements-api.txt 或 requirements.txt）
ARG REQUIREMENTS_FILE=requirements-api.txt

# 安装运行时依赖（FFmpeg 用于视频合成）
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app/backend

# 先装依赖（利用 Docker 缓存层）
COPY ${REQUIREMENTS_FILE} requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# 复制后端代码
COPY . .

# 创建运行时目录（确保权限正确）
RUN mkdir -p ../assets ../models/lora ../exports ../logs ../qc_reports

EXPOSE 8000

CMD ["uvicorn", "main_app:app", "--host", "0.0.0.0", "--port", "8000"]