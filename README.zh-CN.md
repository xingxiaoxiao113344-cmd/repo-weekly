# Repo Weekly

[English](README.md)

把 GitHub 仓库近期的 Issue、Pull Request 和 Release 整理成 Markdown 维护周报。采集数据可以另存为 JSON，之后无需联网也能再次生成报告。

这是一个处于早期阶段的只读命令行工具。当前版本使用确定性模板，不调用 AI 模型或 OpenAI API，也不会发表评论、修改 Issue、合并 PR 或写入 GitHub 仓库。

## 安装与体验

需要 Python 3.11 或更新版本，无第三方运行时依赖。在项目目录中执行：

```sh
python -m pip install .
repo-weekly doctor --offline
repo-weekly demo --lang zh
```

演示使用明确虚构的数据。仓库、人物、活动和数字均为示例，不能作为真实用户或项目采用情况的证明。

Windows 用户也可以从源码目录直接运行，无需安装：

```powershell
.\run.ps1 demo --lang zh --output demo.md
.\run.ps1 report pallets/click --days 7 --lang zh --output weekly.md
```

可先查看[中文演示周报](examples/demo-report.zh.md)和[英文演示周报](examples/demo-report.en.md)。

## 生成周报

```sh
repo-weekly repo python/cpython
repo-weekly report python/cpython --days 7 --lang zh --output weekly.md
```

仓库参数支持 `OWNER/REPO` 或 GitHub 仓库 URL。`--lang en` 和 `--lang zh` 控制报告的标题与标签；Issue、PR 和 Release 的原标题保持原样，不会自动翻译。`--max-items` 限制每个列表展示的条目数，统计仍包含全部已采集记录。

工具读取 GitHub 公共 REST API。公开仓库可以不带令牌访问，但仍受 GitHub 访问规则和速率限制约束。如需令牌，将它设为环境变量 `GITHUB_TOKEN` 或 `GH_TOKEN`；前者优先。工具不会有意打印令牌。只授予读取目标仓库所需的权限。

## 保存快照与离线重现

指定结束时间，便于记录确切的报告区间：

```sh
repo-weekly collect python/cpython --days 7 --until 2026-10-22T00:00:00Z --output snapshot.json
repo-weekly report python/cpython --data snapshot.json --lang zh --output weekly.md
```

`collect` 联网采集数据；`report --data` 从本地快照生成报告，并沿用快照中的时间区间，因此不能再搭配 `--days` 或 `--until`。保留 JSON 文件可以追溯报告使用的数据。如果令牌可读取私有仓库，快照也可能包含非公开内容，分享前请检查文件。

默认拒绝覆盖已有输出文件。确实需要替换时，添加 `--force`：

```sh
repo-weekly report python/cpython --data snapshot.json --output weekly.md --force
```

## 时间区间与数据覆盖

所有报告区间使用 UTC，包含起点、不包含终点，即 `[since, until)`。`--days 7` 表示截至 `--until` 的七天；省略 `--until` 时使用当前时间。结束时间支持 UTC 日期或带时区的 ISO 时间戳。

报告汇总新建及关闭的 Issue、新建及合并的 PR、未合并即关闭的 PR、Release，以及活跃 Issue 和 PR。数字反映采集结果及报告区间，不代表完整的历史审计记录。

阅读时需要关注两项限制：

- GitHub 当前的 Issue 和 PR 记录无法还原每一次历史重新打开、此前的关闭操作或此前状态。事后采集较早区间，可能无法重建当时的全部活动。
- 每类来源都有分页上限，默认为 10 页，可用 `--max-pages` 调整。达到上限且仍有更多结果时，快照与报告会显著标记相关覆盖为不完整（partial），此时不能把数字视为完整统计。

使用统计前，请先读报告中的覆盖提示。增加页数可以获得更多记录，但不能恢复 API 未提供的历史状态。

采集或报告的数据不完整时，退出码为 **3**，仍会返回已获得的数据，在标准错误流输出提示，JSON 中的 `ok` 为 `true`。完整结果退出码为 0；参数或输入无效为 2；API 或文件错误为 1。

## 命令

| 命令 | 用途 |
| --- | --- |
| `repo-weekly doctor --offline` | 不联网，检查本地令牌配置与演示数据是否可用。 |
| `repo-weekly doctor --check-network` | 额外检查 GitHub 连通性。 |
| `repo-weekly repo OWNER/REPO` | 读取仓库资料。 |
| `repo-weekly repos OWNER --limit 20` | 列出指定用户或组织的仓库。 |
| `repo-weekly collect OWNER/REPO --days 7 --output snapshot.json` | 采集周报快照。 |
| `repo-weekly report OWNER/REPO --days 7 --lang zh --max-items 20` | 生成维护报告。 |
| `repo-weekly demo --lang zh --output demo.md` | 不联网生成虚构示例。 |
| `repo-weekly api /repos/OWNER/REPO` | 向 `api.github.com` 发出只读 GET 请求。 |

用 `repo-weekly --help` 或 `repo-weekly COMMAND --help` 查看参数。`api` 只能访问 GitHub API 主机，不能用作通用 HTTP 客户端。

## 脚本调用

全局 `--json` 可以放在子命令前或后：

```sh
repo-weekly --json doctor --offline
repo-weekly repo python/cpython --json
repo-weekly --json report python/cpython --data snapshot.json --lang zh
```

成功结果统一为 `{"ok": true, "data": ...}`；错误统一为 `{"ok": false, "error": {"code": ..., "message": ...}}`。报告结果包含原始快照、统计、Markdown 和输出信息。详见 [JSON 接口说明](docs/JSON.md)。

安装后如果终端找不到 `repo-weekly`，可以使用等价的 `python -m repo_weekly`，例如 `python -m repo_weekly demo --lang zh`。

## 参与开发

```sh
python -m pip install .
python -m unittest discover -s tests -v
```

自动测试使用本地 fixture 和模拟网络响应。CI 在 Ubuntu、Windows 以及 Python 3.11、3.12、3.13 上运行；测试不需要 GitHub 令牌或实时 API 请求。CI 安装项目时可能需要下载构建工具。

参与方式见 [CONTRIBUTING.md](CONTRIBUTING.md)，安全问题处理见 [SECURITY.md](SECURITY.md)，许可证为 [MIT](LICENSE)。

## 后续方向

未来可探索可选 AI 摘要、更完整的历史事件采集，以及真实维护者的使用反馈。这些功能当前尚未实现；现有报告功能无需 OpenAI 账号或 API 额度。

开源发布及 Codex for Open Source 申请准备见 [申请准备说明](docs/APPLICATION.zh-CN.md)。创建公开仓库不会自动获得资助或产品访问权限。
