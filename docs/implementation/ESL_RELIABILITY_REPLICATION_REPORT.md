# PhysicalEvoBench ESL：可靠性与独立重复实施报告

**最终复核：注册执行自审与独立目录全量重算均PASS，结果逐项一致。工程、测量、算法分别判断。**

本轮要保留的结论是：**在固定 Place–Release 有限问题上，八次独立学习都形成了可继承、可重复验证的释放技能改进；尚未建立相对专家模板的稳定优势，更没有证明广泛或递归自进化。** Feedback为128/128，每个block均16/16；Frozen、NoFeedback、Deletion均87/128；TemplateSearch-4为126/128。注册执行自审和独立解包全量重算均已通过，最终收据见文末。

本轮保留 Place–Release Factorial v2，公开上下文固定 public-context-v3，执行版本固定 core-place-public-v5-ready2。独立学习8个block，每block16个配对query，五方法；全部产物先冻结，再开始查询。旧Alpha及其失败不改判、不池化。

| 方法 | 已知成功 / 全部分配 | 有效任务执行成功 | 学习物理尝试 | 实际模型调用 | 输入 / 输出 tokens |
|---|---:|---:|---:|---:|---:|
| Frozen | 87/128 | 87/128 | 0 | 0 | 0 / 0 |
| NoFeedback | 87/128 | 87/128 | 0 | 8 | 136642 / 8544 |
| TemplateSearch-4 | 126/128 | 126/128 | 64 | 0 | 0 / 0 |
| Feedback | 128/128 | 128/128 | 54 | 62 | 1643005 / 66272 |
| Deletion | 87/128 | 87/128 | 0 | 0 | 0 / 0 |

每方法另有128次配对查询；表中物理成本列仅为在线学习成本。Frozen/NoFeedback/Deletion成功率67.97%，TemplateSearch-4为98.44%，Feedback为100%。货币费用无账单为unknown。全分配列是已观察到的成功产出，缺失/服务故障不会补成模型能力零分；下表列出缺失和归因。有效执行分母另列。Deletion恢复共同starter，其配套学习成本已在Feedback计费，不重复计费。

| 验收维度 | 判断与边界 |
|---|---|
| 工程 | **本机范围通过**：无PPO权重状态执行、冻结恢复、通用stdin接入、同机新源码/新CPU环境及固定样例重算已实测。第二机器/独立外部人复现未验证。 |
| 测量 | **本批有限分布得到支持**：640/640查询有效，初始化无效/查询进程失败/未知结果均0；真实PhysX质量/惯量读回、故障注入和逐子步重算共同约束测量。同图不一致0/128是本批观测，不是零噪声保证。旧异常的唯一根因仍未定。 |
| 算法 | **受约束技能改进得到重复支持**：八block的Feedback−Deletion均为正；**相对专家模板稳定领先未证明**，纯反馈因果作用及广泛/递归自进化未证明。此判断来自成绩与不确定性，不来自工程或审计PASS。 |

本轮交付为可比较的单问题研究版本，工程与测量在上述边界内分别验收。参考资格在方法查询前完成，判据不要求starter失败或Feedback获胜；方法结论另外依赖固定版本、完整配对成绩、逐block重复、真实执行作用与成本。没有据此启动跨任务或跨模型正式排名。

## 固定方法比较与逐block结果

这是budget-cap comparison：NoFeedback和Feedback共享最大预算，但允许自然提前冻结，实际tokens/调用可以不同。TemplateSearch-4是人工专家候选先验加score-only选择，4候选×共同2支持条件；不是无先验盲搜，也不等于全图空间最优搜索。

| 比较 | block均值差 | 分层95%区间 |
|---|---:|---|
| Feedback − NoFeedback | +32.03 pp | [+27.34 pp, +37.50 pp] |
| Feedback − Deletion | +32.03 pp | [+27.34 pp, +37.50 pp] |
| Feedback − TemplateSearch-4 | +1.56 pp | [+0.00 pp, +5.47 pp] |

