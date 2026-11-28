# 长期记忆与课程 Wiki · 服务器部署计划

**启动条件。** [本地开发计划](./长期记忆与课程Wiki-本地开发计划.md)已验收，并且项目维护者明确决定开始部署。部署时选定要上线的版本，结合本地验收后新增的功能复核接口、数据迁移和生产配置。复用本地阶段已验证的业务模块与数据结构。

## 部署步骤

1. **生产入口。** 沿用宝塔 Nginx、HTTPS 域名和 Docker Compose。宿主机 443 转发到 `127.0.0.1:8080`，FastAPI 留在容器内部。宿主代理把 `Host` 设为 `$http_host`，把 `X-Forwarded-For` 设为 `$remote_addr`，把 `X-Forwarded-Proto` 设为 `$scheme`。给 SSE 保持 300 秒读取超时并关闭代理缓冲。站点页面保留容器 Nginx 的 `Referrer-Policy: same-origin`，账号与业务 API 使用后端设置的 `no-referrer`。
2. **配置账号和模型。** 从 [环境变量示例](../backend/.env.example) 配置 `backend/.env`。必填项包括公开 HTTPS 地址 `SITE_ORIGIN`、`AUTH_AI_ACCOUNT_DAILY` 和 `AUTH_AI_SITE_DAILY`。用户用用户名和密码注册并登录后可使用站点配置的模型。额度按每次上游请求计量，每天香港时间 08:00 恢复。从后端容器测试模型与视频平台连通性，按需配置容器可访问的出口代理。
3. **运行环境。** Compose 的 `app-data` 卷保存账号库和所有个人库，`model-cache` 卷保存共享语义模型。以单台 **2 核 4 GB**、一个 FastAPI 进程运行。可先执行 `docker compose run --rm --no-deps backend python -m services.study_embeddings --prepare` 准备模型。升级前备份，重建时使用原数据卷。
4. **试运行和切换入口。** 从测试 HTTPS 域名在浏览器走一遍用户名注册、登录和退出。验证两个账号的数据隔离，以及手机和电脑登录同一账号后的资料连续性。正式站点在完成这些验证后从 Basic Auth 切到站内登录。若须回滚，恢复升级前的镜像、数据卷和入口配置，并保留新版数据卷供核对。

## 旧库导入和备份恢复

- 旧资料由维护者一次性导入。先注册目标用户名，再把可信的旧库副本作为只读文件挂载给维护容器。暂停后端，执行 `python -m maintenance import-library /transfer/legacy-copy.sqlite3 --username learner_demo`，然后启动服务并核对资料、Wiki 和历史。已使用的账号需要另选空账号承接副本。
- 旧版邮箱账号的 SQLite 库启动时会升级，账号 ID、密码哈希和个人资料保持一致。已有用户在用户名栏填写原邮箱地址，用原站内密码登录。升级前保留账号库和个人库的备份。
- 每日备份在维护窗口进行。暂停后端后，由维护容器运行 SQLite 快照命令。确认输出目录包含 `accounts.sqlite3` 和 `users/` 中的现有个人库，再用运维侧的备份工具加密并复制到另一台机器或备份存储。启动后端并检查 `/api/health`。在同一主机验证导入和备份时，测试实例使用独立数据卷。

```bash
docker compose stop backend
docker compose run --rm --no-deps -v /srv/magical-backups:/backups backend \
  python -m maintenance backup "/backups/snapshot-$(date +%Y%m%d-%H%M)"
docker compose up -d backend
```

- 恢复时把备份解密至维护目录，并准备一个新数据卷。运行以下命令后，在独立测试环境把恢复卷挂载到 `/data`，将 `STUDY_DATA_DIR` 指向 `/data/data`。用两位测试账号登录并检查各自的资料和历史。恢复后的所有设备需要重新登录。

```bash
docker volume create magical-video-recovered
docker compose run --rm --no-deps -v /srv/magical-backups:/backups:ro \
  -v magical-video-recovered:/recovered backend \
  python -m maintenance --data-dir /recovered/data restore /backups/所选备份目录
```

## 上线完成条件

- [ ] 验证登录、退出和会话过期恢复。检查未登录请求会被受保护的资料库、分析、问答和任务 API 拒绝，后端端口仅供容器内部访问。
- [ ] 用电脑、iOS Safari 和 Android Chrome 验证从登录到打开课程、提问和核对引文的流程。覆盖锁屏、断网、换设备和未保存资料的限时访问。
- [ ] 在目标服务器记录资源使用与检索耗时。重建容器后验证资料和对话仍可访问，在测试环境完成一次备份恢复演练。
- [ ] 记录管理员的安装、升级、恢复、回滚和排障步骤，以及客户端如何登录、提交视频和换设备继续学习。

## 旧版邮箱登录验收记录

| 记录项 | 当前记录 |
| --- | --- |
| 状态 | 2026-11-27 旧版在本地和隔离 Compose 验收通过。当前用户名版的本地结果见[本地开发计划](./长期记忆与课程Wiki-本地开发计划.md)，正式上线待安排 |
| 验证环境 | 本机独立 Colima，2 核 4 GB，Python 3.12 后端容器，Nginx 静态前端，测试 HTTPS 代理和 TLS SMTP 收件箱 |
| 注册与重建 | 两个测试账号完成注册与登录，同一账号两个独立会话可同时读取资料。验证生产 Cookie 属性，重建后端后账号和导入资料仍可读取 |
| Nginx 来源校验复测 | 2026-11-27 从隔离 Compose 的本机 HTTP 入口用浏览器完成注册发信、登录和退出，并确认跨来源写请求返回 403。[本地复测记录](./长期记忆与课程Wiki-本地开发计划.md#代码审查修复与复测2026-11-27) |
| 迁移与恢复 | 将当前工作树旧库副本导入指定空账号，确认 3 条归档和 1 门课程可读。启用新卷恢复后，两账号资料仍隔离，旧会话失效，旧库原件校验一致。自动化另验证带字幕引用的问答历史往返恢复 |
| 语义检索与队列 | 共享 E5 模型达到就绪状态，两个账号的短问答任务均完成，用时约 0.06 秒。任务结束后的单次内存采样约为后端 846 MiB、Nginx 3.3 MiB。该轮问答为无上下文的澄清路径，承载实际模型与视频并行流量需在正式测试域名复测 |
| 待上线验证 | 当前用户名版在测试域名的注册登录、生产代理链路和 iOS Safari、Android Chrome 实机。在上线目标环境验证服务端模型和视频平台连通性，以及异机加密备份恢复 |
