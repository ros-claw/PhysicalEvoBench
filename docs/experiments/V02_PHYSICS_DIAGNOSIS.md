# v0.2 物理与控制诊断

状态：W1 原生仪表已通过两种终止模式集成和16回合代表案例补跑；W2/W3独立登记运行中。历史结论保持不变。下面明确区分已完成结果和待验证假设。

## 已确认（离线）

动作语义由固定源码和 live mapping 双重核对：机械臂 `q_target = 0.5 * action + explicit_nominal_offset`，不是逐步关节增量；夹爪负值关闭、零/正值打开，分别目标 0 和 0.04 m。新执行层在 ActionTerm 完成处理后约束关节目标，不对二值夹爪做错误的连续原始动作解释。

旧调度器的负奖励边界错误成立，但最新 18 个历史任务的首末四分位平均奖励全部为正。新规则反算仅一个任务（s2-continual/round-1）改变下一轮学习率：0.1116835→0.1182887 的增长在预先固定尺度下限 1.0 下不足 1%，故从 1e-4 变为 5e-5。这是尺度下限的影响，不能证明负奖励缺陷导致历史失败。新版本修复；旧函数与所有历史决定保留。

离线选择规则：每种原模型/最后原始持续候选/最后原始重训候选，分别取最深手指越限、成功但越限、失败不越限；按最大手指深度降序、条件 ID/worker 路径打破平局。9 个类别中允许重复同一回合；补跑按模型 SHA+条件去重，完整保留选择清单。另对历史主研究 384 对同模型轨迹计算首次精确记录分歧，不唯一归因为 GPU 或接触。

## W1 补跑冻结配置

- GPU 0 单 worker 顺序运行；记录共享负载，不停止其他任务。
- 先 0.1 kg 名义条件的两个仪表集成回合：LegacyInstant 与 FixedHorizonDiagnostic。
- 新版本严重边界：手指深度 >0.01 m、机械臂 >0.1 rad 或非有限关节状态，终止并记录。它们是诊断中断边界，不是硬件安全认证。
- `TargetBounded`：live hard 位置区间、目标变化率不超过 live velocity limit 与 arm 1 rad/s / finger 0.04 m/s 两者较小值；原 solver 速度/effort、碰撞与重力不改。实际状态独立测量。
- 每个代表回合分别补跑 NumericalOnly 和 TargetBounded；它们属于新诊断实例，不称为历史回合逐位复现。
- 目标、实际位置/速度、ContactSensor 净力及 cube-filtered 力、USD 关节配置、hard/soft/solver limits 与目标单位落盘。实际未读取成功的力字段标 NOT_MEASURED。
- 用 scene.update 后钩子记录暴露的物理子步；recorder.record_pre_reset 在自动重置前记录 terminal。后端内部 decimation 的隐藏子步明确标未测量。
- FixedHorizonDiagnostic 固定 episode 内目标命令时间，不因到达目标立即终止；严重边界仍优先终止。

## 待验证

厘米级越限与处理后目标、接触、solver/资产拓扑的关系；终态是否完整；单位/索引是否匹配。当前不宣称 mimic、重置或 NVIDIA 缺陷是根因。

证据入口将由实际运行补充：`control_semantics.json`、`history_diagnosis.json`、逐回合首越限、物理/目标轨迹、terminal pre-reset。