| Block | Frozen | NoFeedback | TemplateSearch-4 | Feedback | Deletion | F−NoFeedback | F−Deletion | F−Template | 同图不一致 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 10/16 | 10/16 | 16/16 | 16/16 | 10/16 | +37.50 pp | +37.50 pp | +0.00 pp | 0/16 |
| 1 | 10/16 | 10/16 | 14/16 | 16/16 | 10/16 | +37.50 pp | +37.50 pp | +12.50 pp | 0/16 |
| 2 | 11/16 | 11/16 | 16/16 | 16/16 | 11/16 | +31.25 pp | +31.25 pp | +0.00 pp | 0/16 |
| 3 | 12/16 | 12/16 | 16/16 | 16/16 | 12/16 | +25.00 pp | +25.00 pp | +0.00 pp | 0/16 |
| 4 | 11/16 | 11/16 | 16/16 | 16/16 | 11/16 | +31.25 pp | +31.25 pp | +0.00 pp | 0/16 |
| 5 | 10/16 | 10/16 | 16/16 | 16/16 | 10/16 | +37.50 pp | +37.50 pp | +0.00 pp | 0/16 |
| 6 | 11/16 | 11/16 | 16/16 | 16/16 | 11/16 | +31.25 pp | +31.25 pp | +0.00 pp | 0/16 |
| 7 | 12/16 | 12/16 | 16/16 | 16/16 | 12/16 | +25.00 pp | +25.00 pp | +0.00 pp | 0/16 |

统计以独立学习block为最外层，内部在goal×mass cell内配对抽样；本研究只有一个有限物理问题，128个query不是128个独立任务族。每方法/条件通常只有一次物理执行，Frozen/Deletion同图重放用于显示不一致，无法完全分离每个学习产物的物理重放方差。8个block也不保证总体显著性。

| Block | Frozen独胜 | Deletion独胜 | 不一致对 / 有效配对 |
|---|---:|---:|---:|
| 0 | 0 | 0 | 0/16 |
| 1 | 0 | 0 | 0/16 |
| 2 | 0 | 0 | 0/16 |
| 3 | 0 | 0 | 0/16 |
| 4 | 0 | 0 | 0/16 |
| 5 | 0 | 0 | 0/16 |
| 6 | 0 | 0 | 0/16 |
| 7 | 0 | 0 | 0/16 |

不能用净成功差代替重放噪声；相反方向的交换会抵消。历史v2 N=1的三个同向不一致对精确双侧配对二项p=0.25，v3一个不一致对p=1；它们只说明小样本分辨力，不与本轮合并，也不把p阈值当验收条件。

## 在哪些物理条件上发生了变化

| Query目标XY (m) | 质量kg | Frozen | NoFeedback | TemplateSearch-4 | Feedback | Deletion |
|---|---:|---:|---:|---:|---:|---:|
| [0.6, 0.12] | 0.1 | 30/32 | 30/32 | 32/32 | 32/32 | 30/32 |
| [0.6, 0.12] | 0.4 | 32/32 | 32/32 | 32/32 | 32/32 | 32/32 |
| [0.62, -0.12] | 0.1 | 0/32 | 0/32 | 32/32 | 32/32 | 0/32 |
| [0.62, -0.12] | 0.4 | 25/32 | 25/32 | 30/32 | 32/32 | 25/32 |

原始损失主要集中在负Y、0.1kg组合，不能把困难简单解释为“重物更难”。Feedback相对模板的两个额外成功都位于block1的负Y、0.4kg组合。此表是预定义cell的描述，不是四个独立任务族或对新物理机制的总体区间。

640份实测初态覆盖128个注册query：按1e−6舍入有128种机器人关节初态、1种Cube初态，128种包括公开目标/质量的物理起点。reset抽样确实改变机器人姿态；Cube几何/初始位置未形成新对象族。旧Lift遗留目标命令也有128种，但它不是本任务公开放置目标，不能拿它的随机性冒充迁移。X留出只差2cm、小于5cm成功容差，仍是弱因素组合留出。

同图Frozen/Deletion在全部128对上无结果交换。它限定本批重放差异的观测，不意味着物理过程绝对确定或其方差已完整分解。

## 学到了什么、实际执行是否受到影响

Feedback−Deletion与Feedback−NoFeedback均为 **+32.03个百分点，分层95%区间[+27.34,+37.50]**；八个block分别提高25.00–37.50个百分点。冻结图整体的保留具有明确的有限分布性能价值。Feedback−TemplateSearch-4为 **+1.56个百分点，区间[0,+5.47]**，两个额外成功都集中在block1，其余七个block持平。这不能支持Feedback稳定优于专家模板。上述区间只重采样已见block与条件，不能发现尚未出现的失败；区间不含负值也不是预先注册的等价性或优越性检验。

