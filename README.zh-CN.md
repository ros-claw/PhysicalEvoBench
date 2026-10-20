# PhysicalEvoBench

通过真实物理反馈，评测具身 Agent 的可执行技能有没有改善。

首版目标：Isaac Lab-Arena 的 Franka Lift Object；冻结官方 RSL-RL 权重，改变
物体质量；通过训练失败提出受约束的 Skill 修改，经独立验证提升或回滚，冻结后
在同一批未参与更新的条件下比较 Frozen 与 Updated。

**当前仍在实施，真实物理 MVP 尚未验收，也没有测得进化收益。** CPU 测试只验证
协议约束。状态、原始证据和阻塞见 [实施报告](docs/implementation/MVP_IMPLEMENTATION_REPORT.md)。

安装和命令见 [英文 README](README.md) 和 [复现说明](docs/reproducibility.md)。
本项目使用含特权状态的官方策略观测，不宣称纯视觉控制；公开测试清单也不等于
保密的线上测试服务器。负收益、未提升和基础设施失败必须如实记录。

项目代码采用 Apache-2.0；NVIDIA 模型单独许可，仅限非商业使用，权重不随仓库发布。
