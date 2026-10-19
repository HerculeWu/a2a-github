# a2a-github

[English](#english) · [中文](#中文)

---

## English

Humans and agents collaborate through one GitHub repository: issues to talk, PRs to ship code. `a2a` tells each participant **what new activity concerns them**, without polling full issue threads into an agent's context.

It is a role-agnostic capability layer, a set of independent CLI primitives. It has no built-in idea of routers, workers or who should handle what. That policy lives in your config and in how you compose the commands.

Requirements: Python 3.11+ and an authenticated [`gh`](https://cli.github.com/) CLI. There are no other dependencies.

### Install

```bash
# As a Claude Code plugin (puts `a2a` on the agent's PATH and adds the a2a, setup and protocol skills)
claude plugin marketplace add HerculeWu/a2a-github
claude plugin install a2a-github@a2a-github

# As a standalone CLI
pipx install git+https://github.com/HerculeWu/a2a-github
```

Then, in a clone of the repository you collaborate in:

```bash
a2a init                 # writes .a2a/config.toml (repos and login detected via gh)
a2a watch --once         # first round: starts observing from now
```

One workspace can observe several repositories: `a2a init --repo lab/paper --repo lab/sim`. Every thread is then written `owner/name#N`, as in `lab/sim#7`.

**Upgrading from 0.1:** in `.a2a/config.toml`, change `repo = "org/repo"` to `repos = ["org/repo"]`. Your inbox, read state and seen cursors are kept.

### Join a team (Claude Code plugin)

Run `/a2a-github:setup` in an agent session, optionally with a few words about the agent, e.g. `/a2a-github:setup I'm agent-y, I review PRs and never merge`. The agent:
1. finds the team's **Protocol**, the one open issue labelled `a2a:protocol`, and creates it if there is none;
2. asks you for its name (`me`) and creates its workspace;
3. asks you, in one batch, only for the fields your arguments did not cover;
4. after you confirm, posts its **Join Comment** in that issue.

The Protocol is yours to define. a2a requires only the agent's name and its GitHub login. Every other field is the team's choice, such as capabilities, permissions, work it takes on or refuses, model or harness. The agent that creates the Protocol asks you which fields to require.

Good to know:
- **Names.** Give each agent its own name, even when it runs under your own GitHub account. Otherwise your unsigned comments would count as the agent's own. Names must be unique in the team, and must not be someone's GitHub username, because `@name` would notify that person.
- **Several agents in one checkout.** The second agent gets its own workspace, `.a2a-<name>/`. Set `A2A_DIR=.a2a-<name>` in that agent's environment.
- **Starting together.** If several agents run setup at the same moment, exactly one creates the Protocol and the others join it. Creating the label is the claim, and GitHub lets only one create succeed.
- **Keep a watcher running** (`a2a watch --notify`). Protocol changes reach members only through their inbox.
- **Several repositories.** The Protocol lives in the team's **Home** repository, the one that holds the deliverable, such as a paper. It may list **Linked** repositories whose work feeds Home, such as simulation or analysis code. Setup makes each agent observe Home plus every Linked repository its account can read. Run setup from a Linked repository's checkout and it finds Home by itself, or tell it: `/a2a-github:setup home=lab/paper`. Say "not lab/db" to skip one.

The agent that creates the Protocol is its **Steward**, the only one who may change it. Run `/a2a-github:protocol` to change the Protocol, to see who lags behind, or to hand the role over; a handover needs nobody's consent. Every change is announced in the issue, and each member resyncs by running setup again, which edits its Join Comment in place. A change that does not come from the Steward is a conflict, and members ask their human instead of following it.

### Primitives

**`a2a watch [--once] [--interval SEC] [--backfill 7d] [--notify]`**: polls four repository streams: issues and PRs, issue comments, review comments, and issue events. It also reads reviews on PRs that changed. Each stream is polled with `If-None-Match`, so a quiet repository costs four free `304` responses per round. Activity that matches your filter rules is appended to `.a2a/inbox.jsonl`. Seen ids and per-stream cursors make repeated or restarted rounds idempotent. The first run only records what already exists and delivers none of it, unless you pass `--backfill`, which delivers the activity of that last stretch. `--once` runs one round, for cron and scripts; without it, `watch` keeps running and honours GitHub's `X-Poll-Interval`.

**`a2a inbox list [--unread] [--since ISO] [--type T[,T]] [--limit N]` · `inbox ack <id|owner/name#N>… | --all` · `inbox count [--unread]`**: one line per entry, such as `lab/paper#123  comment   alice  2026-10-17T17:40  can we change…`. `ack lab/paper#123` marks every entry of that thread as read; a bare `#123` works while the workspace observes one repository. `count` prints just a number. Read state is stored apart from the append-only inbox, so acking never races the watcher.

**`a2a fetch issue THREAD [--since ISO] [--comments-only] [--max-chars N]`** and **`a2a fetch pr THREAD [… | --files | --diff [PATH…]]`**: one thread, such as `lab/sim#7`, as compact Markdown, from any repository your account can read. `--since` keeps only later comments. `--max-chars` keeps the header and the newest comments that fit, and reports how many older ones it omitted. `fetch pr` interleaves comments and reviews, including inline review notes. `--files` lists `+add -del` per file, and `--diff` prints the patch, optionally only for some paths.

**`a2a notify [--force] [--sink stdout|file|command]`**: when unread entries arrived since the last digest, it sends one line such as `inbox: 3 unread — lab/paper#123 comment(alice), lab/sim#7 assigned, lab/paper#131 review(bob)` to the configured sink. `file` appends to a path. `command` pipes the line to any program's stdin, and that is the extension point for wiring a2a into any agent or chat tool.

**`a2a state get|set|delete|dump`**: a flat JSON key-value store for your own bookkeeping, such as read cursors or claimed threads. Writes are atomic and locked, so concurrent writers never lose keys. `set k v` stores JSON when `v` parses as JSON and a string otherwise; `--raw` always stores a string.

**`a2a sign [--as NAME]`**: appends your signature to a body read from stdin, for example `echo "On it." | a2a sign | gh issue comment 12 -F -`. When several agents share one GitHub account (say, one human running many agents), the signature is how the watcher attributes activity to the right participant. It also lets each agent ignore its own messages.

Every command takes `--json` and `--dir` (or `A2A_DIR`) to choose the workspace. Without either, the nearest `.a2a/` upward is used.

### Configuration (`.a2a/config.toml`)

```toml
repos = ["org/repo"]   # one or more repositories to observe
login = "my-login"     # the account gh is authenticated as
me = "my-login"        # who this workspace acts for; an agent name when the login is shared

[filters]              # OR-combined, alike for every repository; each entry records repo and matched_rules
assignee = true        # threads assigned to me, and assignments / review requests for me
mentions = true        # @me in the text (plus mention_aliases)
mention_aliases = []
participated = true    # threads I opened, commented on or reviewed
labels = ["pin:my-login"]
title_regex = ""
body_regex = ""
ignore_self = true     # exclusion: never deliver my own activity
exclude_authors = []   # exclusion: globs such as "*[bot]"

[watch]
interval = 60

[notify]
sink = "file"          # stdout | file | command
path = ".a2a/notify.log"
# command = ["notify-send", "a2a"]
```

### Composition examples

**1. Resident router.** A router agent watches everything new and hands work out with labels. Worker agents watch only their own label.

```bash
# router workspace: every new thread concerns it
A2A_DIR=.a2a-router a2a init --me router         # then set  title_regex = "."
A2A_DIR=.a2a-router a2a watch --notify &         # [notify] sink = "command" wakes the router

# the router's policy is plain shell; a2a decides nothing
for t in $(A2A_DIR=.a2a-router a2a inbox list --unread --type issue_opened,pr_opened --json | jq -r '.[] | "\(.repo)#\(.number)"'); do
  gh issue edit "${t#*#}" -R "${t%#*}" --add-label "pin:agent-x"    # pick an owner however you like
  A2A_DIR=.a2a-router a2a inbox ack "$t"
done

# each worker: labels = ["pin:agent-x"]
A2A_DIR=.a2a-agent-x a2a init --me agent-x
```

**2. Solo agent.** One agent with its own workspace, woken by cron, which reads only what it needs.

```bash
# crontab: */5 * * * *  cd /work/repo && a2a watch --once --notify
a2a inbox list --unread
a2a fetch issue org/repo#42 --since "$(a2a state get 'read:org/repo#42')" --max-chars 4000
printf 'Fixed in #43.' | a2a sign | gh issue comment 42 -R org/repo -F -
a2a state set 'read:org/repo#42' "$(date -u +%FT%TZ)"
a2a inbox ack 'org/repo#42'
```

To surface the digest inside Claude Code on every prompt, add a `UserPromptSubmit` hook to your settings. This needs `a2a` on PATH, e.g. via pipx:

```json
{ "hooks": { "UserPromptSubmit": [ { "hooks": [ { "type": "command", "command": "a2a notify --sink stdout" } ] } ] } }
```

**3. Human, read-only.** A person keeps an eye on the repository from a terminal.

```bash
a2a init                                   # [notify] sink = "command", command = ["notify-send", "a2a"]
a2a watch --notify                         # leave running in a tmux pane
a2a inbox list --unread                    # what's new for me
a2a fetch pr org/repo#17 --files           # glance at a PR without opening the browser
a2a inbox ack --all
```

### Files

| file | written by | purpose |
|---|---|---|
| `config.toml` | you | repos, identity, filters, sinks |
| `inbox.jsonl` | watch (append-only) | matched activity |
| `acks.json` | inbox ack | which entries are read |
| `seen.json` / `etags.json` | watch | dedup cursors per repository / conditional-request ETags |
| `state.json` | state | your key-value bookkeeping |
| `notify.json` | notify | last announced entry |

### Development

```bash
uv venv --python 3.11 .venv && uv pip install --python .venv/bin/python -e '.[dev]'
.venv/bin/pytest --cov=a2a                       # unit, fake-gh, file, CLI layers
A2A_TEST_REPO=org/sandbox .venv/bin/pytest -m smoke   # optional: against a real sandbox repo
scripts/dev-link.sh                              # point the installed Claude Code plugin at this checkout
```

Re-run `scripts/dev-link.sh` after `claude plugin update`, a reinstall, or a version bump: each re-copies the plugin and drops the link.

The design and its reasons live in [CONTEXT.md](CONTEXT.md), [docs/design.md](docs/design.md) and [docs/adr/](docs/adr/).

---

## 中文

多个人和多个 agent 通过同一个 GitHub 仓库协作：issue 用来沟通，PR 用来提交代码。`a2a` 告诉每个参与者**有哪些新动态和自己有关**，而不需要反复轮询、把整条 issue 灌进 agent 的上下文。

它是一个与角色无关的能力层：一组彼此独立的 CLI 原语。它不知道什么是"路由""执行者"，也不决定"谁该处理什么"。这些策略由你写在配置里，或者通过组合命令来实现。

依赖：Python 3.11+，以及已登录的 [`gh`](https://cli.github.com/) CLI。除此之外没有任何依赖。

### 安装

```bash
# 作为 Claude Code 插件（会把 `a2a` 加进 agent 的 PATH，并提供 a2a、setup、protocol 三个 skill）
claude plugin marketplace add HerculeWu/a2a-github
claude plugin install a2a-github@a2a-github

# 作为独立 CLI
pipx install git+https://github.com/HerculeWu/a2a-github
```

然后在协作仓库的本地 clone 里运行：

```bash
a2a init                 # 生成 .a2a/config.toml（repos 和 login 通过 gh 自动探测）
a2a watch --once         # 第一轮：从现在开始观察
```

一个 workspace 可以同时观察多个仓库：`a2a init --repo lab/paper --repo lab/sim`。此时每个 thread 都写成 `owner/name#N`，例如 `lab/sim#7`。

**从 0.1 升级：** 在 `.a2a/config.toml` 里把 `repo = "org/repo"` 改成 `repos = ["org/repo"]`。inbox、已读状态和已见游标都会保留。

### 加入团队（Claude Code 插件）

在 agent 会话里运行 `/a2a-github:setup`，可以顺带写几句关于这个 agent 的说明，例如 `/a2a-github:setup 我是 agent-y，负责 review PR，不做 merge`。agent 会：
1. 找到团队**协议**（Protocol），也就是那个打了 `a2a:protocol` 标签的 open issue，没有就新建一个；
2. 问你它叫什么名字（`me`），并创建自己的 workspace；
3. 把参数里没覆盖到的字段一次性问你；
4. 你确认之后，在这个 issue 下发一条**加入评论**（Join Comment）。

协议内容由你们自己定。a2a 只要求写明 agent 的名字和它的 GitHub 账号，其余字段由团队决定，比如能力、权限、接什么活、不接什么活、模型、harness。创建协议的 agent 会问你要求哪些字段。

需要注意：
- **名字**：每个 agent 都要有自己的名字，即使它用的是你本人的 GitHub 账号，否则你没签名的评论会被当成 agent 自己发的。名字在团队里不能重复，也不能和某个 GitHub 用户名相同，否则 `@名字` 会通知到那个人。
- **同一个 checkout 里有多个 agent**：第二个 agent 会用单独的 workspace `.a2a-<名字>/`。请在那个 agent 的环境里设置 `A2A_DIR=.a2a-<名字>`。
- **同时开始**：几个 agent 同时运行 setup 时，只有一个会创建协议，其余的加入它。创建标签就是抢占，GitHub 只允许一次创建成功。
- **保持 watcher 运行**（`a2a watch --notify`）：协议变更只会通过 inbox 通知到各成员。
- **多个仓库**：协议放在团队的 **Home** 仓库里，也就是存放最终成果（比如论文）的那个仓库。协议里可以列出若干 **Linked** 仓库，它们的工作为 Home 服务，比如模拟或分析代码。setup 会让每个 agent 观察 Home，以及它的账号能读到的每个 Linked 仓库。在 Linked 仓库的 checkout 里运行 setup 时，它会自己找到 Home；也可以直接告诉它：`/a2a-github:setup home=lab/paper`。说"not lab/db"可以跳过某个仓库。

创建协议的 agent 是协议的 **Steward**，只有它能修改协议。用 `/a2a-github:protocol` 修改协议、查看谁还没同步，或者把 Steward 移交给别人；移交不需要任何人同意。每次修改都会在这个 issue 里发通知，各成员重新运行一次 setup 即可同步，setup 会原地编辑自己的加入评论。不是 Steward 发出的修改算作冲突，成员会去问自己的用户，而不是照着执行。

### 原语

**`a2a watch [--once] [--interval SEC] [--backfill 7d] [--notify]`**：轮询仓库的四个数据流：issue 和 PR、issue 评论、PR 行内评论、issue 事件。对有变化的 PR，还会读取它的 review。每个数据流都带 `If-None-Match` 发条件请求，仓库没有动静时，每轮只花 4 个不计限额的 `304`。命中过滤规则的动态会追加写入 `.a2a/inbox.jsonl`。靠已见 id 和每个数据流的游标，重复运行或重启都不会产生重复条目。首次运行只记录已有的动态，一条都不投递；加 `--backfill` 时，才投递最近那段时间里的动态。`--once` 只跑一轮，适合 cron 和脚本；不加时常驻运行，并遵守 GitHub 返回的 `X-Poll-Interval`。

**`a2a inbox list [--unread] [--since ISO] [--type T[,T]] [--limit N]` · `inbox ack <id|owner/name#N>… | --all` · `inbox count [--unread]`**：每个条目一行，例如 `lab/paper#123  comment   alice  2026-10-17T17:40  能不能改成…`。`ack lab/paper#123` 把这个 thread 的所有条目标为已读；workspace 只观察一个仓库时，也可以只写 `#123`。`count` 只输出一个数字。已读状态和只追加的 inbox 分开存储，所以 ack 永远不会和 watcher 抢着写文件。

**`a2a fetch issue THREAD [--since ISO] [--comments-only] [--max-chars N]`** 和 **`a2a fetch pr THREAD [… | --files | --diff [PATH…]]`**：把一个 thread（例如 `lab/sim#7`）输出为紧凑的 Markdown，任何你的账号能读的仓库都可以。`--since` 只保留该时间之后的评论。`--max-chars` 保留表头和放得下的最新评论，并注明省略了多少条较早的评论。`fetch pr` 把评论和 review（含行内评论）按时间排在一起。`--files` 列出每个文件的增删行数，`--diff` 输出补丁，可以只看指定路径。

**`a2a notify [--force] [--sink stdout|file|command]`**：只要上次摘要之后有新的未读条目，就把一行摘要发到配置的通道，例如 `inbox: 3 unread — lab/paper#123 comment(alice), lab/sim#7 assigned, lab/paper#131 review(bob)`。`file` 通道追加写入文件。`command` 通道把这一行通过 stdin 交给任意程序，这就是把 a2a 接到任何 agent 或聊天工具上的扩展点。

**`a2a state get|set|delete|dump`**：扁平的 JSON 键值存储，用来记录你自己的状态，比如读到哪了、认领了哪些 thread。写入是原子的，并且加了锁，多个进程同时写也不会丢 key。`set k v` 时，`v` 能按 JSON 解析就存 JSON，否则存字符串；`--raw` 强制存字符串。

**`a2a sign [--as NAME]`**：从 stdin 读入正文，追加你的签名后输出，例如 `echo "On it." | a2a sign | gh issue comment 12 -F -`。当多个 agent 共用一个 GitHub 账号时（比如一个人同时开很多 agent），watcher 靠签名把动态归到正确的参与者名下，每个 agent 也靠它忽略自己发的消息。

所有命令都支持 `--json`，也都支持用 `--dir`（或环境变量 `A2A_DIR`）指定 workspace。两者都没给时，向上查找最近的 `.a2a/`。

### 配置

配置项说明见上方英文部分的 `config.toml` 示例。要点：
- `me` 是这个 workspace 代表谁。等于 `login` 时是独立账号模式；不等时是共享账号模式，此时靠签名识别身份。
- `repos` 列出要观察的一个或多个仓库。
- 各条过滤规则是 OR 关系，对每个仓库一视同仁；每个条目都会记录来自哪个仓库（`repo`）以及命中了哪些规则（`matched_rules`）。
- `ignore_self` 和 `exclude_authors` 是排除规则，优先级高于任何命中。

### 组合示例

**1. 常驻路由型**：一个路由 agent 关注所有新 thread，用标签把工作分派出去；执行 agent 只关注自己的标签。命令见上方英文部分的示例 1。路由策略全写在那段 shell 循环里，a2a 本身不做任何决定。

**2. 单兵型**：一个 agent 有自己的 workspace，由 cron 唤醒，并且只读它需要的那个 thread。命令见上方英文部分的示例 2，其中也给出了把摘要注入 Claude Code 的 `UserPromptSubmit` hook 配置。

**3. 纯人工查看型**：一个人在终端里关注仓库动态：常驻运行 `a2a watch --notify` 弹桌面通知，用 `a2a inbox list --unread` 查看新动态，用 `a2a fetch pr org/repo#17 --files` 快速浏览 PR。命令见上方英文部分的示例 3。

### 开发

开发和测试命令见上方英文部分。`scripts/dev-link.sh` 会把已安装的 Claude Code 插件用符号链接指向当前 checkout，修改无需重装即可生效；每次 `claude plugin update`、重装或升级版本号之后需要重新运行。设计说明和决策原因见 [CONTEXT.md](CONTEXT.md)、[docs/design.md](docs/design.md) 和 [docs/adr/](docs/adr/)。
