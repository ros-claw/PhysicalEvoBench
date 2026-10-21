# PhysicalEvoBench v0.1 — Codex 工程实施任务书

**项目名称**：PhysicalEvoBench  
**英文副标题**：Benchmarking Self-Improving Embodied Agents through Physical Feedback  
**GitHub 组织**：https://github.com/ros-claw  
**目标仓库**：`ros-claw/PhysicalEvoBench`（如不存在，由 Codex 在有权限的账号下创建）  
**项目定位**：开放、中立、可复现的物理智能体自进化评测基准；ROSClaw 是首批被测系统，不是裁判。  
**首版版本**：v0.1.0-MVP  
**最优先交付物**：一次真正运行于 Isaac Lab-Arena 的物理交互—失败反馈—技能更新—冻结—独立复测闭环，及其可审计报告。  
**状态**：实施规格；本文中所有“预期表现”和样本量均为设计，不代表已经完成实验。

---

## 0. 给 Codex 的最高优先级指令

你是 PhysicalEvoBench 的首版工程负责人。请直接实施，不要止步于方案或 README。先确认运行机器、实际分支 API 和可用 GPU，再依次落地、测试、记录证据、提交代码。

**第一优先级是最小真实闭环，不是架构规模。** 必须让同一个真实物理仿真任务在相同协议下分别运行 Frozen Baseline 和 Feedback-Updated Skill，对一次真实物理失败提取证据，经训练/验证环节形成一个持久化的新 Skill 版本，在此前未用于更新的测试任务上比较结果。进化后效果可以提高、不变或降低；不得以固定的伪造分数、硬编码最优技能、假造失败日志来“完成验收”。

在第一版中：
- 一个机器人：**Franka Panda**；
- 一个物理任务：**Lift Object**；
- 一个物理扰动主轴：**对象质量变化**；第二扰动如摩擦或初始位姿，仅在可用、可复现时加入；
- 一个基础运动策略：**官方已训练的 RSL-RL policy**，冻结权重；
- 一个能被改进的技能产物：**受约束的控制策略参数或动作后处理器**；
- 一个自动更新器：**基于训练 Episode 反馈产生候选技能、经验证决定提升/回滚**；第一版允许确定性 Feedback Search Agent；
- 两个核心实验组：**Frozen Baseline** 与 **Feedback-Updating Agent**；同时预留 Retry/Raw History 组的标准接口；
- 三个完全隔离的数据分区：`train`、`validation`、`heldout_test`；
- 一套证据：每次 Episode 的真实反馈、参数修改 Diff、候选验证结果、固定版本、独立测试结果、成功率与成本对照；
- 一个公开 GitHub 仓库，英文 README、中文补充、清晰的运行命令、自动化 CPU 测试及 GPU 复现说明。

**先跑通，再扩展。禁止第一版同时开发多个机器人、VLA 微调、RL 重训练、云调度、大型 Dashboard、通用多 Agent 框架。**

---

## 1. 科学背景、研究问题与边界

### 1.1 为什么做

传统具身智能 Benchmark 往往报告机器人在一次固定训练后完成新任务的成功率。它们无法直接回答：Agent 经历物理失败后是否学到了东西；学到的知识是否成为可执行的能力；是否改善了下一次任务；是否具有迁移价值；以及改进是否增加了风险与成本。

**PhysicalEvoBench 的核心不是评测“完成任务”，而是评测“完成任务的能力如何随真实物理反馈改变”。**

### 1.2 相关工作

1. **Isaac Lab-Arena**：提供 Scene、Embodiment、Task 的可组合任务描述，GPU 物理仿真、策略评测、任务成败与子目标评估。它是**基础设施**，并非完整的 Agent 自进化评测协议。
2. **EmbodiedCLBench**（arXiv:2610.13021）：考察基础任务经验能否被重组后迁移到高级任务，强调持续学习与组合泛化；不等价于接触动力学闭环中的技能改进。
3. **EmbodiedEvo**（arXiv:2610.18867）：在 RoboDojo 中将交互反馈提炼成可复用代码 Skills 与 Lessons，并通过 Playground/Test 分离验证；是直接相关的重要方法工作。不要宣称“世界首个物理自进化 Benchmark”。
4. **LIBERO / RoboDojo**：后续可用于持续学习、长任务、不同机器人与任务扩展，但 MVP 不引入其整个运行时。

相关工作应写入 `docs/research/background.md`，区分「他人已实现」「PhysicalEvoBench 建议」「本项目实测」三类内容。

### 1.3 首版科学假设

H1：在**相同基础策略权重、相同训练交互预算、相同测试条件**下，经真实物理反馈更新的 Skill 能够被评测系统识别和独立测试。

H2：反馈驱动的候选 Skill 可能改善对质量变化的适应，但必须由实验结果决定，不预设改善。