本轮属于自然提前冻结的budget-cap comparison。NoFeedback实际每block只调用1次模型，Feedback共62次调用；因此Feedback−NoFeedback比较的是完整方法流程，不能单独归因为物理反馈的信息价值。TemplateSearch-4带有人工专家候选先验，该先验的开发成本未量化，不能把零在线模型调用解释为零总体研发成本。

| 方法 | 冻结后实际保留了什么 | 本轮继承判断 |
|---|---|---|
| Frozen | 共同starter，13节点 | 原始参照，无新增经验 |
| NoFeedback | 八次都保留同一个starter可执行图；文字或来源差异不改变这一事实 | 未形成相对starter的新可执行行为，不把笔记或artifact哈希差异计为能力增长 |
| TemplateSearch-4 | 八次都选中零基索引1，即第二个“按实际夹爪开度释放”专家候选 | 126/128，是应保留的强先验基线；不是无先验盲搜 |
| Feedback | 八次都把release转移改为finger_min≥0.035m，同时修改lower的目标位置/物速条件及部分超时处理；block0保留13节点，其他七个移除原hold节点为12节点 | 相对Deletion八block均有正收益，值得在此有限分布继承；节点删除本身不作为贡献证据 |
| Deletion | 删除学习后的整个产物并恢复共同starter | 87/128，支持收益随冻结可执行图保留；不是单独删除文字memory的消融 |

迁移到测试进程的是图，测试期零模型调用，文本memory不参与控制。这里实测到的是一类通用释放与落稳条件的修订。本设计没有跨block重采样新的物理机制theta，不能据此声称已证实物理系统辨识或广泛上下文适应；八次学习也没有产生八个独立任务族。性能值得继承不等于已经证明经济上划算：Feedback在线学习少用10次物理尝试，但比Template多用62次模型调用；缺少货币账单、任务收益权重与后续复用频率，不能据此构造统一成本最优排名。


以下仅记录产物和真实执行链，不能凭文件diff、笔记不同或节点增加判为能力增长。是否值得继承，要同时看Feedback−Deletion、参考方法比较、成本与独立block不确定性。 本批八个Feedback形成八个不同可执行指纹；block7只访问了3/4支持句柄，其余七个访问4/4，实际序列如下，未强制补齐或重抽。

| Block | Feedback实践数 | 覆盖支持句柄 | 图与starter行为指纹是否不同 | 最终节点数 | NoFeedback调用数 | Feedback调用数 |
|---|---:|---|---|---:|---:|---:|
| 0 | 6 | ['practice-0', 'practice-0', 'practice-1', 'practice-1', 'practice-2', 'practice-3'] | True | 13 | 1 | 7 |
| 1 | 7 | ['practice-0', 'practice-0', 'practice-2', 'practice-1', 'practice-1', 'practice-3', 'practice-0'] | True | 12 | 1 | 8 |
| 2 | 8 | ['practice-0', 'practice-0', 'practice-2', 'practice-1', 'practice-1', 'practice-3', 'practice-0', 'practice-2'] | True | 12 | 1 | 9 |
| 3 | 7 | ['practice-0', 'practice-0', 'practice-1', 'practice-1', 'practice-2', 'practice-3', 'practice-0'] | True | 12 | 1 | 8 |
| 4 | 5 | ['practice-0', 'practice-0', 'practice-2', 'practice-1', 'practice-3'] | True | 12 | 1 | 6 |
| 5 | 8 | ['practice-0', 'practice-0', 'practice-2', 'practice-1', 'practice-1', 'practice-1', 'practice-3', 'practice-0'] | True | 12 | 1 | 9 |
| 6 | 5 | ['practice-0', 'practice-0', 'practice-1', 'practice-2', 'practice-3'] | True | 12 | 1 | 6 |
| 7 | 8 | ['practice-0', 'practice-0', 'practice-2', 'practice-1', 'practice-1', 'practice-1', 'practice-1', 'practice-1'] | True | 12 | 1 | 9 |

| 查询方法 | GUARD_EVALUATED | BRANCH_TAKEN | COMMAND_CHANGED | APPLIED_TARGET_CHANGED |
|---|---:|---:|---:|---:|
| Frozen | 128000 | 1152 | 1024 | 1024 |
| NoFeedback | 128000 | 1152 | 1024 | 1024 |
| TemplateSearch-4 | 128000 | 1152 | 1024 | 1024 |
| Feedback | 128000 | 1152 | 1024 | 1024 |
| Deletion | 128000 | 1152 | 1024 | 1024 |

