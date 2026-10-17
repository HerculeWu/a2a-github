# a2a-github — original spec (verbatim, 2026-10-17)

> Source of truth for the original intent. Decisions that refine or change it
> are recorded in `docs/adr/` and in the grilling outcome; read those first.

## 背景
多个人和多个 agent 通过同一个 GitHub 仓库协作：issue 用于通信，PR 用于提交代码。agent 需要及时知道"有什么新东西和我有关"，但不能靠反复轮询把完整 issue 内容灌进上下文。

你要做的是一个**与角色无关的能力层**：一组独立的 CLI 原语。不要假设 agent 是路由、单兵还是别的什么；不要在代码里内置任何"谁该处理什么"的策略。策略全部由使用者通过配置或组合命令决定。

## 技术约束
- Python 3.11+，单包 `a2a/`，入口命令 `a2a`
- 所有 GitHub 访问走 `gh` CLI（`gh api` / `gh issue view` 等），不直接用 token 调 REST
- 对 `gh` 的调用必须收口在一个 `GhClient` 类里，构造时可注入替身，便于测试
- 本地数据全部在 `.a2a/` 目录下：`config.toml`、`inbox.jsonl`、`state.json`、`etags.json`、`seen.json`
- 除 `gh` 外只用标准库（toml 解析用 `tomllib`）
- 输出面向 agent 消费：默认极简纯文本，`--json` 给机器可读格式

## 五个原语

### 1. `a2a watch [--once] [--interval SEC]`
守护进程，拉取仓库的 issue / issue comment / PR / PR review 事件，按配置过滤，命中的写入 `inbox.jsonl`。
- 用 `gh api` 带 `If-None-Match` 头做条件请求，304 时什么也不做。ETag 持久化到 `etags.json`
- 用 `seen.json` 按 `(type, id, updated_at)` 去重，保证重启或重复拉取不产生重复 inbox 条目
- `--once` 只跑一轮就退出（给测试和 cron 用）
- 过滤规则从 `config.toml` 读，支持：`assignee`、`mentions`（@名）、`labels`、`title_regex`、`body_regex`、`participated`（我评论过的 issue 有新动态）。规则之间是 OR
- inbox 每条记录字段：`id`、`ts`、`type`（issue_opened / comment / pr_opened / review / assigned / labeled ...）、`number`、`author`、`title`、`snippet`（正文前 200 字符，单行）、`url`、`matched_rules`、`read: false`

### 2. `a2a inbox list [--unread] [--since ISO] [--type T] [--limit N]`
默认每条一行，格式固定：
`#123  comment   alice  2026-10-17T17:40  能不能改成…`
`a2a inbox ack <id|#number|--all>` 标记已读。
`a2a inbox count --unread` 只输出一个数字。

### 3. `a2a fetch issue <N> [--since ISO] [--comments-only] [--max-chars N]`
拉取单个 issue 的正文和评论，输出为紧凑 Markdown。`--since` 只输出该时间之后的评论；`--max-chars` 从末尾截断并标注 `[truncated]`。
同样提供 `a2a fetch pr <N> [--diff] [--files]`，`--diff` 默认只给 `--stat`，加 `--full` 才给完整 diff。

### 4. `a2a notify`
当 `inbox count --unread > 0` 时，生成一行摘要（如 `inbox: 3 unread — #123 comment(alice), #130 assigned, #131 review(bob)`）并发送到配置的通道。
通道可插拔，`config.toml` 的 `[notify]` 里选 `sink = "stdout" | "file" | "command"`。
- `file`：追加到指定路径
- `command`：把摘要作为 stdin 喂给指定命令
不要内置任何特定 agent 的接入方式；`command` 就是扩展点。

### 5. `a2a state get <key>` / `set <key> <value>` / `delete <key>` / `dump`
一个扁平 JSON 键值存储，值是任意 JSON。写入要原子（写临时文件再 rename）。

## 配置示例（请生成 `a2a init` 产出这个模板）
```toml
repo = "org/repo"
me = "my-agent-login"

[filters]
assignee = true
mentions = true
participated = true
labels = ["pin:my-agent"]
title_regex = ""
body_regex = ""

[watch]
interval = 60

[notify]
sink = "file"
path = ".a2a/notify.log"
```

## 交付物
1. 可运行的包和 CLI, 并可以作为claude code的plugin安装
2. `README.md`：每个原语一段，含三种组合示例（常驻路由型、单兵型、纯人工查看型），中英双语
3. `SKILL.md`：面向 agent 的使用说明，告诉 agent 什么时候用哪个命令、如何只读需要的那个 issue 来控制上下文。SKILL及其它agent可见内容保持纯英语。
4. 完整测试，见下

## 6. 测试策略（必须按这个做）

**分层：**

**a. 纯函数单元测试（无 I/O）**
- 过滤规则：给定一个事件 dict 和一份配置，断言匹配结果和 `matched_rules`。每条规则至少一个正例一个反例，再加组合 OR 的用例
- snippet 生成：多行、超长、含 emoji、空正文
- `fetch` 的截断和 `--since` 过滤逻辑
- inbox 行格式化：固定宽度对齐，用 golden 字符串断言

**b. GhClient 替身测试**
- 实现 `FakeGhClient`，从 `tests/fixtures/*.json` 返回预录的 GitHub API 响应，并能模拟 304
- `watch --once` 跑在 FakeGhClient + 临时目录上，断言 `inbox.jsonl` 内容
- 幂等性：同一批 fixture 跑两次 `watch --once`，inbox 条目数不变
- ETag：第二次调用返回 304 时，断言没有写入也没有读 seen.json 之外的东西
- 增量：fixture A 跑一次，fixture B（A 的超集）跑一次，只新增差集

**c. 本地文件层测试**
- `state set/get` 回环，包括嵌套 JSON、unicode、并发写入（两个进程同时 set 不同 key，最终两个都在）
- `inbox ack` 后 `--unread` 不再列出，文件格式仍合法
- 所有写操作中途被 kill（用 monkeypatch 让 rename 前抛异常）不损坏原文件

**d. CLI 集成测试**
- 用 `subprocess` 跑真实的 `a2a` 命令，环境变量 `A2A_GH_FAKE=1` 时让 GhClient 走替身
- 覆盖每条命令的 `--json` 输出能被 `json.loads`
- `notify` 的三种 sink：stdout 捕获、file 追加、command 收到正确 stdin

**e. 真实仓库冒烟测试（默认跳过）**
- 只在设置了 `A2A_TEST_REPO=org/sandbox` 时运行
- 创建一个 issue → `watch --once` → 断言 inbox 有它 → 评论 → 再 watch → 断言有 comment 事件 → 关闭 issue 清理

**工具：** pytest，`tests/conftest.py` 提供 `tmp_a2a_dir` 和 `fake_gh` fixture。目标覆盖率 ≥ 85%，用 `pytest --cov`。

**顺序要求：** 先写 a 和 b 的测试（红），再实现让它们通过（绿），最后补 c/d/e。每个原语独立提交一次。
