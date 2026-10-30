# Ready state-only：最小复现

本入口保留 Place–Release Factorial v2，执行版本为 `core-place-public-v4-ready1`，公开上下文固定 `public-context-v3`。每次 Agent 动作前固定预演200物理子步，验证支撑后恢复同一注册初态；任务20秒从恢复后起算。它改变了求解器历史，不能与旧Alpha分数池化。算法可以零收益或负收益。

## 获取轻量代码

```bash
git clone --filter=blob:none --sparse --branch feature/esl-reliability-replication https://github.com/ros-claw/PhysicalEvoBench.git
cd PhysicalEvoBench
git sparse-checkout set physicalevobench configs docs/core docs/reliability scripts tests
uv sync --locked --extra dev
uv run physicalevobench-core smoke
uv run pytest -q tests/test_esl_reliability.py tests/test_core.py tests/test_executable_skill.py
```

也可使用轻量源码包。包内不包含历史轨迹、PPO模型或原生依赖；CPU测试不算物理执行。无Git历史的源码包先 `git init && git add . && git commit -m 'Initialize Ready source'`，然后建立固定后端gitlink并按已有 `scripts/setup_arena.sh` 安装。

## 原生依赖与模型服务

按根README / `scripts/setup_arena.sh` 准备独立Arena原生venv，保持Arena `c7edf3a9d5d8276565208f72422f8f8a0806d6cf`、Lab gitlink `91a0906f93802eb859192dcb0bca879f891e92d6`。CPU环境与Arena环境分开。新状态技能路径不下载、不构建、不读取PPO actor或其checkpoint，也无需 `params/agent.yaml`。机器人/桌面等资产与原生依赖仍遵循各自许可。

参考模型参与者使用已安装并登录的Codex CLI；注册模型 `gpt-6.1-terra`，实际服务的effort/fingerprint未暴露，不声称固定权重。所有模型调用真实计费；货币费用无账单时为unknown。

## 最小完整接口 smoke（1次实际物理执行）

使用随包的 `configs/reliability/qualification.json`，内容哈希必须对应当前执行文件；不需要下载开发者旧实验目录。若修改了执行代码，先重新做下节资格，不能手改资格卡哈希。

```bash
uv run python -m physicalevobench.core.adapter_smoke --output /absolute/path/peb-ready-stdin-smoke-new --gpu 2
```

该入口经通用stdin adapter执行NoFeedback设计→产物冻结→新的原生进程执行一个预登记query条件。实际调用/usage、初态、Ready探测、任务轨迹和返回码全部留在输出目录。其意义是验证第二种协议接入，仍使用同一模型/CLI，不是第二个独立Agent框架。任务失败和接入失败分别报告。

通用provider协议：stdin一个公开JSON，stdout仅一行 `{"response":...,"usage":{"input_tokens":真实整数,"output_tokens":真实整数}}`。`response`遵守graph-v2参与者schema；缺usage报unknown，不补0。实现示例在 `physicalevobench/core/stdin_adapter.py`，原始CLI收据由stderr保留。测试期零模型调用，文本memory只作来源记录。

## 重做新执行资格（14回合）

```bash
uv run physicalevobench-core ready-qualify --output /absolute/path/peb-ready-qualification-new --gpu 0
uv run physicalevobench-core audit --run-dir /absolute/path/peb-ready-qualification-new
```

starter4 / strong4 / identical strong4 / force-open2。资格要求执行有效、强参考可达、明确负对照响应及无硬边界终止；不要求starter失败或学习方法赢。原始动作/子步与注册干预绑定，正常初态和同图重放差异均保留。

## 固定8-block主研究（至多768任务回合）

```bash
uv run physicalevobench-core replicate --qualification configs/reliability/qualification.json --output /absolute/path/peb-ready-replication-new --gpus 0,1,2,3
uv run physicalevobench-core audit --run-dir /absolute/path/peb-ready-replication-new
```

五方法：Frozen / NoFeedback / TemplateSearch-4 / Feedback / Deletion。TemplateSearch-4有明确人工专家候选先验；自然提前冻结的比较叫budget-cap comparison，实际tokens和计算可不相等。全部8个block全部产物冻结后才查询；每block16条件=2目标×2质量×4reset抽样。所有方法共享条件，方法/条件槽位顺序预登记轮换。默认学习每GPU一条lane、查询每GPU两条lane；可在开始前用 `--query-lanes-per-gpu 1` 降低并发，注册后不按分数更改。不因输赢停止/追加，不自动重试/换seed。

查询640回合，学习最多128回合；每个物理尝试另有1秒Ready预演成本。`INIT_INVALID`不产生任务成败，参与者非法/超预算与provider/基础设施故障分开。报告全分配及有效任务执行两种分母、全部block点、同图discordance、外层block分层区间、实际调用和物理成本。它仍是单一有限问题上的重复学习，不证明跨任务迁移或广泛自进化。

完整轨迹默认不下载。需要离线复算全研究时才使用可选原始证据包；固定局部样例只验证局部执行，不替代全研究审计。

目前验证范围以本轮报告为准；同机新目录不代表第二台机器或独立外部人已复现。新release和合并须另行审批，旧Alpha与PR #10保持原状态。