这些是嵌套的真实轨迹计数，计数相同不代表策略相同，也不证明收益。Feedback的1152次转移中1108次为守卫分支、44次为有界超时；其他方法没有超时分支。不能把超时写成阈值满足。

按“block0、首个实际排定query、最早进入完整执行链的已修改守卫”固定规则取例：query-009，第500控制步，lower从旧pose守卫改为goal_xy_error≤0.04m、goal_z_error≤0.02m、物速≤0.1m/s；实测条件满足后进入release，夹爪命令close→open，两个指关节实际目标0→0.0008m。[完整观测与目标记录](../evidence/esl-reliability-20261030/final/changed_guard_example.json)。该例证明改动参与控制，不单独识别哪一条改动造成最终成功。

把starter与冻结图都喂给**同一条已记录公开观测序列**，得到以下命令映射差异。它不是另一次物理rollout，不推断starter真的会经过同一轨迹：

| 方法 | Query数 | 目标命令不同的query | 目标命令不同控制步 | 夹爪命令不同控制步 | 最大目标差m |
|---|---:|---:|---:|---:|---:|
| Frozen | 128 | 0 | 0 | 0 | 0.000 |
| NoFeedback | 128 | 0 | 0 | 0 | 0.000 |
| TemplateSearch-4 | 128 | 128 | 3968 | 0 | 0.112 |
| Feedback | 128 | 128 | 28028 | 22764 | 0.112 |
| Deletion | 128 | 0 | 0 | 0 | 0.000 |

实际执行层另记录全部控制目标和限幅；主研究共184767个控制步被共同目标速率约束限幅，硬边界终止/测得的位置越界episode均0。这是特定坐标/时间采样的结果，Cube净力或指物接触不覆盖所有碰撞，更不构成真机安全结论。

## 参数传输缺陷、初始化边界与尚未确定的因果归属

三条旧异常对预选同条件正常对照，首次明显分离均在记录的第17个物理子步（0.085s）：异常z≈0.01943m、vz≈−0.83385m/s；正常z≈0.02100m、vz≈−0.00535m/s，指物法向接触为0。它发生在夹持之前，支持支撑异常层面的判断。旧协议未测cube–table配对接触，不能追溯断言某个collider/cooking/API是唯一根因。

18次固定关节/开指、无接近交叉诊断：旧异常条件轮换首/二/三槽位，有/无额外readback，均未复现穿桌；不足以证明普通随机噪声，也不能据此排除初始化时序问题。并发源码导出曾发生半写入误判；已完成9次保留，仅9个未启动槽位恢复，源码缓存导出改为跨线程/进程锁。

Ready采用固定200子步（1秒）无候选支撑预演，检查PhysX静态桌面shape ray hits、Cube实测净法向力、速度/高度、有限状态、shape/body数量及质量读回；恢复同一条件原始关节/物体状态、朝向和速度，不换seed、不再随机、不改任务时钟/评分。任务起点仍是原始cube高度0.055m，相对抬升门槛未放宽。求解器/接触历史被预演，属于新执行分布。

实际静态桌面碰撞路径为 /World/envs/env_0/table/Collisions/Cube，运行时查询顶部约−0.003m；Cube落稳中心约0.021m。Cube net_normal_forces_w是世界轴牛顿值（轻质量约0.981N），不是精确cube–table配对力。静态桌面不能直接用旧的刚体ContactSensor正则过滤；该错误启动尝试保留。PhysX配对report当前为空/未测，不能把净力冒充配对力。GPU动态Cube ray返回曾显示滞后姿态，因此Ready仅用静态桌面查询，不声称所有动态查询已同步。

| 诊断/尝试 | 实际物理尝试 | 结果 |
|---|---:|---|
| 固定姿态交叉（含仅未启动槽位恢复） | 18 | 0次自发异常复现；根因未定 |
| Ready-001 | 0 | 静态表面传感器filter构建失败，原生设置失败 |
| Ready-002 | 6 | 原碰撞配置未生效，负例无效，不能作检测证明 |
| Ready-003 | 6 | 4正常READY，2个已确认移除碰撞体的负例INIT_INVALID，任务控制0步 |
| 参数传输独立诊断 | 6 | GPU缓存0.4kg而PhysX模型0.1kg/惯量不一致；同值同步重写组未发现不一致 |
| Ready-004（Ready2） | 6 | 4正常READY且真实模型参数匹配，2确认支撑缺失INIT_INVALID，任务控制0步 |
| 新执行参考资格 | 14 | QUALIFIED；starter 3/4，strong 4/4，同图 4/4，force-open 0/2 |