H3：记录“失败证据 → 候选修改 → 验证 → 冻结 → 未见测试表现”的链条，比只报告最终成功率更能区分真正的技能更新与任务内重试。

请始终说明：v0.1 是 **Harness/Skill Adaptation Track 的 MVP**，不是“模型权重自主学习”，也不是已经证明了通用 Physical Self-Evolution。后续版再增加 Memory、Lessons、长期遗忘、跨任务迁移与元学习。

---

## 2. 必须核对并锁定的上游依赖

### 2.1 Isaac Lab-Arena

官方仓库：https://github.com/isaac-sim/IsaacLab-Arena

首选固定分支 `release/0.3.1`；调研时核对的 Git Commit：
`c7edf3a9d5d8276565208f72422f8f8a0806d6cf`

请在实施开始时重新核对 Git 对象、submodule、`uv.lock` 和上游 README。不要使用未固定的 `main` 作为正式实验依赖；如果必须升级，需要单独提交升级 PR，并完整重跑基线。

推荐将上游作为**只读 Git submodule** 保存在：
`external/IsaacLab-Arena/`

创建之后应执行：

```bash
git submodule add https://github.com/isaac-sim/IsaacLab-Arena.git external/IsaacLab-Arena
git -C external/IsaacLab-Arena checkout c7edf3a9d5d8276565208f72422f8f8a0806d6cf
git submodule update --init --recursive
git status
```

**不要在上游目录里直接打补丁。** 自定义 Task、Policy、Variation、Runner 均在本项目包内实现。确有 upstream bug 时先给本项目写明确的兼容适配层；必要时另开上游 Issue/PR。

**特别注意版本漂移**：`main` 上的某些环境录制/回放 API 不一定存在于锁定的 `release/0.3.1` 中。先以固定 Commit 实际源码和 `--help`、`--list_variations` 输出验证；不要把开发分支示例照抄后假设有效。

### 2.2 官方模型（仅下载，不随项目发布）

Hugging Face：
https://huggingface.co/nvidia/Arena-Franka-Lift-Object-RL-Task

官方提供 `model_1999.pt` 和 `params/agent.yaml`。推荐按上游示例下载：

```bash
hf download nvidia/Arena-Franka-Lift-Object-RL-Task \
  --local-dir "$HOME/models/physicalevobench/franka_lift"
```

跑通后**记录实际 Hugging Face Revision 与 `sha256sum`**，写入 `provenance.json`；后续使用固定 Revision 和内容哈希，不只写“latest”。

**法律与许可硬约束**：模型卡声明该权重仅限非商业使用，并由 NVIDIA 单独许可约束。本项目不能因为代码选 Apache-2.0 就将权重重新授权。仓库不得提交模型文件，不得暗示预训练权重用于商业场景也可自由使用。需要支持使用者自行接受模型许可并独立下载。项目代码与自建资产的许可单独核对。

### 2.3 最小验证命令

在符合要求的 RTX Linux 环境上，按固定分支官方安装步骤创建环境。首先执行上游官方 Zero-action smoke：

```bash
python isaaclab_arena/evaluation/policy_runner.py \
  --policy_type zero_action --num_steps 20 cube_goal_pose
```

然后直接执行官方 RSL-RL checkpoint：

```bash
python isaaclab_arena/evaluation/policy_runner.py \
  --policy_type rsl_rl \
  --num_episodes 10 \
  --checkpoint_path "$HOME/models/physicalevobench/franka_lift/model_1999.pt" \
  lift_object
```

上述命令在 Arena 仓库工作目录及其 Python 环境中执行。**切勿把本文所引命令的成功当作我们已经运行成功**；Codex 必须在目标机器真机执行并保存终端日志、软件/驱动/GPU 信息、观察到的 Episode 数与真实成绩。

### 2.4 硬件与运行约束

优先检查 Linux RTX A6000 工作站（或其他符合当前 Isaac Sim 要求的 RTX GPU），使用 `nvidia-smi`、驱动、CPU/RAM/显存、磁盘空间检测。H800 不应作为默认 Isaac Sim 图形物理仿真主机。H800 可在后续给远程 LLM/训练服务提供推理计算。首版**不以 H800、ROS 2 或 ROSClaw 安装作为启动前提**。

机器不具备 Isaac Sim 条件时，仍可开发 CPU schema 测试和 mock runner，但**不得声称已完成物理 MVP**；必须记录明确的 GPU BLOCKER 与恢复步骤。

---

## 3. 首版任务定义：PEB-Lift-Mass-v0

### 3.1 任务

Franka Panda 在 Isaac Lab-Arena `lift_object` 环境中，根据给定目标位姿抓取并提升桌面物体。底层使用 PhysX，控制和成功判据沿用实际锁定版本的官方任务实现。

与上游示例保持相同控制时间步长和动作接口。禁止为了获得更好的结果修改正式成功判据、超时时限或测试数据。

