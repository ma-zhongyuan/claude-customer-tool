# 代码助手 MVP（Claude API 版）

这是一个能直接起步的最小版本，适合你验证“卖代码场景 AI 额度包”这个方向。

## 功能
- 注册测试用户
- 为用户分配额度点数
- 提交编程问题 / 代码 / 报错
- 调用 Anthropic Claude API 返回回答
- 自动扣减额度
- 保存聊天记录到 SQLite

## 适合验证的商品形态
- 9.9 元：20 次基础问题
- 29.9 元：100 次基础问题
- 59.9 元：项目小助手包
- 99 元：复杂问题包

## 目录结构
- `app/main.py`：FastAPI 后端
- `static/index.html`：简单前端页面
- `app.db`：运行后自动生成的 SQLite 数据库
- `.env.example`：环境变量示例

## 本地启动
```bash
cd claude_mvp
python -m venv .venv
source .venv/bin/activate   # Windows 用 .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# 编辑 .env，填入你的 ANTHROPIC_API_KEY
uvicorn app.main:app --reload
```

然后访问：
- http://127.0.0.1:8000

## 关键环境变量
- `ANTHROPIC_API_KEY`：Claude API key
- `ANTHROPIC_MODEL`：默认模型，示例 `claude-sonnet-4-6`
- `MAX_INPUT_CHARS`：单次输入字符上限
- `DEFAULT_INITIAL_CREDITS`：新用户默认赠送点数

## 当前扣费逻辑（演示版）
代码里不是按真实 token 精确计费，而是按输入长度粗略扣点：
- <= 800 字符：1 点
- <= 2500 字符：2 点
- <= 6000 字符：3 点
- 更长：5 点

你后面可以升级成：
1. 用官方 token counting 做预估
2. 按模型分层（便宜模型 / 强模型）
3. 按功能包收费（基础问答 / 项目分析 / 批量生成）

## 下一步最值得加的 6 件事
1. 接入支付和订单系统
2. 管理后台：给用户充值、封禁、查日志
3. 多模型路由：简单问题走便宜模型，复杂问题走更强模型
4. Prompt caching，降低重复上下文成本
5. 上传文件 / 仓库压缩包
6. 用户登录、邀请码、订单绑定

## 淘宝展示建议
别卖“账号”，卖“工具”或“额度包”：
- 程序报错 AI 助手｜按次数
- 代码修复助手｜项目问题问答
- 开发者 AI 小工具｜调试解释写测试

## 风险提醒
- 不要宣传成“Claude 账号”
- 不要做无限量低价包年
- 一定要限制单次输入长度和每日额度
- 先做小场景，再扩展