短诊断总计42次，低于48上限；两版参考资格各14次另列。无故障注入冒称自发故障复现。正常检查与明确支撑缺失负例的离线原始重算一致；这限定了当前可检测边界，不能保证所有仿真错误均可识别。Ready失败不生成任务标签；原因不明的运行期掉落仍保留任务失败/UNKNOWN，不自动免责。

已确认的参数传输缺陷：固定Lab的indexed setter把GPU数据异步wp.copy到pinned CPU mass/inertia/index scratch，随后CPU PhysX setter可能消费未完成的旧数据。直接PhysX getter与GPU shadow读回分离的诊断复现了这一点；同值同步重写消除该诊断中的不一致。Ready2只在Cube对应的set_masses/set_inertias入口等待当前上下文传输完成，保留原采样与惯量比例。预演前后及恢复后都用PhysX get_masses/get_inertias验证真实模型值，不能靠缓存自证。固定Arena/Lab文件没有修改。

首次Ready1 cohort因此在所有query开始前整体停止，未挑有利block回收：59次已完成物理尝试、41次真实模型调用、0query，全部成本单列保留。这不是负算法成绩，也不是一次正式8-block结果。新Ready2从所有方法共同starter/空记忆重新登记完整8-block；提示仍是原v3，没有把新诊断写进Agent上下文。旧Ready1资格卡保留，但其缓存核验不能追认为真实质量已验证。

## 首槽位、query-000与代表失败

查询条件顺序已与进程槽位分开：40个native首槽位分布于12个不同base query编号，只有1个首槽位恰为query-000。40个首槽位及40个query-000均有效，均无≤8控制步极早任务失败；全部640query均完整1000控制步。它支持当前故障边界，不倒推旧异常唯一原因。[槽位检查](../evidence/esl-reliability-20261030/final/first_slot_query_zero.json)。

固定取最低block/编号的Frozen失败，并列出全部两个模板失败：

| 方法 / Block / Query | 抬起 / 运输 | 最大合格落稳时长 | 终态XY误差 | 结果 |
|---|---|---:|---:|---|
| Frozen / 0 / 008 | 均已观察到 | 0s | 6.75cm | 有效任务失败 |
| TemplateSearch-4 / 1 / 012 | 均已观察到 | 0s | 5.31cm | 有效任务失败 |
| TemplateSearch-4 / 1 / 015 | 均已观察到 | 0s | 6.12cm | 有效任务失败 |

这三例均为20秒horizon结束、终态XY误差超过5cm，不能改归初始化故障。Feedback本批没有查询失败；这不保证未见条件上不会失败。完整终态与选择规则见[代表失败记录](../evidence/esl-reliability-20261030/final/representative_failures.json)。未通过专门物理消融识别单个守卫/超时改动的因果贡献。

## 故障、分母和真实成本

| 方法 | 全部分配 | 有效任务执行 | INIT_INVALID | 参与者非法 | 结果缺失 |
|---|---:|---:|---:|---:|---:|
| Frozen | 128 | 128 | 0 | 0 | 0 |
| NoFeedback | 128 | 128 | 0 | 0 | 0 |
| TemplateSearch-4 | 128 | 128 | 0 | 0 | 0 |
| Feedback | 128 | 128 | 0 | 0 | 0 |
| Deletion | 128 | 128 | 0 | 0 | 0 |

服务/基础设施导致的未完成方法记录：[]。自动provider/物理重试均为0；usage缺失为unknown。参与者格式错误可在原预算内自行修正，评测器不代修图。

主研究实际物理成本（诊断、参考资格、外部接入另列）：

```json
{
  "task_attempts": 758,
  "task_controls": 758000,
  "task_physics_substeps": 3032000,
  "ready_physics_substeps": 151600,
  "init_invalid": 0,
  "native_processes": 56,
  "native_process_seconds": 63253.363829999995,
  "native_processes_missing_timing": 0,
  "reserved_task_attempts": 758,
  "uncompleted_reserved_attempts": 0,
  "unverified_completed_task_attempts": 0,
  "hard_boundary_episodes": 0,
  "position_violation_episodes": 0,
  "limited_task_controls": 184767
}
```