### 3.2 物理扰动

MVP 只选一个确凿且有物理意义的主扰动：**抓取物体质量**。已在 `release/0.3.1` 代码中核对存在：
`isaaclab_arena/variations/object_mass_variation.py`
（`ObjectMassVariation`，运行时按环境重置采样，并相应更新惯量）。

请先运行：

```bash
python isaaclab_arena/evaluation/policy_runner.py \
  --policy_type zero_action \
  --list_variations \
  lift_object
```

核对真实可用的变体命名与 Hydra 参数路径。若 `dex_cube.mass` 可用，再配置采样器；必须读取结果核对物理质量已实际改变，并非只修改 YAML 标签。

**难度校准**：先对正常的、未人为削弱的预训练策略进行质量敏感性扫描；选出基线并非全胜、也并非全败、且不会产生非物理仿真故障的范围。记录扫描数据，再在正式评测前冻结任务分布。不得看 `heldout_test` 成绩后修改区间。

推荐配置示意（**仅是候选区间，不是验证过的有效区间**）：

```yaml
benchmark_id: PEB-Lift-Mass-v0
embodiment: franka_joint_pos
arena_task: lift_object
physics_backend: physx
observation_track: state_observation
variation:
  field: object_mass_kg
  candidate_range_kg: [0.05, 0.40]
  distribution: calibrated_by_pilot
success:
  source: upstream_lift_object_completion
  require_consecutive_steps: as_upstream
episode:
  timeout_s: 5.0
```

正式分区里的质量值、目标位姿、初始化随机种子必须有**可复现的条件清单**。若固定的 Arena 分支没有合适的逐 Episode 完整回放 API，就在本项目可信执行器中生成 manifest，使用当前版本允许的 Variation/Event/Command 配置按条件重放。不要为图省事把所有候选策略放在不同随机条件上比较。

### 3.3 训练 / 验证 / 测试隔离

- `train`：更新器可查看许可的观测、动作记录、训练失败标签；可多轮访问，所有物理 Episode 全部计费。
- `validation`：用于在候选 Skill 与当前 Skill 之间做 promotion gate；不得读取隐藏物理参数。任何候选访问都计入验证预算。
- `heldout_test`：只能在 Skill 冻结后运行；独立条件和随机种子，结果**永不返回更新器**；测后不再为本轮调整候选。

首版完全开源时，这只是 **held-out evaluation**，而不是真正保密的线上 hidden test。不能将一个所有人都能读取的公开测试 manifest 宣称成不可作弊的隐藏排行榜。长期版本再增加评测服务器与保密测试集。

推荐 MVP 最小预算：每组 8 个 train Episode、4–8 个 validation Episode、16–32 个 held-out test Episode；先完成 1 个端到端种子。若要在 README 中写“性能确有改善”，至少增加独立种子、配对评估和区间估计，例如 5 个独立随机种子 × 每种 32 个测试 Episode（实际数量以方差和算力为准）。单轮 smoke 只证明流程可执行，不能证明显著提升。

---

## 4. 精确定义什么可以“进化”

### 4.1 固定基础策略，更新可执行 Skill

首版冻结 `model_1999.pt`，开发 `SkillAdaptedPolicy`，在其输出动作与物理仿真 `env.step()` 之间插入有版本号的 `SkillSpec`。

动作修改必须：
- 明确记录对应机器人的 Joint/Action 名称及映射，**不硬编码未核实的最后一个 tensor 下标**；
- 遵守动作区间、机器人关节极限及时序限制；
- `SkillSpec` 以 JSON/YAML 显式保存、类型校验、SHA256 摘要；
- 每个 Episode 必须记录加载的是哪一个 `skill_hash`；
- 模型权重保持哈希不变，避免把模型更新冒充 Skill 更新。

建议 v0.1 的候选参数维度为（最终以真实动作接口为准）：

```yaml
skill_version: 0
base_checkpoint_sha256: "<verified sha256>"
controller:
  arm_action_gain: 1.0
  gripper_switch_bias: 0.0
  gripper_close_hold_steps: 0
constraints:
  arm_gain_min: 0.85
  arm_gain_max: 1.15
  max_abs_gripper_switch_bias: 0.25
  max_close_hold_steps: 5
```

其中 `gripper_switch_bias` 与 `gripper_close_hold_steps` 要按 `BinaryJointPositionActionCfg` 的真实符号、饱和及控制语义实现；如果该参数不会在仿真产生可测量作用，就从搜索空间移除，不得保留成“名义参数”。

可执行 `Skill` 并不要求 LLM 每次生成代码；它至少必须是一个**会真正改变机器人动作的、可复用的受约束控制产物**。

### 4.2 自动更新器

先实现 `FeedbackSearchAgent`（确定性、透明、可复现），输入仅为训练阶段受允许的信息，例如：

