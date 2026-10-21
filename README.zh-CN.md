# PhysicalEvoBench

通过真实物理反馈，评测具身 Agent 的可执行技能有没有改善。

**首个真实闭环已跑通，首个候选未通过验证，尚无正向技能改进证据。**

Franka Lift Object / PhysX 的正式实验共执行 48 个 Episode：8 次训练、8 次验证、32 次独立测试。
更新器根据真实训练失败提出 arm gain 1.0→1.05，候选动作确实改变；验证双方均为 4/4，按预先固定规则回滚。
测试计数为 3/16 与 4/16，但最终技能哈希相同，6.25 个百分点的差异属于物理重放波动，不能宣称自进化成功。

[实际 HTML 报告](docs/evidence/experiments/mvp-seed20261021-001/report/index.html) ·
[真实相机视频](docs/evidence/experiments/mvp-seed20261021-001/videos/baseline_candidate_rejected.mp4) ·
[完整实施报告](docs/implementation/MVP_IMPLEMENTATION_REPORT.md)

安装及一键实验命令见 [英文 README](README.md)。原始轨迹、质量/惯量读回、技能版本、候选理由、
验证决策、分区清单、预算、独立审计均随证据保存。视频展示原技能和被拒绝候选的独立重放，额外消耗
两个物理 Episode，不计入正式成绩。最终新克隆 GPU 复现、PR 检查与发布验收仍在进行。

本项目属于冻结模型权重的状态观测技能适配赛道，不宣称纯视觉控制或模型自主学习。公开测试清单不等于
保密测试服务器。代码 Apache-2.0；NVIDIA 模型单独许可、仅限非商业使用，权重不随仓库发布。
