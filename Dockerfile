# 使用 Python 轻量镜像
FROM python:3.9-slim

# 设置环境变量，防止 Python 缓存文件和输出缓冲
ENV PYTHONDONTWRITEBYTECODE=1  # 不生成 .pyc 文件
ENV PYTHONUNBUFFERED=1         # 实时输出日志（无缓冲）

# 设置容器内的工作目录
WORKDIR /app

# 将当前目录的文件复制到容器内
COPY . /app

# 安装 pip 的最新版本
RUN pip install --upgrade pip

# 安装依赖库，同时使用 requirements.txt（更易维护）
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# 运行脚本
CMD ["python", "wechat-teslamate.py"]