```json
{
  "episode_id": "train-0007",
  "success": false,
  "failure_type": "failed_to_lift",
  "max_lift_height_m": 0.025,
  "action_statistics": {
    "gripper_close_fraction": 0.38,
    "action_saturation_fraction": 0.02
  },
  "remaining_episode_budget": 5
}
```

这些仅为**输出 schema 示意**，不是实验数据；字段只有在能够用真实日志计算时才能出现。诊断标签必须说明其来源、规则与置信度，不能将物理真值或人工答案伪装成 Agent 推理。

更新器必须：
1. 读取并总结训练失败；
2. 提出一个或多个参数化候选 `SkillSpec`，写明假设；
3. 在训练预算范围内对候选执行真实物理 Episode；
4. 通过独立 validation 判断是否 promotion；
5. 未达到门槛则 rollback 或维持原版本；
6. 产出完整候选日志及 `skill_v0 → skill_v1` Diff。

优先简单的一维/二维受约束候选搜索或失败类型驱动的候选生成，不要首版写一个通用强化学习框架。**禁止预先把测试最优参数硬编码进去**。

保留开放接口：

```python
class EvolutionAgent(Protocol):
    def propose_update(
        self,
        current_skill: SkillSpec,
        training_feedback: list[EpisodeFeedback],
        remaining_budget: Budget,
    ) -> SkillProposal: ...
```

v0.2 可通过独立 Agent Adapter 加入 Codex、ROSClaw、Hermes、OpenClaw 等；但不要让任何 Agent 获得评测器环境对象、直接修改任务规则或读取 held-out 数据。

### 4.3 公平对照

至少实施：

**B0 Frozen**：相同预训练基础策略、相同初始 Skill；不读取跨 Episode 反馈，也不能在测试期间更新。

**B1 Feedback Search**：同一初始模型和 Skill，训练时允许利用真实反馈更新，最终冻结版本参加同一套测试。

建议加一个廉价的 **B2 Random/Budget-Matched Search**：在相同候选数量、相同训练交互与 validation 预算下，随机提议技能，作为排除“仅仅搜索了更多参数就变强”的对照。只有完成该组后，才有资格声称反馈诊断比盲目搜索更有效。

注意区分两个比较：
- Frozen vs Updated：验证系统有无实测的“更新收益”；
- Budget-Matched Random vs Feedback Search：验证“基于失败的学习机制”是否产生额外价值。

---

## 5. 严格的观测与评测权限边界

Arena 的 `PolicyBase.get_action(env, observation)` 允许 Policy 接收环境对象；这个接口**不能原样暴露给待测 Agent**。

首版必须采取可信 `ArenaWorker` + 受限 `AgentAdapter`：
- **ArenaWorker / Evaluator**：独占 `env`、随机种子、质量真值、实际任务判定、episode split 和测试成绩；
- **Frozen RSL-RL 基础策略**：允许读取官方 `policy + task_obs` 训练兼容状态观测；属于 **state-observation track**。官方任务观测包含目标/物体位置等状态信息，**不应宣称纯视觉感知或完全无特权 state**；
- **EvolutionAgent**：只能拿到白名单 `EpisodeFeedback`、允许的统计信息、Skill 版本及剩余预算；不能 `import` 评测器内部模块、不能读取物理 mass 真值或测试文件；
- **Testing**：更新器进程结束或权限关闭，冻结物件的哈希保持不变，只允许执行与评分。

技术上建议区分两个 OS 进程或最小 RPC / 文件消息协议。即使第一版运行在同一物理机器上，至少确保 `AgentAdapter` 只获得序列化白名单数据；不能将 `env` Python 对象直接交给 Codex 运行时或模型工具。

不得在测试集使用真实物理质量值自适应控制，除非未来明确开设 privileged track。

---

## 6. 系统架构与仓库目录

核心流程：

```text
Experiment Manifest / Split Registry
                |
                v
Trusted Arena Worker (Isaac Lab-Arena + PhysX)
                | authorized observations / physical feedback
                v
       Evolution Agent
                | candidate SkillSpec
                v
      Skill Safety Validator
                | approved candidate
                v
        Training Rollouts
                |
                v
       Validation / Promotion
            |           |
        promote       rollback
            |
            v
      Immutable Skill Snapshot
            |
            v
     Independent Heldout Test
            |
            v
   Metrics + Evidence + Report
```

推荐仓库：

