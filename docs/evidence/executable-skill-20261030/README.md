# 1030 实验证据入口

[完整实施报告](../../implementation/EXECUTABLE_SKILL_LEARNING_实施报告_20261030.md) 先给学习问题、各组实际结果与解释限制。此目录只保留轻量派生证据；完整物理/模型原始记录在 [实验 Alpha](https://github.com/ros-claw/PhysicalEvoBench/releases/tag/esl-alpha-20261030) 的可选分片中。许可权重及资产不随项目分发。

- `method_results.json`：五组分开保存的成绩、每实例结果、模型实际费用与产物成本；探索性扩展复用旧产物，不重复计学习实例。
- `method_query_cases.csv`：全部查询的真实逐条件结果与终态，质量等评估器字段仅在冻结后导出。
- `*-learning_events.json`：真实调用、客观反馈与下一提案的对应；模型自己的笔记是假设，不是事实标签。
- `actual_costs.json`：全部本轮研究的实际物理回合、控制/物理样本、执行干预、进程时间及失败。
- `full_initial_pairing_audit.json`、`cross_study_query_seed_audit.json`：实测初态配对与五组查询seed不重叠；不是新增物理试验。
- `very_early_drop_observations.csv`：所有≤8控制步的任务失败，保留分数并单列场景支撑异常线索，根因未知。
- `reference_replay_results.json`：12个既有查询条件、各两次执行同一强参考，24回合；不是24个学习实例。
- `fresh_workflow_provenance.json`：新目录流程的登记、接口版本与状态；原生依赖和许可模型复用，不能称为另一台机器全新安装。
- `authored-collision-geometry.json`、`environment/`、`old-release-events/`：只读资产/环境测量及旧失败的事件重建，均不改旧分数、不计新物理回合。

发布文件：`executable-skill-source.tar.gz` 为轻量源码/配置/文档；`executable-skill-sample.tar.gz` 是修复后实例中预先指定query-000的Frozen/Feedback局部原始记录，不是全部查询，也不按成功挑选。完整重算需要 `manifest.json` 列出的所有 `data-*.tar.gz` 和 `source-*.tar.gz`，不能用局部样例替代研究审计。

```bash
uv run python -m physicalevobench.core.delivery verify --evidence /path/to/downloaded-assets --output /new/extraction-directory
```

`public_delivery_audit.json` 记录完整分片在另一目录解包后的离线重算；`source_rebuild_audit.json` 记录不带旧Git对象的源码包CPU重建；`source_manifest.json`、`SHA256SUMS` 与 `publication_receipt.json` 区分打包源码、文件哈希与公开发布元数据。离线审计、CPU重建、新目录物理执行是三种不同证据。
