# 使用 Python 轻量镜像
FROM python:3.9-slim

# 设置容器内的工作目录
WORKDIR /app

# 将 requirements.txt 复制到容器内
COPY requirements.txt /app/requirements.txt

# 安装 pip 的最新版本
RUN pip install --upgrade pip

# 安装依赖库
RUN pip install --no-cache-dir -r requirements.txt

# 将当前目录的文件复制到容器内
COPY . /app

# 暴露 HTTP 服务端口
EXPOSE 7777

# 运行脚本
CMD ["python", "wechat-teslamate.py"]