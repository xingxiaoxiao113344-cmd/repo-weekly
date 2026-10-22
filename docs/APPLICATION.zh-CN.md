# 开源发布与 Codex for Open Source 申请准备

Repo Weekly 是一个刚起步的维护周报工具。当前版本读取 GitHub 活动、保存 JSON 快照并用确定性模板生成 Markdown；尚未接入 OpenAI API，也没有实现 AI 摘要。

新项目可以开始积累真实维护记录，但创建仓库本身不保证符合资助条件或获得批准。应按实际情况填写申请，不编造用户、星数、下载量、节省时间或生态影响。

## 先把项目用起来

1. 在本地安装，运行离线演示和测试，确认自己能解释报告中的时间区间与数据覆盖限制。
2. 在 GitHub 创建公开仓库，把代码、MIT 许可证、中英文 README 和 CI 一起提交。填写真实的仓库介绍，启用 Issues 和私密漏洞报告功能。
3. 用自己维护的仓库生成第一份真实周报。检查来源链接与统计，把报告中确实帮助你的地方记下来。
4. 邀请有对应需求的维护者试用，收集可核实的反馈、问题和改进建议。获得同意后再公开他人的评价或使用情况。
5. 修复实际问题，形成有说明的提交与版本记录。申请时引用已经发生的工作，并明确标注未来计划。

无需为了申请购买星数、制造下载量或填充空提交。早期项目可如实说明状态；是否录取由计划方审核。

## 申请前需要补齐的信息

- 你的公开 GitHub 用户名。
- 发布后的公开仓库 URL。
- 你在仓库中的真实角色：主要维护者或核心维护者，以及对应的维护工作。
- 已有的真实证据，例如自己的实际使用、其他维护者反馈、Issue 处理、版本发布、真实星数或下载量。没有的数据可以不声称。
- 如果申请 API 额度，提供你的 OpenAI Organization ID，并说明额度将支持什么具体工作。组织 ID 不需要写进本公开仓库。
- 如果考虑 Codex Security，说明相应维护权限与安全需求。它是可选申请方向，访问权限逐案审核。

当前工具不依赖 API 额度。若申请额度用于未来可选 AI 摘要，应明确写“计划开发”，说明用途与如何验证结果，不能把计划描述成已上线能力。

## 可修改的英文草稿

以下两段分别为 375 和 405 个英文字符（包含空格），适合按表单的 500 字符上限进一步修改。提交前必须核对自己的实际状态；获得真实数据后再补充证据。

**Why does this repository qualify?**

> Repo Weekly is an early-stage MIT-licensed Python CLI for GitHub maintainers. It turns issues, pull requests, and releases into reproducible Markdown reports, saves JSON snapshots, and flags incomplete coverage. I maintain the code, documentation, and tests. Adoption is not yet established; I am seeking feedback from maintainers and will report actual usage as it develops.

**How will you use API credits for your project?**

> The current release does not use the OpenAI API. I plan to add an optional, explicitly enabled AI summary of collected repository activity, with links to source items and clear separation from measured counts. Credits would support prototyping and evaluating summary accuracy on public or consented data, plus tests and maintainer feedback. Deterministic reports would remain available without API access.

这两段只陈述当前能力和计划，不声称项目已有广泛采用或必然具有生态重要性。如果你尚未承担文档、代码或测试维护，也应调整维护角色表述。

## 官方入口与规则

- [Codex for Open Source 官方说明](https://developers.openai.com/community/codex-for-oss)
- [官方申请表](https://openai.com/form/codex-for-oss/)
- [项目条款](https://learn.chatgpt.com/docs/codex-for-oss-terms)

官方说明面向核心维护者、运营广泛使用公开项目的维护者，也鼓励在生态中有重要作用但不完全符合常规条件的项目说明理由。申请滚动审核，Codex Security 逐案审核；请以提交时官网表单与条款为准。本文不承诺审批时间、最低指标或获批结果。