```text
PhysicalEvoBench/
├── README.md
├── README.zh-CN.md
├── LICENSE
├── NOTICE.md
├── CITATION.cff
├── .gitignore
├── .gitmodules
├── pyproject.toml
├── Makefile
├── external/
│   └── IsaacLab-Arena/                 # pinned, unmodified submodule
├── physicalevobench/
│   ├── __init__.py
│   ├── cli.py                          # doctor, smoke, run, evaluate, report
│   ├── config.py                       # typed versioned schemas
│   ├── tasks/
│   │   └── lift_mass.py                # task definition / condition builder
│   ├── adapters/
│   │   ├── arena_worker.py             # trusted Arena integration
│   │   └── rsl_rl_skill_policy.py      # base policy + skill modifier
│   ├── protocols/
│   │   ├── agent.py                    # agent contract
│   │   ├── feedback.py                 # observation/feedback allowlist
│   │   └── skill.py                    # immutable SkillSpec
│   ├── agents/
│   │   ├── frozen.py
│   │   ├── feedback_search.py
│   │   └── budget_random.py
│   ├── evaluation/
│   │   ├── manifests.py                # deterministic train/val/test conditions
│   │   ├── gate.py                     # promotion/rollback
│   │   ├── evaluator.py
│   │   └── metrics.py
│   └── reporting/
│       └── generate.py                 # HTML + plots + evidence manifest
├── configs/
│   ├── lift_mass_v0.yaml
│   ├── smoke.yaml
│   └── mvp.yaml
├── scripts/
│   ├── doctor.sh
│   ├── install.sh
│   ├── download_checkpoint.sh
│   └── run_mvp.sh
├── tests/
│   ├── test_skill_validation.py
│   ├── test_split_isolation.py
│   ├── test_feedback_permissions.py
│   ├── test_gate.py
│   ├── test_metrics.py
│   ├── test_budget_accounting.py
│   └── test_dry_run.py
├── docs/
│   ├── research/background.md
│   ├── architecture.md
│   ├── benchmark_protocol.md
│   ├── upstream_compatibility.md
│   └── reproducibility.md
├── examples/
│   └── report_sample/                # 只放明确标记的合成格式演示数据
└── runs/                              # gitignored, real experiment artifacts
```

如果选择更简单的代码结构可合理调整，但 `Agent / Arena / Evaluator` 权限边界、数据格式和运行命令必须稳定。

---

## 7. 数据协议：保证每次能力变化可审计

每次正式实验对应独立 `run_id`，绝不覆盖旧结果：

```text
runs/<run_id>/
├── provenance.json                 # git SHA, arena SHA, Isaac versions, GPU, checkpoint SHA
├── config_resolved.yaml            # resolved immutable config
├── splits/
│   ├── train.jsonl
│   ├── validation.jsonl
│   └── heldout_test.jsonl          # evaluator only
├── baseline/
│   ├── episodes.jsonl
│   └── skill_v0.json
├── evolution/
│   ├── training_episodes.jsonl
│   ├── proposals.jsonl
│   ├── validation_episodes.jsonl
│   ├── promotion_decisions.jsonl
│   ├── skill_v1.json
│   └── skill_diff.json
├── test/
│   ├── baseline_episodes.jsonl
│   ├── updated_episodes.jsonl
│   └── paired_results.jsonl
├── videos/                         # optional真实渲染画面
├── report/
│   ├── index.html
│   ├── metrics.json
│   ├── learning_curve.png
│   └── comparison.png
└── audit.json                       # missing data / taint / completeness checks
```

每条 Episode 至少有：

```json
{
  "schema_version": "0.1",
  "run_id": "...",
  "episode_id": "...",
  "split": "train",
  "environment_id": "PEB-Lift-Mass-v0",
  "condition_id": "...",
  "seed": 42,
  "agent_id": "feedback_search",
  "base_checkpoint_sha256": "...",
  "skill_sha256": "...",
  "success": false,
  "termination_reason": "...",
  "failure_type": "failed_to_lift",
  "steps": 250,
  "simulated_seconds": 5.0,
  "unsafe_action_count": 0,
  "observation_artifact": "...",
  "trace_artifact": "...",
  "video_artifact": null
}
```

此例是**schema，不是实际结果**。真实数据必须从真实物理执行产生。`unsafe_action_count=0` 只表示具体规则检查为零，不代表“零碰撞”；没有部署碰撞传感与事件检测的字段应写 `null/not_measured`，不能偷偷填 0。

可信内部 `condition.json` 可包含物理质量、目标值、初始位姿等，但这些真值字段**不得进入 Agent 的 feedback payload**。Manifest 可有公开开发分区及只供 evaluator 读取的本地密封测试分区；v0.1 不声称做到线上反作弊。

每次候选更新必须关联训练 Episode ID 与 validation 结果；每次测试必须有 `frozen_skill_sha256`。若缺少链条，报告标记为 `INCOMPLETE`，不允许纳入正式比较。

---

## 8. 统计指标与失败处理

首版主指标：

```text
P_frozen = frozen policy 在 heldout_test 的成功数 / 试验数
P_updated = frozen后更新 Skill 的 heldout_test 成功数 / 试验数
EvolutionGain = P_updated - P_frozen  （百分点）
```

