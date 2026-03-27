【最简单的公网部署办法：Render】

你要准备：
1. 一个 GitHub 账号
2. 一个 Render 账号
3. 这个项目文件

步骤：
1. 把整个项目上传到 GitHub 仓库
2. 登录 Render
3. 选择 New + -> Web Service
4. 连接你的 GitHub 仓库
5. Render 会自动识别 render.yaml
6. 在 Environment Variables 里填写：
   - ANTHROPIC_API_KEY
   - ANTHROPIC_MODEL=claude-sonnet-4-6
   - MAX_INPUT_CHARS=12000
   - DEFAULT_INITIAL_CREDITS=20
   - ADMIN_PASSWORD=你自己的后台密码
7. 点击 Deploy
8. 部署完成后，Render 会给你一个公开网址

顾客访问：
- 首页：你的 Render 网址 /
- 管理员后台：你的 Render 网址 /admin

注意：
1. 不要把 .env 上传到 GitHub
2. 公网版不要继续用本地的 127.0.0.1
3. app.db 是本地 SQLite 数据库，平台重启时可能丢数据；正式卖的时候建议后面换成真正数据库
