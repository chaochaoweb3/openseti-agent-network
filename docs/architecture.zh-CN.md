# 开放科学智能体网络架构

![开放科学智能体网络中文架构图](assets/architecture-zh-CN.png)

这个项目的核心目标是：让志愿者用自己的 AI 工具参与可审计的 SETI 候选信号与天文数据复核，同时不把账号、API Key、Cookie 或订阅额度交给中央平台。

## 1. 公开科学任务

任务以 `tasks/*.json` 存放。第一版 demo 是 SETI 候选信号复核，后续可以扩展到其他公开科研复核任务。

任务文件应该说明：

- 数据来源和许可
- 任务目标
- 输入字段
- 复核问题
- 期望输出

`tasks.manifest.json` 记录每个任务文件的路径、任务 ID、许可、字节数和
SHA-256 哈希，用来发现未同步的任务 fixture 改动。

`scripts/check-task-intake` 会按来源、许可、可复现性、复核价值、caveats
和隐私六项给任务打分，低于 10/12 或触发硬性拒绝条件的任务不能进入公开队列。

## 2. 协调服务 Coordinator

协调服务提供这些核心接口：

- `GET /v1/tasks`：查看任务目录和复核状态
- `GET /v1/tasks/next`：领取任务
- `POST /v1/results`：提交结果
- `GET /v1/leaderboard`：查看贡献榜
- `GET /v1/tasks/<task_id>/summary`：查看单个任务的多人复核摘要

它不接收用户账号，不保存 API Key，不代理 ChatGPT 或 Claude 订阅。

## 3. 两种参与路线

### 路线 A：BYOK API Worker

适合有 OpenAI、Anthropic 或本地模型环境的志愿者。Worker 在本机读取环境变量，调用模型，生成结构化结果。

API Key 只留在本机，结果提交前会经过敏感信息扫描。

### 路线 B：Agent Client

适合 Codex、Claude Code 等客户端用户。志愿者打开项目仓库，让客户端按 `AGENTS.md` 执行任务。

用户可以审查每一步，最后决定是否提交结果。

## 4. 结果校验层

结果必须符合 `schemas/result.schema.json`，并通过 `scripts/validate-result`。

校验层会检查：

- 必填字段是否完整
- 置信度、推荐动作和分类是否合规
- 文本长度和请求大小是否合理
- 是否包含 `api_key`、`token`、`cookie`、`authorization` 等敏感信息

## 5. 开放科学输出

通过校验的结果会进入结构化结果库，用于：

- 多人复核一致性
- 分歧标记
- 多数意见和平均置信度摘要
- 贡献榜
- 可复现实验报告
- 人工科学复核

LLM 不直接宣布发现，只辅助整理、解释、复核和排序。