次指标：
- `training_episode_budget`：所有用于学习的真实 Episode，包括提出候选所使用的试验；
- `validation_episode_budget`：所有用于提升/回滚判断的 Episode；
- `success_gain_per_100_episodes`（注明分母及计算规则）；
- `fallback_count` / `promotion_count`；
- `unsafe_action_count`、`joint_limit_violation_count`；
- `candidate_count`、`skill_diff`、`model_token_usage`（无模型则 0）；
- 最终 `learned_skill_sha256`；
- 对照组测试的 `condition_id` 覆盖和一致性。

**配对统计**：Frozen 和 Updated 必须在同一组 `condition_id` 上执行；计算逐条件二元成功差和配对均值差。对多随机种子/条件组合可报告 bootstrap 置信区间，同时呈现原始分子/分母，不允许只画没有误差范围的漂亮曲线。

**异常规则**：
- 仿真崩溃、模型文件缺失、动作 NaN、Episode 日志损坏，属于执行失败，不可记为机器人任务失败；必须区分 `INFRA_FAILURE` 与 `TASK_FAILURE`；
- 超预算自动终止更新，不能静默补跑；
- validation 未通过可以回滚，不得为满足 KPI 强行 promotion；
- 没有发现改进也是**有效的科研结果**，报告客观说明失败发生在哪一步。

**避免人为制造假进化**：可以设置“故意有问题的参数”作为测试代码是否能恢复的**工程自检**，但它必须位于 `tests/` 或 `examples/diagnostic/`，不能混入正式任务，不可将恢复到原参数的行为报告为真正的自进化科学发现。

---

## 9. 具体实施阶段和 Gate

### P0 — GitHub、环境与上游复现

实施：
1. 检查 `ros-claw/PhysicalEvoBench` 是否存在；若不存在且 GitHub 身份有组织创建权限，用 `gh repo create ros-claw/PhysicalEvoBench --public` 创建。**不要擅自改为个人仓库或其他组织**。创建失败则清楚报告权限问题，先把代码保存在本地可提交工作区。
2. 创建 Apache-2.0 项目代码许可、NOTICE、贡献指南、英文 README、中文 README、CITATION.cff、`.gitignore`，强调模型许可不同。
3. 加入并锁定 Arena submodule；记录环境/驱动/GPU/依赖、启动日志。
4. 运行 Zero-action smoke 与官方原始 RSL-RL `lift_object` checkpoint。
5. 保存真实 baseline Episode、真实轨迹与控制台日志；确认成功判据确实来自 Arena。
6. 增加 `physicalevobench doctor`，输出结构化环境检查结果。

**Gate P0**：官方 `lift_object` 真正在 PhysX 内完成至少一个非零动作的 Episode；不是只启动 GUI、只调用 dummy、或只打开 USD 场景。未完成 P0 不准进入“自进化已完成”的宣称。

### P1 — 可控物理任务和正常基线

实施：
1. 读取 `ObjectMassVariation`、Franka action 配置、RSL-RL 策略加载实现；列出官方 API、动作维度、映射和物理质量应用路径。
2. 生成可复现 condition manifests，验证不同质量区间的实际质量与物体惯量已生效；
3. 抽样运行**正常预训练策略**，寻找可学的物理扰动难度；
4. 创建 `SkillSpec` 和 `SkillAdaptedPolicy`，证明候选参数会真实改变控制动作，但绝不破坏原始 checkpoint；
5. 编写 Frozen 测试执行器及 Episode logger。

**Gate P1**：同一 `condition_id` 重放时配置与主要初始状态匹配；baseline 统计与每个 Episode 视频/日志可追溯。对不可完全确定的 GPU 物理误差写入 reproducibility 文档。

### P2 — 一次完整技能进化

实施：
1. 运行训练 Episode，至少捕获一个实际任务失败；
2. 从训练反馈生成候选 Skill，显示明确的候选修改理由；
3. 对候选做 schema/safety 检查；
4. 在允许的训练与验证预算内真正执行候选控制参数；
5. 使用 validation 比较候选与当前技能；按预先固定规则 promotion 或 rollback；
6. 生成 `skill_v0.json`、`skill_v1.json`（如有提升）及 `skill_diff.json`；
7. 冻结更新器，记录不可变技能 hash。

**Gate P2**：从训练失败到候选再到验证存在可核查、可重放的实际物理证据。不要求“必须胜出”，但要求修复逻辑确实更新了待执行动作，并由验证器独立决定是否保留。若被回滚，报告应明确列出原因。

### P3 — 真正独立测试与报告

实施：
1. 固定测试清单，选择与训练/验证不同的 `condition_id`；
2. 冻结基线与最终技能；同一条件分别执行 Frozen / Updated；
3. 严格阻断测试结果返回训练 Agent；
4. 计算主指标、资源成本、异常数、CI 与安全数据完整性；
5. 生成 HTML 报告、JSON 原始成绩、可复现的 CLI 命令、可追溯 Episode；
6. 从真实渲染结果剪辑一段 before/after 演示；不得把动画或示意画面冒充物理执行。