任务物理时长按实际子步×0.005s，Ready时长另列；模型缓存是输入的子集，不与输入重复相加。原生进程时间含启动、空闲等待模型和退出，不等于GPU独占时长。货币费用无账单为unknown。安全只报告已测硬边界、坐标越界与限幅，不宣称全接触/真机安全。

```json
{
  "method": "NoFeedback",
  "calls": 8,
  "input_tokens": 136642,
  "output_tokens": 8544,
  "cached_input_tokens": 97920,
  "cache_write_input_tokens": 0,
  "wall_seconds": 124.90197836374864,
  "money": "unknown"
}
```

```json
{
  "method": "Feedback",
  "calls": 62,
  "input_tokens": 1643005,
  "output_tokens": 66272,
  "cached_input_tokens": 646272,
  "cache_write_input_tokens": 0,
  "wall_seconds": 943.6738815600984,
  "money": "unknown"
}
```

## 外部接入与复现范围

同机新源码目录、新CPU venv，复用固定原生安装/资产缓存；通用stdin adapter走实际模型调用，设计并冻结后在新原生进程执行：

```json
{
  "status": "PASS",
  "physical_attempts": 1,
  "task_success": true,
  "task_controls": 1000,
  "PPO_weights_used": false,
  "model_calls": 1,
  "scope": "Protocol and real execution integration only; task failure would not by itself fail engineering integration."
}
```

适配器仍经同一个Codex CLI和同一请求模型，不是第二个独立框架或模型。第二兼容RTX机器与未参与开发的外部人员复现均未验证；本轮不冒称完成。新状态执行无需下载/加载未使用的PPO checkpoint，身份为代码/执行配置哈希，旧模型接口保留。资产与原生依赖许可单独遵守。

最小入口见 [Quickstart](../reliability/QUICKSTART.md)，源码/固定局部样例与完整轨迹分开。默认不下载历史证据。DeliberationOnly-9与额外B2/B4查询曲线在主研究开始前登记为NOT_RUN，本轮优先完成固定主研究；B2/4/8快照只留档，不伪造未测学习曲线。

## 证据与适用范围

- 主研究注册与完整结果：[peb-esl-replication-20261030-002](/home/dell/peb-esl-replication-20261030-002)，注册源码 `aefd7955fcbf75363979ef0cd0e5825e52748771`。
- 新执行资格：[peb-esl-ready-qualification-20261030-002](/home/dell/peb-esl-ready-qualification-20261030-002)；故障边界：[peb-esl-ready-conformance-20261030-004](/home/dell/peb-esl-ready-conformance-20261030-004)。
- 旧异常首次分离：[原始来源与SHA](../evidence/esl-reliability-20261030/old_first_divergence.json)。
- 任务书：[ESL下一阶段实施任务书](../../PhysicalEvoBench_ESL_下一阶段实施任务书_20261030.md)。

物理命令/返回码见每个native的launch.json与process.json；请求、保留预算、模型真实usage、公开反馈、Ready预演、逐子步轨迹、产物SHA、逐block图与实际执行链保留。离线重算不会产生新的独立学习或物理回合。服务标识gpt-6.1-terra，具体基础权重哈希、effort与fingerprint unavailable，结论限定于本实验窗口。

查询X差仅2cm，小于5cm成功容差，称留出因素组合而非强空间OOD。结论不外推到跨任务迁移、视觉、在线任意代码、权重学习、多智能体或递归自进化。旧双任务Core不因此追认验收。未按成绩换题、换提示、追加直到显著；PR #10与旧Alpha保留，新合并/发布不在本轮授权范围。

## 本轮全部已付出成本

| 阶段 | 实际物理尝试 | INIT_INVALID | 模型调用 | 输入 / 输出tokens | 原生退出或耗时未知 |
|---|---:|---:|---:|---:|---:|
| 短诊断（上限48） | 42 | 5 | 0 | 0 / 0 | 0 |
| 两版参考资格 | 28 | 0 | 0 | 0 / 0 | 0 |
| 停止的Ready1批次 | 59 | 2 | 41 | 967958 / 42235 | 4 |
| 两版stdin工程smoke | 2 | 0 | 2 | 34786 / 2146 | 0 |
| USD依赖元数据 | 0 | 0 | 0 | 0 / 0 | 0 |
| 正式Ready2主研究 | 758 | 0 | 70 | 1779647 / 74816 | 0 |

