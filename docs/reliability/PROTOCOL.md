# ESL reliability / replication：实施登记

历史Alpha、旧全部分数、public-context-v3提示与公开采样保留。工程可用、测量可靠、算法有效分别判定；零/负算法收益不使基准失败，审计通过不使方法成绩自动可信。新物理初始化采用新执行/任务版本，不能池化旧pilot。

A的资源上限48个短物理尝试。第一批18个固定关节/开指、无接近试验：A=旧扩展异常seed315924514，B=旧新目录异常seed903479326，N=预先指定正常light seed1132640734；三种循环顺序×有/无额外readback，三槽位。首次调度在并发源码导出时失败：已完成9个保留，仅原先未启动的9个在独立目录恢复，注册条件不变。18个均未复现穿桌，不据此判为普通随机噪声，也不认定根因。

Episode Ready候选 `support-probe-restore-1`：新任务 `core-place-public-v4-ready1`。物理步长、控制、质量、目标与评分不变；开启PhysX scene query和cube支撑传感器，字段仅evaluator。每次首次参与者动作前，固定200物理子步（1s）保持原始关节目标/开指，测运行时table shape ray hits、实测支撑/运动与参数。之后恢复同一注册初态的关节/物体位置速度与朝向，不重随机、不再写质量；任务20s从恢复后开始。预演物理成本单列。探测改变solver/contact历史，故是新执行版本，不能假称旧初态分布完全未变。预演不得使用候选、任务成败或未来query表现筛选条件。

Ready conformance：4正常尝试（含异常原seed、轻重质量及同进程reset）+2显式关闭table collision的注入负例，全部固定关节。负例只验证可检测边界，不是自发故障根因的复现。无重试，6个尝试计入A短诊断；0模型调用。场景有效性和参考可达性另判：新执行需14个参考资格回合（starter4、strong4、identity4、open2），不要求学习方法赢。

B的提示、schema、compaction与推理/物理上限保存在 `configs/reliability/public_context_v3.json`。原CLI未暴露effort/fingerprint，不虚构固定权重哈希；保留原调用参数。服务鉴权/不可用/传输/未知deadline/usage缺失与合法输出/预算错误分开。provider和物理的自动retry上限均0；失败尝试保留，usage unknown不填0。

D：仅在Ready边界及新执行参考资格通过后，冻结全部执行、说明、搜索模板、方法与统计协议。固定8个独立learning block，support4，query16=2目标×2质量×4独立reset抽样；五组Frozen/NoFeedback/TemplateSearch-4/Feedback/Deletion；模型标识gpt-6.1-terra，空记忆正常starter；10calls/300k input/48k output/120s每调用，Feedback最多8实践，模板4×共同2条件=8。主比较命名budget-cap comparison，允许提前冻结，记录实际计算，不声称完全隔离反馈因果作用。全部block全部产物先冻结，再运行query。

学习/查询任务回合最多768=8×(8+8)+8×16×5。每任务分配另有200子步Ready成本，明确不算任务/算法实践控制步。任何INIT_INVALID均发生在参与者第一次动作之前，记录物理尝试/子步、不产生成功标签；此study不自动重试、不换seed。无法获得合法执行的条件在全分配口径不算成功；有效执行任务率另报。配对效果只在五方法均有合法执行的同一条件集计算；同时保留各方法全部分配尝试的完成率、基础设施率及缺失，不仅展示过滤分数。未知运行期掉落仍保留任务失败或UNKNOWN，不能自动算基础设施。provider故障导致block/method不完整，不能当非法图记0技能能力；参与者非法/超预算保留方法固定分母。

按block平衡模型方法顺序和query方法进程顺序；每个arm内query条件也用预登记轮换，分离首槽位和具体条件。冻结前登记所有条件/顺序/源码/预算，不按分数停止、换提示或追加。固定GPU共享原生进程，不改变他人作业。统计以block为最外层，保留全部逐block点；以条件cell分层、方法配对重采样作分层区间。identity用逐条件discordance，不用净成功差作为唯一噪声。N=1旧pilot只作小样本诊断，不合成新N。

稀疏B=2/4/8快照可以不增加调用地留档，但本轮不运行额外256回合曲线；未测部分不画成绩。DeliberationOnly-9为独立具名诊断，若运行必须在开始前单独登记，不混入上述768，不按主结果好坏决定追加。跨任务扩展不在本轮实施范围。

剥离PPO依赖使用 `state-program-reference-1` / `state-execution-skill-1` 与执行配置哈希，不能把新identity伪称旧checkpoint SHA；旧权重接口兼容保留。第二stdin adapter、同机新目录物理接入单列；没有第二台机器或独立外部人时如实未验证。新发布/合并不在本任务自动授权范围；既有Alpha与PR保持原状态。本轮先创建可审查feature PR，最终报告 `docs/implementation/ESL_RELIABILITY_REPLICATION_REPORT.md`。

在主研究读取结果前固定资源安排：学习阶段每GPU一条lane（同时最多4条模型/原生学习流程）；查询阶段每GPU两条lane（最多8个独立原生进程，每block/arm仍新进程）。现有共享GPU约13–18GB常驻占用，余量充足；不修改他人作业。记录每次进程的GPU负载、时长和顺序。并发只改变墙钟调度，不改变物理dt、任务时长、动作或评分；其可见的重放差异保留，不能声称GPU独占或确定性。

## 执行纠正：Ready2（查询前的物理测量阻断）

Ready1的8-block尝试在任何query启动前停止：固定支撑预演发现真实下落；进一步对质量切换读回，PhysX模型仍为0.1kg，而GPU shadow/请求为0.4kg，惯量亦有不一致。独立6个短参数传输诊断复现了该区别，同值同步重写后真实模型读回恢复一致。固定Lab的indexed setter把GPU数据异步复制到pinned CPU scratch，紧接着让PhysX CPU setter消费；不能拿GPU shadow当真实模型读回。这批已发生的学习、物理与41次模型调用全部单列保留，不作为算法零分，不挑有效block回收，不运行其query。

纠正保留原题与public-context-v3字符串/采样/预算。新profile `support-probe-restore-2`、任务/执行版本 `core-place-public-v5-ready2`：仅在Cube RigidBodyView.set_masses/set_inertias之前加当前上下文的Warp device fence，使既有CPU数据和index scratch传输完成，不改采样、质量、惯量比例、dt、控制或评分，不改固定Arena/Lab源码。Ready在预演前/后及恢复后从PhysX模型get_masses/get_inertias独立读取，核对请求与GPU缓存；缺失/不一致不得READY。旧Ready1资格与数据保留，不能凭其缓存审计给新版本正式资格。

新6回合正常/故障注入将使A短诊断总计42（18+6+6+6+6），仍不超过48。新版本另做14回合参考资格，之后从空记忆/starter开始新的固定8-block cohort；8-block的128实践+640查询上限与早停规则保持。被停止的Ready1成本作为测量故障的工程尝试另列，不偷塞为新正式研究成功样本；不补用其产物，不在新query看到成绩后修改规则。所有已发生开销都需在最终报告汇总。