**Gate P3**：任何人能从一套真实的可重放 Episode 与版本数据，回答“改变了什么、为什么变、在什么条件下有效/无效”。报告对负收益和未测指标同样诚实。

### P4 — 开源收稿与验收

实施：
1. `pytest` / `ruff` / `mypy`（按实际选型）通过；GitHub Actions 只跑无需 Isaac Sim 的 CPU tests，GPU smoke 通过手动或自托管 runner 运行。
2. README 第一屏说明：问题是什么、怎样测量、怎样复现、当前支持什么、哪些还不支持。
3. 增加 Quickstart（doctor、模型下载、smoke、mvp run、生成报告）及复现环境说明。
4. 用独立的新工作目录做一次 fresh clone + submodule + 安装验证。
5. 代码经 PR 提交，验收通过后合并到 `main`；若有权限完成发布，打 `v0.1.0` tag，附 release notes 和已完成/未完成事项。
6. 发布前检查没有上传模型权重、私密 API Key、过大视频或未经授权的 NVIDIA/第三方资产。

**Gate P4**：README 的运行命令与实际操作一致；不是只有一个漂亮仓库首页而真实闭环尚未运行。

---

## 10. 标准 CLI：必须实现并验证

最终统一为以下命令（由本项目自行实现，不是假称已有上游 CLI）：

```bash
# 一、检查环境与模型
physicalevobench doctor \
  --config configs/lift_mass_v0.yaml

# 二、运行最小真实物理 smoke
physicalevobench smoke \
  --config configs/smoke.yaml \
  --gpu 0

# 三、一键完成 Frozen 与 Feedback Search 的真实训练/测试
physicalevobench run \
  --config configs/mvp.yaml \
  --agents frozen,feedback_search \
  --gpu 0 \
  --run-dir runs/mvp_local

# 四、独立校验结果完整性与测试集隔离
physicalevobench audit \
  --run-dir runs/mvp_local

# 五、从真实结果生成静态 HTML 报告
physicalevobench report \
  --run-dir runs/mvp_local
```

可以通过 `python -m physicalevobench` 提供同等入口；把 `physicalevobench` 注册为 `pyproject.toml [project.scripts]` console script。`scripts/run_mvp.sh` 必须调用这一实现，不允许另写一个仅用于演示的假流程。

`run` 需要支持 resume，resume 时验证原始配置/manifest/skill checkpoint hash 与 run_id 一致，避免重复计数、污染预算和覆盖结果。最初版本可先显式拒绝不安全 resume，而不假装支持。

---

## 11. 测试矩阵

**CPU CI（无需 Isaac Sim）**：
- Skill JSON schema 和 hash 稳定性；
- 非法 gain、NaN/Inf、越界动作被拒；
- train/validation/test 条件 ID 不重复；
- Agent 不得读取 evaluator-only mass 字段；
- Test split 的反馈不能调用 `propose_update`；
- Gate 条件预先固定，回滚可正确恢复旧 Skill；
- 预算溢出必须失败，不得暗中多跑；
- 合成输入只用于验证汇总计算，必须明确 `synthetic_fixture=true`；
- 报告对缺失危险传感器字段显示 `not_measured`；
- 相同条件的配对评测合并正确。

**GPU Integration（必须在 Isaac Sim 机器上真实执行）**：
- upstream zero-action；
- upstream checkpoint `lift_object`；
- mass variation 真正在仿真中改变；
- Skill 改动真正在 `env.step` 输入动作中出现；
- 一次完整 baseline Episode；
- 失败/诊断/候选/validation/rollback 或 promotion；
- 独立 test；
- 报告文件与可追溯视频；
- 重新克隆环境后复现。

---

## 12. MVP 最低验收清单

以下条件**全部满足**才算完成 `v0.1.0-MVP`：

- [ ] `ros-claw/PhysicalEvoBench` 公开仓库可访问；若因授权不能创建，明确列为尚未完成，不得谎称开源发布；
- [ ] 精确锁定 Arena Git Commit、Python 依赖和模型 Revision + SHA；
- [ ] 在合适 GPU 上真正运行 Isaac Lab-Arena PhysX `lift_object`，完整打印成功/失败/计数；
- [ ] 运行正常预训练基线（不是故意损坏过的策略）；
- [ ] 至少一组可核实的物理质量扰动；
- [ ] 至少一条真实失败 Episode 及其非伪造物理反馈；
- [ ] 至少一次自动生成的候选 Skill 修改，控制动作实质发生变化；
- [ ] validation 决定 promotion 或 rollback，结果与动作证据可核查；
- [ ] 至少 16 个此前未用于训练与 validation 的测试条件/试验；Frozen 和 Updated 使用同一批条件；
- [ ] 已生成真实结果的 `metrics.json`、`episodes.jsonl`、`skill_diff`、`provenance`、`audit`、`report/index.html`；
- [ ] 至少一段真实仿真视频，清楚展示动作/失败/技能更新前后表现，非脚本动画；
- [ ] README Quickstart 和 CPU CI 可在新环境验证；
- [ ] `README` 明确：“首版证明评测协议跑通，不自动声称算法优越性或通用自进化”。

