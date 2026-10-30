# Executable-Skill Learning：独立运行与接入

当前产品入口不依赖 ROSClaw、旧 B1 目录或 PPO 历史数据。T0 是回归与物理 smoke 项；新 Place 学习题只有取得资格卡才可运行学习 pilot。旧双任务 Core 的失败记录在 [1027 报告](../implementation/CORE_BENCHMARK_实施报告_20261027.md)，不会阻塞单独 T0。

## 轻量源码

```bash
git clone --filter=blob:none --sparse --branch feature/executable-skill-learning https://github.com/ros-claw/PhysicalEvoBench.git
cd PhysicalEvoBench
git sparse-checkout init --cone
git sparse-checkout set physicalevobench tests configs/core configs/learning docs/core scripts
uv sync --locked --extra dev
uv run physicalevobench-core tasks
uv run physicalevobench-core smoke
uv run pytest -q tests/test_core.py tests/test_executable_skill.py
```

`smoke` 只检查 CPU 合约，物理回合为零。源码小包不含权重与历史轨迹。若使用无 Git 的源码压缩包，先建立本地 Git 提交，运行器才能冻结执行源码；资格核对使用代码内容 SHA，不要求开发者历史运行路径或旧 Git 对象。

## 真实物理 smoke

按根 README 和 `scripts/setup_arena.sh` 安装独立 Arena 原生环境，保持 Arena `c7edf3a9d5d8276565208f72422f8f8a0806d6cf` / Lab gitlink `91a0906f93802eb859192dcb0bca879f891e92d6`。不要共用 CPU venv。按 NVIDIA 原始条款单独获取模型，设置 `PHYSICALEVOBENCH_CHECKPOINT` 指向仓库外 `model_1999.pt`；同级需有 `params/agent.yaml`。模型 SHA 为 `babbbfd363f894443ffe494f26c5b6e0485fb35d4f5480c088295c23fc2a13aa`。

```bash
uv run physicalevobench-core physical-smoke --output /absolute/path/peb-smoke-new --gpu 2
```

该命令实际预留并执行 1 个 T0 物理回合，不调用模型、不读旧 B1、不依赖 T1。`result.json` 给出任务成功与控制步；物理启动错误与任务失败分开。使用干净、已提交源码和新输出目录；GPU 编号可选择，不停止其他用户任务。新目录物理复跑、全新原生安装与离线审计是三种不同验证。

## 资格与学习

已发出的轻量 `configs/learning/qualification.json` 若状态为 QUALIFIED，连同任务卡、程序与执行内容哈希即可复用，不需先下载开发原始数据。若此文件尚未生成，说明资格仍未完成，不能直接启动比较。

重做资格（新的明确工作，不覆盖既有成绩）：

```bash
uv run physicalevobench-core qualify --output /absolute/path/peb-qualification-new --program configs/learning/reference_aperture.json --gpu 2
```

实际学习与同模型对照：

```bash
uv run physicalevobench-core learn --output /absolute/path/peb-learning-new --qualification configs/learning/qualification.json --instances 2 --gpu 2
```

默认使用已安装并独立登录的 Codex CLI 参考 provider，模型固定 `gpt-6.1-terra`；临时会话、禁用内置工具，只传序列化公开上下文。支持其他 JSON provider：添加 `--provider '["/absolute/path/to/participant"]' --model YOUR_FIXED_MODEL`。入口从 stdin 读一个 JSON，stdout 输出一行 `{response,usage}`；`response` 遵循 `configs/learning/participant_schema.json`，usage 为真实 `input_tokens` / `output_tokens`，禁止估算为零。学习与无反馈组必须使用同一基础模型和计算上限。

程序通过 `program_json` 提交完整 graph-v2；run_trial 注册并执行实践，revise 仅修改候选，freeze 选择持久产物。模型自行选择句柄和修改，不要求先失败、不要求正收益。事件级反馈与少量周期状态进入上下文，全部原始高频轨迹留档。测试期仅运行冻结程序，文本 memory 是来源记录，不参与控制；不是完整在线 Agent harness。

每实例预留最多 8 Feedback +8 Search +5×4 query =36 回合，两实例最多72；允许早冻，实际费用单列。搜索是4候选共同2条件比较的有限提案族，不能代表全图空间最优搜索。所有实例全部冻结后才开始 query。无效提交保留为零分及有效性失败；基础设施错误单列，不悄悄从方法分母中删失败。

旧 P 接口仅用于历史协议复现：`physicalevobench-core run` 仍转交旧 `core.pilot`，其历史单次预注册限制不适用于新的 `learn`。请勿把饱和 P 题作为学习主成绩。

## 离线审计

```bash
uv run physicalevobench-core audit --run-dir /path/to/extracted/study
```

重新计算物理评分、程序命令、产物绑定、模型决策、支持/查询隔离和真实 reset 配对。原始轨迹包为可选下载；此命令不调用模型或模拟器，不产生新独立学习实例。


新目录执行已经导出的学习产物（不重新学习、不计正式 query）：

```bash
uv run physicalevobench-core physical-smoke --task place-settle --artifact /path/to/exported-artifact.json --seed 2026103030 --output /absolute/path/peb-artifact-smoke-new --gpu 2
```

先固定使用实例0的Feedback产物，不按其成绩挑选；若该方法未形成合法产物，如实记录无法复跑，不用另一个有利产物替换。该入口只需冻结JSON、轻量资格和正常任务配置，复核执行内容哈希，不依赖原学习目录。
