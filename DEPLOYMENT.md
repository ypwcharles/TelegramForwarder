# 项目部署指南

本文档提供了将此 Telegram 机器人项目部署到一台新的 `amd64` 架构服务器（例如 Lightsail, EC2, etc.）上的详细步骤。

---

### 一、 首次部署

如果您是在一台全新的服务器上从零开始部署，请遵循以下步骤。

**1. 安装 Docker 和 Docker Compose**

请根据您服务器的操作系统，参考 Docker 官方文档完成安装。

**2. 克隆项目仓库**

```bash
git clone <your-repo-url>
cd TelegramForwarder
```

**3. 创建必要的目录**

`docker-compose` 文件需要将服务器上的一些目录挂载到容器内部，用于持久化存储数据。请执行以下命令创建这些目录：

```bash
mkdir -p db logs sessions temp config
mkdir -p ufb/config
mkdir -p rss/data rss/media
```

**4. 创建生产环境配置文件 (`.env`)**

这是最关键的步骤之一。您需要创建一个名为 `.env` 的文件，其中包含您**线上生产环境**的配置。

```bash
# 1. 从模板复制一份配置文件
cp .env.example .env

# 2. 编辑 .env 文件
nano .env
```

在编辑器中，请务必填写您的**生产环境（主号）**信息，特别是：
- `API_ID`
- `API_HASH`
- `PHONE_NUMBER`
- `BOT_TOKEN` (您的主机器人的 Token)
- `USER_ID` (您的主用户 ID)
- `DATABASE_URL` (建议保持 `sqlite:///./db/forward.db`)

**5. 准备 Docker Compose 文件**

本项目包含 Docker Compose 文件：
- `docker-compose.yml`: 用于构建镜像


您需要将部署模板复制为服务器上实际使用的 `docker-compose.yml` 文件：

```bash
cp docker-compose.yml docker-compose.yml
```

**6. 启动服务**

现在，一切准备就绪。执行以下命令来启动服务：

```bash
# 1. 从 Docker Hub 拉取我们预先构建好的 amd64 镜像
docker-compose pull

# 2. 在后台启动服务
docker-compose up -d
```

**7. 验证**

使用 `docker-compose logs -f` 查看日志，确保程序正常启动，没有报错。

---

### 二、 更新部署

当您在本地开发了新功能（就像我们刚刚做的一样），并希望更新到线上服务器时，请遵循以下流程。

**1. （本地）构建并推送新版镜像**

在您的本地开发机上，使用 `buildx` 构建一个带**新版本号**的 `amd64` 镜像并推送到 Docker Hub。

```bash
# 示例：将版本号更新为 v2.2.0
docker buildx build --platform linux/amd64 -t your-dockerhub-username/telegram-forwarder:v2.2.0 --push .
```

**2. （本地）更新部署文件**

修改 `docker-compose.yml` 文件，将 `image` 字段指向您刚刚推送的新版本号。

```yaml
# docker-compose-syn.yml
services:
  telegram-forwarder:
    image: your-dockerhub-username/telegram-forwarder:latest # <-- 更新这里的版本号
    ...
```

**3. （本地）上传文件到服务器**

使用以下命令将更新后的 `docker-compose-syn.yml` 文件上传到服务器：

```bash
# 设置密钥权限（如果尚未设置）
chmod 400 ~/path/to/your/key.pem

# 上传 docker-compose-syn.yml 文件到服务器（上传后改名为 docker-compose.yml）
scp -i ~/path/to/your/key.pem \
  ./docker-compose-syn.yml \
  ubuntu@your.server.ip:~/telegram_forwarder/docker-compose.yml

# 如果需要上传其他文件（如 .env），使用类似的命令
scp -i ~/path/to/your/key.pem \
  ./.env \
  ubuntu@your.server.ip:~/telegram_forwarder/.env
```

**4. （线上服务器）执行更新**

使用 SSH 登录到服务器并执行以下操作：

```bash
# 登录到服务器
ssh -i ~/path/to/your/key.pem \
  ubuntu@your.server.ip

# 进入项目目录（如果没有需要先创建）
mkdir -p ~/telegram_forwarder
cd ~/telegram_forwarder

# 0. (安全第一) 备份当前数据库！
# 可以先 docker-compose down 停掉服务，再操作，更安全
docker-compose down
cp ./db/forward.db ./db/forward.db.backup-$(date +%Y%m%d-%H%M%S)

# 1. 将 .env 文件复制到项目目录（如果上传了的话）
# 如果 .env 文件直接上传到了项目目录，这步可以跳过

# 2. 拉取新的镜像
docker-compose pull

# 3. 使用新镜像强制重新创建并启动服务
docker-compose up -d --force-recreate
```

**5. （线上服务器）验证和回滚**
- 使用 `docker-compose logs -f` 观察日志，确保一切正常。
- 如果出现严重问题，您可以立即执行 `docker-compose down`，用备份的数据库文件覆盖现有文件，然后修改 `docker-compose.yml` 指向**上一个可用**的镜像版本，再 `docker-compose up -d` 即可快速回滚。