实验可能显示改进、无改进或退化。只有**真实闭环完整**才有资格宣布 MVP 成功；只有在足够独立实验和公平对照下取得稳定正收益，才可以进一步宣称方法有效。

---

## 13. Codex 最终必须提交的实施报告

文件：`docs/implementation/MVP_IMPLEMENTATION_REPORT.md`，必须包含：

1. GitHub 仓库 URL、默认分支、最新 Commit、PR、是否合并、CI 状态；
2. 环境信息：GPU / NVIDIA 驱动 / CUDA / Isaac Sim / Isaac Lab / Arena / checkpoint SHA；
3. 每个 P0–P4 Gate 的 PASS / FAIL / BLOCKED，含证据路径；
4. 真实运行过的命令、退出码、控制台日志路径；
5. 物理任务设计、实际质量条件分布、训练/测试隔离策略；
6. 实际反馈内容、每个候选 Skill Diff、版本、验证结果；
7. Frozen / Updated / Budget-Matched 对照表，样本量、成功数、成功率、Evolution Gain、成本与统计区间；
8. 一段完整的代表性失败—更新—验证—复测案例，附视频与 Episode ID；
9. 缺失功能和已知风险：物理随机性、privileged state、权重许可、有限样本、无真实 hidden server；
10. 明确的结论：**技术链条是否真正跑通？有没有正向自进化证据？还有什么尚不能证明？**
11. 下一阶段不超过三项最高优先级建议，避免把计划扩张为无法交付的大工程。

---

## 14. 首版之后的研究路线（不纳入 MVP 验收）

**v0.2 — Agent-Harness Track**：开放 ROSClaw、Codex、Hermes 等适配器，比较 Frozen / Retry / Raw History / Memory / Skills，在相同模型和交互预算下测量经验编码与可执行技能进化。

**v0.3 — Continual Transfer Track**：从单物体抓取扩展至新物体、新物理属性、复合长任务，并增加旧任务 Retention、失败知识迁移与技能删减的因果消融。

**v0.4 — Safe Self-Improvement / Policy Update**：引入系统性安全门控、多轮技能升级、策略微调赛道、真正不可访问的评测服务器；允许跨机器人但不同硬件赛道分榜。

**长期研究问题**：Agent 是否能从物理失败中改进自己的学习过程，而不是只记住某一次试验的正确参数？

---

## 15. 官方参考入口（Codex 以实际固定源码优先）

- Arena Repo：https://github.com/isaac-sim/IsaacLab-Arena
- Arena release/0.3.1 文档：https://isaac-sim.github.io/IsaacLab-Arena/release/0.3.1/
- Franka Lift 工作流：https://isaac-sim.github.io/IsaacLab-Arena/release/0.3.1/pages/example_workflows/reinforcement_learning/index.html
- Franka 预训练评测：https://isaac-sim.github.io/IsaacLab-Arena/release/0.3.1/pages/example_workflows/reinforcement_learning/step_3_evaluation.html
- 在自己仓库集成 Arena：https://isaac-sim.github.io/IsaacLab-Arena/release/0.3.1/pages/arena_in_your_repo/external_installation.html
- Mass Variation 源码：`isaaclab_arena/variations/object_mass_variation.py`
- Lift 环境源码：`isaaclab_arena_environments/lift_object_environment.py`
- RSL-RL 源码：`isaaclab_arena/policy/rsl_rl_action_policy.py`
- Franka 动作源码：`isaaclab_arena/embodiments/franka/franka.py`
- NVIDIA 模型：https://huggingface.co/nvidia/Arena-Franka-Lift-Object-RL-Task
- EmbodiedCLBench：https://arxiv.org/abs/2610.13021
- EmbodiedEvo：https://arxiv.org/abs/2610.18867

## 给 Codex 的最终执行原则

**不要用演示代替实验，不要用仿真启动代替物理闭环，不要用日志摘要代替真实执行，不要用恢复故意破坏的参数代替科学上的自进化。**

从当前系统的条件出发，持续交付可运行代码、真实物理测试与可审计证据。优先完成 P0→P1→P2→P3，再开始包装展示、PR 与发布。遇到具体 API 不存在时，先检查被锁定的上游源码，再做最小外部适配，不要猜测 API 或悄悄修改基准定义。