官方参考：[关节稳定性指南](https://docs.omniverse.nvidia.com/kit/docs/omni_physics/110.0/dev_guide/guides/articulation_stability_guide.html)、[确定性说明](https://isaac-sim.github.io/IsaacLab/main/source/how-to/reproducibility.html)。这些是排查指导；运行 API 以固定安装源码为准。

## 2026-10-26 实际完成的 W1 结果

原始四回合集成记录分为 smoke-001 和 smoke-002（各两回合），均实际完成。001初版把Python层约束结果作为下发目标记录；002修正为ActionTerm写入后读回float32值，两版源码和实际成本均保留，不把001冒充修正后的记录。002全部控制步通过仿射动作映射和物理目标包络的逐步重算；250控制步对应1000个post-physics记录，dt为0.005秒、控制dt为0.02秒、decimation=4。终止前关节位置/速度和物体位置/速度与最后物理样本一致。未发现该后端隐藏decimation；不对PhysX内部不可见求解迭代作采样声明。

读回九个可动关节，11个USD关节（7转动、2移动、2固定），stage单位1m。手指live hard范围为[0,0.0399999991]m、live velocity limit约0.2m/s；机械臂限位为rad、USD角度限位为degree，不能直接按相同数字比较。已采样关节的applied schemas未列出mimic API，不能据此把未遍历资产或全部求解器约束都宣称排除；W3新版本进一步保存body0/body1等关系目标。ContactSensor成功读回净力及cube-filtered力；implicit actuator的computed/applied_torque字段不是求解器真实关节驱动力，仍未获得该测量。

受限执行配置见 `configs/v02_target_bounded.yaml`，运行真值是每个worker的control_semantics.json和注册源码。这个配置文件记录已运行版本的参数，不倒改已登记源码或物理条件。

代表案例按9类别去重为8实例，每个实例补跑两种执行层，16回合全部完成并经独立审计。成对初始物理状态8/8完全相同；这些是新补跑，不能替代历史原始终态。

| 新补跑执行层 | 回合 | post-physics瞬时到达 | 严重事件 | >1mm越界回合 | 最大手指越界 |
|---|---:|---:|---:|---:|---:|
| NumericalOnly | 8 | 2 | 3 | 4 | 17.960 mm |
| TargetBounded | 8 | 0 | 0 | 2 | 7.136 mm |

这8个实例是按极端行为有意选择的小样本，不是一般成功率或风险率估计。严重边界会提前终止，因此新版本峰值不能直接与历史不中断峰值比较。TargetBounded减少这批案例的严重事件，但显著改变了策略执行，不能宣称无代价修好物理或已得到合格基线。

### 首次越界提供了什么线索

- sample-00 NumericalOnly：第65控制步、全局物理计数263首次超过1mm，手指目标仍为正常打开位置0.04m，左指速度约1.581m/s，净接触力z约1289.47N、cube-filtered力为零。
- 同条件TargetBounded：第224控制步才首次超过1mm，右指目标仍为0.04m，右指速度约-1.687m/s，净接触力z约262.61N、cube-filtered力为零。
- sample-03 NumericalOnly：第40控制步已在关闭目标0m时首次越界，两指cube-filtered接触力非零。
- sample-05 TargetBounded：第234控制步打开目标0.04m时首次越界，右指净接触力z约47.96N、cube-filtered为零，随后该回合最大越界达7.136mm。

因此至少存在“正常二值指目标+非cube净接触”和“闭合抓取cube接触”两类越界上下文。目标约束不能阻止所有实际状态越界；报告的solver速度限值也不等于瞬时状态必然受限。尚未区分非cube力究竟来自桌面、自碰撞或其他接触，尚未进行dt/effort/接触因素的单因素因果试验。不能从同期力峰值唯一推出NVIDIA缺陷、mimic竞争或驱动刚度是根因。

历史384对同模型主研究记录中，110对没有记录值/长度差异，274对有轨迹差异，66对官方结果不同；274对的物体首次差异中位数为第5控制步，关节为第7步，动作第5步。跨GPU/进程块混杂仍在，不能归因为单一因素。当前W2会在同GPU和同动作接口下收窄这个问题。

本地原始入口：`/home/dell/peb-v02-smoke-20261026-002`、`/home/dell/peb-v02-representatives-20261026-001`；离线历史入口 `runs/v02-history-20261026/history_diagnosis.json`。代表案例的 `diagnosis.json` 保存逐案例首次越界动作、速度、接触证据，`episode_metrics.csv` 为可检查汇总。

### 一回合最小复现

以下命令会先注册**额外1个**实际诊断回合，使用原登记commit的不可变源码、相同模型SHA和条件；需要本地已有单独许可的模型，不承诺逐位复现：

```bash
uv run python scripts/reproduce_v02_case.py \
  --registration /home/dell/peb-v02-representatives-20261026-001/registration.json \
  --worker sample-00-NumericalOnly --gpu 0 \
  --output /home/dell/peb-v02-minimal-repro-NEW
```

只审核已完成证据、不启动仿真：

```bash
uv run python scripts/report_v02_diagnostics.py \
  --run-dir /home/dell/peb-v02-representatives-20261026-001
```

上述一回合脚本已实际运行于 `/home/dell/peb-v02-minimal-repro-20261026-001` 并通过审计：第170控制步结束、严重边界终止、最大手指越界14.622mm。原代表补跑为67步和17.960mm，故这是严重问题的再次出现，**不是相同时间和相同轨迹的逐位复现**。新增1回合已计入本阶段实际成本。

对齐图（每张n=1，时间零点为该回合首次测得>1mm越界，物理采样5ms；不能跨图把不同时间零点当作同一物理时刻）：

- [原始策略、NumericalOnly](figures/v02-first-violation/sample-00-NumericalOnly.png)
- [同条件、TargetBounded](figures/v02-first-violation/sample-00-TargetBounded.png)
- [持续学习候选、cube接触](figures/v02-first-violation/sample-03-NumericalOnly.png)
- [受限执行层仍有状态越界](figures/v02-first-violation/sample-05-TargetBounded.png)

图表脚本 `scripts/plot_v02_diagnostics.py` 不启动SimulationApp；使用已固定Arena解释器的matplotlib，输入经audit_run重算通过后才绘图。图源SHA见对应目录plot_sources.json，数值来自原始物理记录，线段只连接采样点，不声明采样间状态已测量。