合计889次已完成/889次预留物理尝试、113次真实模型调用，输入2782391、输出119197tokens，usage未知调用0。失败与停止成本保留，不把未用预算算成消耗。这是本轮任务书范围，历史Alpha和更早PPO研究不池化计分，也不声称这是项目全部历史成本。

主研究118次学习（Feedback54、Template64）+640查询=758次；758000控制步、3032000任务物理子步=15160模拟秒，另151600个Ready子步=758秒，共15918秒。全阶段任务3387400子步=16937秒，Ready174200子步=871秒；启动/内部未暴露子步未伪造计入。

主研究实际模型累计耗时NoFeedback124.90秒、Feedback943.67秒；主研究56个native均退出0，已知原生进程时长合计63253.36秒；全阶段87个native中已知累计68970.82秒，4个早停进程退出或耗时未完整记录。并发、模型等待和启动退出均在其中，不能叫GPU独占小时；CPU重算与归档也不是额外物理回合。货币费用unknown。缓存是输入子集：NoFeedback缓存97920、Feedback缓存646272tokens；服务原始usage实际报告本批cache-write为0；未暴露或缺失的其他费用信息仍保持unknown。

全分阶段明细：[all_incurred_costs.json](../evidence/esl-reliability-20261030/final/all_incurred_costs.json)。

## 固定身份、实际命令与复核入口

本次主研究请求模型`gpt-6.1-terra`，实际CLI版本`codex-cli 0.166.0`；不暴露的effort、服务fingerprint和基础权重SHA保持unavailable。每方法每block预算10次调用、300000输入/48000输出tokens，单次120秒，自动provider/physics重试均0。学习4条lane、查询8条lane（4 GPU，每卡2查询进程），这是结果产生前的资源登记。每block自己的starter、空记忆、支持流与会话独立；并不声称服务权重在窗口内有不可变哈希。

公开上下文指令SHA为`cfcf29c2d36b31d8720287a417cd61369bbef6b1dee38a81eabed3b58cda3554`，context契约SHA为`a24b1043809550e2336a38f88e75ebd6f54399a094f98514f9bb62bd8777a71c`。全部产物冻结于2026-10-30 11:27:54 UTC；末个query进程结束于13:45:59 UTC；注册执行自审完成于14:01:09 UTC。

Arena固定`c7edf3a9d5d8276565208f72422f8f8a0806d6cf`，Lab固定`91a0906f93802eb859192dcb0bca879f891e92d6`，受跟踪源码均未改动。原生实际安装为IsaacSim6.1.0.0、IsaacLab17.0.2、isaaclab_physx6.0.0、Torch2.11.0+cu128、RSL5.4.1、Warp1.16.0、numpy2.3.1，记录见[实际分发包与模块来源](../evidence/esl-reliability-20261030/native_distributions.json)。

23个已解析USD依赖层用序列化USDA内容SHA记录，**不是原始USD二进制字节SHA**；非layer纹理/MDL内容没有完整哈希，OmniPBR.mdl未由只读解析器解析。依赖快照SHA为`a477d5f00db7b6909b026d88313a7d104fe61c89f535a9b13267dcb578f7b827`，在研究登记时绑定。它提高同机资产可核对性，不建立完整资产或第二机器等价性；元数据完整性检查也不冒称重新加载了原始资产物理场景。

实际主研究命令（退出0；56个native子进程均退出0）：

```bash
PHYSICALEVOBENCH_CHECKPOINT=/__not_available__/unused-policy.pt \
uv run physicalevobench-core replicate \
  --qualification configs/reliability/qualification.json \
  --output /home/dell/peb-esl-replication-20261030-002 \
  --gpus 0,1,2,3 --query-lanes-per-gpu 2
```

这里故意指定不存在的checkpoint路径；真实状态技能仍完成学习与查询。21个关键执行文件、starter/强参考与profile内容绑定的资格卡可在无历史Git对象的新源码目录使用，不靠手改SHA取得资格。实际新目录源码包为[/home/dell/peb-esl-ready2-source-aefd795.tar.gz](/home/dell/peb-esl-ready2-source-aefd795.tar.gz)（347551字节）。新CPU环境36项契约测试通过；仓库完整135项CPU测试及Ruff均通过，[命令与退出码](../evidence/esl-reliability-20261030/validation_commands.json)、[最后一次代码检查](../evidence/esl-reliability-20261030/final_cpu_checks.json)。CPU通过本身不是物理成绩。

