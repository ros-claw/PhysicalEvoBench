# v0.2 Agent 接口实现范围

状态：基础代码和CPU合约验证；不是已经运行的 AutonomousAgent。

`physicalevobench/v02/agent.py` 提供 observe / propose / run_trial / validate / freeze / load。Agent工具调用者仍需单独接入，不能把脚本搜索或PPO重命名为Agent。trial和有限开发验证分别计费，调用前写入预算账本，基础设施失败也消耗实际调用；无最终留出分数工具。评测器负责提供只包含公开状态的 observe、opaque condition handle 和脱敏训练反馈。Python回调是可信评测器代码，此白名单不是恶意代码隔离沙箱。

可冻结的 `SkillProgram` 是有限关节位置程序：最多16段、总计250控制步，七个有限物理角度目标和二值夹爪；阶段名仅限 approach/align/close/wait/lift/hold/recover。动作按live scale和offset逆变换后进入共同 TargetEnvelope。阶段名表示意图，不证明笛卡尔接近、对齐或抓取已经成立。物理参数、任意Python、评分器及测试条件不是可修改字段。SHA只取可执行内容，重复提案同内容得到同引用；实际重复物理调用仍计费。冻结文件独占创建，后续会话只能显式读回该技能文件，不继承旧实例聊天。

当前CPU验证覆盖失败调用计费、字段拒绝、内容哈希、新实例读回且生成相同行为、被篡改产物拒绝。尚未完成：W3参考控制器通过、各变量的真实动作作用测试、实际模型工具循环、持久经验知识的白名单表示与四组公平比较。因此不启动W4/W5正式研究、不声称跨实例性能迁移已得到物理验证。参考校准通过后才将该DSL或更小的已验证参数子集接入物理执行，不从尚未通过的教师复制未经验证的能力宣称。
