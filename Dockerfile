FROM mcr.microsoft.com/playwright/python:v1.54.0

# 设置时区为亚洲/上海
ENV TZ=Asia/Shanghai

# 设置工作目录
WORKDIR /app

# 更新apt-get并安装tzdata
RUN apt-get update && apt-get install -y \
    tzdata \
    && ln -fs /usr/share/zoneinfo/$TZ /etc/localtime \
    && dpkg-reconfigure -f noninteractive tzdata \
    && apt-get install -y \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .
# 安装依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制所有文件
COPY . .

# 创建临时文件目录
RUN mkdir -p /app/temp

# 运行主程序
CMD ["python", "main.py"]