主研究的注册执行源码固定为`aefd795`；后续读取/导出、故障路径修正和审计阶段进度提示属于交付代码，不能冒称主研究用最终分支HEAD执行。未见方法故障的本批正常路径保持注册源码结果，独立读取必须逐项与原结果一致。

默认只获取轻量源码；可选[固定工程样例](../evidence/esl-reliability-20261030/minimal-sample/manifest.json)总3121455字节，包含一条预先指定的stdin完整工程运行及准确源码，不按主研究高分选样。按[Quickstart](../reliability/QUICKSTART.md)可只增加这一稀疏目录，再用CPU执行：

```bash
uv run python -m physicalevobench.core.delivery verify \
  --evidence docs/evidence/esl-reliability-20261030/minimal-sample \
  --output /absolute/path/new-sample-extraction
```

该文档路径已实际执行、退出0，见[固定样例重算收据](../evidence/esl-reliability-20261030/minimal_sample_audit.json)。单条样例不替代完整研究审计。改变实际PhysX质量而保持GPU缓存/请求正确的篡改副本被独立审计拒绝，见[真实模型不一致拒绝证据](../evidence/esl-reliability-20261030/tamper_actual_model_rejection.json)；未改原始文件。

完整原始证据包目前保留在本地，尚未上传新的公共下载地址；不默认下载，不含许可资产或权重：

| 包 | 本地路径 | 主要范围 |
|---|---|---|
| 主研究 | [/home/dell/peb-esl-reliability-main-evidence-20261030](/home/dell/peb-esl-reliability-main-evidence-20261030/manifest.json) | 758次物理尝试、70次模型调用；数据归档2073882317字节，另附准确源码与SHA256SUMS |
| 诊断/工程 | [/home/dell/peb-esl-reliability-engineering-evidence-20261030](/home/dell/peb-esl-reliability-engineering-evidence-20261030/manifest.json) | 诊断、资格、停止批次、两版stdin与资产元数据；数据归档247646548字节 |

诊断/工程包已在独立目录提取并重算，见[收据](../evidence/esl-reliability-20261030/engineering_bundle_audit.json)。收据保留Ready-002无效负例注入的conformance FAIL，以及停止/设置失败状态，不把“证据可审计”改写成“实验成功”。

全研究摘要与逐条件表均可直接检查：[注册](../evidence/esl-reliability-20261030/final/registration.json)、[完整结果](../evidence/esl-reliability-20261030/final/results.json)、[640行分配成绩CSV](../evidence/esl-reliability-20261030/final/per_condition.csv)、[实际图差异](../evidence/esl-reliability-20261030/final/artifact_differences.json)、[目标×质量](../evidence/esl-reliability-20261030/final/goal_mass_cells.json)、[实测初态多样性](../evidence/esl-reliability-20261030/final/measured_reset_diversity.json)。导出表也已逐项与注册结果核对，640条分配无重复、每方法128条，真实模型质量列最大偏差约5.96×10⁻⁹kg，见[表格对账](../evidence/esl-reliability-20261030/final/table_reconciliation.json)。完整离线核验无需GPU：

```bash
uv run python -m physicalevobench.core.delivery verify \
  --evidence /home/dell/peb-esl-reliability-main-evidence-20261030 \
  --output /absolute/path/new-main-extraction
```

这里的独立指新目录重新提取和读取，不是外部团队或第二套评分实现。本轮实际独立核验通过`core.delivery.verify`调用完成，须以独立提取文件重新计算物理指标、冻结身份、公共状态动作、分母与分层统计，并精确对比注册执行结果；不只核对已有汇总JSON或归档SHA。最终状态见[独立提取全量重算收据](../evidence/esl-reliability-20261030/final/independent_extracted_main_audit.json)及[一致性摘要](../evidence/esl-reliability-20261030/final/independent_main_audit.json)。

本轮保留锚点，不按结果扩大任务或追加学习。需要继续区分“更多推理机会”与“物理反馈信息”时，应另登记DeliberationOnly-9比较；需要证明物理上下文适应时，应先验证新的theta确实要求经验，而非再修改当前starter制造差距。这两项均不是本轮已完成结论。[PR #11](https://github.com/ros-claw/PhysicalEvoBench/pull/11)保持草稿，[CI状态](https://github.com/ros-claw/PhysicalEvoBench/pull/11/checks)单独可查；PR #10和旧Alpha不改动，没有合并或新release。
