# v0.2 物理与控制诊断

登记阶段：W1 原生仪表尚未验证，不将下列计划当完成结果。历史结论保持不变。

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
