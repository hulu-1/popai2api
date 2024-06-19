# 使用基础镜像
FROM python:3.8-slim

# 设置工作目录
WORKDIR /app

# 安装必要的依赖项
RUN apt-get update && apt-get install -y \
    wget \
    unzip \
    xvfb \
    libxi6 \
    libgconf-2-4 \
    libnss3 \
    libxss1 \
    libappindicator1 \
    gnupg \
    --no-install-recommends

RUN rm -rf /var/lib/apt/lists/*

# 添加Google的签名密钥
RUN wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | apt-key add -

# 添加Google Chrome的仓库
RUN sh -c 'echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list'

# 更新软件包列表并安装Google Chrome
RUN apt-get update && apt-get install -y google-chrome-stable
    
# 清理APT缓存
RUN apt-get clean && rm -rf /var/lib/apt/lists/*

# 下载并安装 ChromeDriver
RUN  wget -q "https://storage.googleapis.com/chrome-for-testing-public/126.0.6478.62/linux64/chromedriver-linux64.zip" \
    && unzip chromedriver-linux64.zip \
    && cd chromedriver-linux64/ \
    && mv chromedriver /usr/local/bin/ \
    && cd .. \
    && rm chromedriver-linux64.zip

# 复制应用程序代码到工作目录
COPY . .

# 安装 Python 依赖项
RUN pip install --no-cache-dir -r requirements.txt

# 设置环境变量
ENV DISPLAY=:99

# 暴露端口
EXPOSE 3000

# 启动应用程序
ENTRYPOINT ["python", "./main.py"]