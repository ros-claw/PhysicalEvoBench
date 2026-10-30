# graph-v2：公开物理表达接口

沿用 graph-v1 的 16 节点、2恢复、64转移和全局时限；字段集合不变，target/guard 可以是公开表达式。旧 v1 解释行为保留，旧 place_* 固定目标别名只允许旧 v1，不进入新比赛图。

目标对象：`{"frame":"goal","offset_m":[0,0,0.08],"grasp_offset":true}`。frame 为 object / goal / ee / anchor / initial_object；goal 是公开 task_goal_position，每轴偏移 ±0.2m，grasp_offset 可加抓取时真实末端/物体相对偏移。世界轴表达，不能改变物理状态。

守卫：`{"observable":"finger_min","op":"ge","value":0.038}`；组合 `{"all":[...,...]}` / `{"any":[...]}`，最多3层、每层最多4子项，无任意字段路径。可测 finger_min、object_speed、goal_xy_error、goal_z_error、object_goal_error、ee_object_distance、target_error、orientation_error、finger_contact_min/max。比较为 le/ge，值有固定合法范围。连续 dwell 在不满足时清零；minimum_s 是最短节点驻留，不是夹爪实际完成。超时沿声明边走，不能绕过全局时限。

接触是指物法向力，不是总力或桌面支撑力。支撑几何估计与支撑接触明确区分。现有 `ee_quaternion_xyzw` 字段沿用历史命名，实际原生数组约定为 wxyz；方向可编辑空间不开放该字段，固定方向控制使用原生 wxyz，orientation_error 为计算后的标量。

`contact-integral-v1` 对所有参赛方法相同：启用条件为实测双指法向力≥0.5N 且平均指坐标<.035m；失接触按固定0.2s 时间常数平滑卸载，积分增益/幅值来自冻结正常执行配置，目标包络不变。程序 mode 是兼容/记录标签，不能用换标签开启隐藏补偿。旧 phase-integral 版本仅为历史复现。

`command_response.json` 用同一组真实公开观测同时解释两个候选，报告期望目标/夹爪分歧；它是命令映射的反事实，不是额外物理回合。真实 processed/applied targets 与限幅步另记，避免把候选变化等同于最终动作变化。

独立 lift/place 槽位的旧 SkillLibrary 继续兼容。`reuse_provenance()` 明确 framework_mapped_parameter_transfer、固定任务分派、无共享可执行模块、原样 lift 的哈希及序列化字节。不能把它单独解释为自主技能抽象或共享抗遗忘。当前单题 pilot 没有声称迁移/保持运行。

mode仍声明图解释器中的通用抓取frame捕获及recover计数语义：进入close/recover可更新anchor，进入probe保存物体/相对偏移，close/probe转lift更新抓取偏移。这是公开程序语义，不能将mode称为完全无作用标签；被移除的是mode对新执行协议积分启停的隐藏影响。
