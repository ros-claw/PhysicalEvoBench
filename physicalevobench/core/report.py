"""Local implementation report, with explicit incomplete gates and actual costs."""

import argparse
import json
from datetime import datetime
from pathlib import Path

from physicalevobench.v02.audit import records
from physicalevobench.core.metrics import lift_followup
from physicalevobench.doctor import save_json


STUDIES=[
 ('B1 参数空间','peb-core-b1-20261027-001'),
 ('P 首个模型闭环','peb-core-pilot-20261027-002'),
 ('T1 初版开发','peb-core-place-dev-20261027-003'),
 ('T1 唯一修正','peb-core-place-dev-correction-20261027-001'),
 ('T1 独立确认','peb-core-place-confirm-20261027-001'),
 ('两任务流程','peb-core-flow-20261027-001')]


def read(path):
    return json.loads(path.read_text())


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def generate(root,parent,output,final=False):
    table=[]
    total=steps=samples=processes=0
    conditions=set()
    costs=[]
    violations=hard=0
    peaks={}
    duration={}
    native_wall=0.
    for title,name in STUDIES:
        study=parent/name
        if not study.exists():
            table.append(f'| {title} | '+('NOT_RUN_GATE_FAILED' if final else '尚未启动')+' | 0 | — |')
            continue
        status=read(study/'status.json')
        reg=read(study/'registration.json')
        data=[]
        for path in study.rglob('episodes.jsonl'):
            meta=read(path.parent/'control_semantics.json')
            for row in rows(path):
                data.append(row)
                state=read(path.parent/'episodes'/row['episode_id']/'initial_state.json')
                conditions.add((state['condition']['seed'],state['condition']['object_mass_kg']))
                for n,depth,span in zip(meta['joint_names'],row['diagnostic']['maximum_joint_depths'],
                                        row['diagnostic']['violation_durations_s'],strict=True):
                    peaks[n]=max(peaks.get(n,0.),depth)
                    duration[n]=duration.get(n,0.)+span
        n=len(data)
        total+=n
        steps+=sum(r['steps'] for r in data)
        samples+=sum(r['diagnostic']['physics_samples'] for r in data)
        violations+=sum(r['diagnostic']['first_violation'] is not None for r in data)
        hard+=sum(r['diagnostic']['hard_boundary_terminated'] for r in data)
        for launch in study.rglob('launch.json'):
            processes+=1
            receipt=launch.parent/'process.json'
            if receipt.exists():
                start=datetime.fromisoformat(read(launch)['started_at'])
                finish=datetime.fromisoformat(read(receipt)['finished_at'])
                native_wall+=(finish-start).total_seconds()
        for name2 in ('model_calls','S_model_calls'):
            if (study/name2/'budget.json').exists():
                costs.append({'stage':title,**read(study/name2/'budget.json')})
        table.append(f'| {title} | {status["status"]} | {n}/{reg["physical_budget"]} | `{reg["source_commit"][:12]}` |')
    cancelled=[]
    for p in sorted(parent.glob('peb-core-*/status.json')):
        value=read(p)
        if value['status']=='CANCELLED_BEFORE_LAUNCH':
            cancelled.append({'study':p.parent.name,'episodes':value['actual_episodes'],'reason':value['reason']})
    ledger={'schema':'core-implementation-costs-1','episodes':total,'control_steps':steps,'physics_samples':samples,
            'unique_conditions':len(conditions),'native_processes':processes,'native_wall_minutes':native_wall/60,
            'registered_violation_episodes':violations,'hard_event_episodes':hard,
            'maximum_joint_depths':peaks,'violation_durations_s':duration,'model_costs':costs,
            'preflight_model_cost':{'calls':1,'input_tokens':13507,'output_tokens':15},
            'cancelled_before_launch':cancelled,'new_PPO_transitions':0,
            'scope':'Actual stage costs, independent condition/replay distinction; native runtime includes loading and shared GPU waiting.'}
    save_json(root/'runs/core-cost-ledger-20261027.json',ledger)
    pilot=parent/'peb-core-pilot-20261027-002/pilot_results.json'
    ptext='真实 Agent 的独立测试与离线核验尚在执行，不能提前填成绩。'
    if pilot.exists():
        p=read(pilot)
        pt=['| 方法 | 成功/回合 | 可执行技能 SHA256（前12位） |', '| --- | --- | --- |']
        for a,title in [('frozen','Frozen'),('search','Score-only Search'),('feedback','Feedback Agent'),('ablation','移除新增经验')]:
            v=p['arms'][a]
            pt.append(f'| {title} | {v["successes"]}/{v["episodes"]} | `{v["skill_hash"][:12]}` |')
        pt+=['',f'Feedback 相对初始参考：**{100*p["feedback_vs_initial"]["gain"]:+.1f} 个百分点**；'
             f'相对经验删除对照：**{100*p["artifact_contribution"]["gain"]:+.1f} 个百分点**。',
             '', '这是 **1 条反馈学习轨迹、1 条搜索轨迹、4 个配对留出条件**；没有跨学习运行的置信保证。'
             '初始与经验删除控制器相同，其重放差异不能归为学习。']
        followup={}
        followup_table=['| T0 方法 | 瞬时到达 | 有效持稳 | 终态合格 | 首次合格后离开目标 |',
                        '| --- | --- | --- | --- | --- |']
        for arm in ('frozen','search','feedback','ablation'):
            worker=pilot.parent/('test-'+arm)
            entries=[]
            for row in rows(worker/'episodes.jsonl'):
                values=lift_followup(records(worker/'episodes'/row['episode_id']/'physics.jsonl.gz'))
                if values['effective_hold']!=row['success']:
                    raise ValueError('T0 additive followup changed the registered primary outcome')
                entries.append({'condition_id':row['condition_id'],**values})
            followup[arm]=entries
            counts=[sum(e[k] for e in entries) for k in ('instant_arrival','effective_hold','terminal_eligible','left_goal_after_first_hold')]
            followup_table.append('| '+arm+' | '+' | '.join(f'{n}/4' for n in counts)+' |')
        save_json(pilot.parent/'lift_followup.json',{'schema':'core-T0-followup-report-1','arms':followup})
        pt+=['','\n'.join(followup_table),'','有效持稳表示曾连续合格0.30秒，不保证此后始终留在目标内；以上为追加观测，没有更改主成绩。']
        ptext='\n'.join(pt)
    ttext=[]
    for title,name in STUDIES[2:]:
        path=parent/name/'place_results.json'
        if path.exists():
            v=read(path)
            ttext.append(f'- {title}：正对照 {v["positive"]["successes"]}/{v["positive"]["episodes"]}，'
                         f'张爪对照 {v["negative"]["successes"]}/{v["negative"]["episodes"]}；'
                         f'开发资格 `{v.get("development_qualified")}`，独立门槛 `{v.get("independent_gate_passed")}`。')
    flow=parent/'peb-core-flow-20261027-001/flow_results.json'
    if flow.exists():
        f=read(flow)
        ft=['| 方法 | 零额外学习迁移收益 | T1 学习收益 | T0 保持变化 |','| --- | --- | --- | --- |']
        for m,c in f['changes'].items():
            ft.append(f'| {m} | {100*c["zero_learning_transfer"]["gain"]:+.1f} pp | '
                      f'{100*c["T1_learning_gain"]["gain"]:+.1f} pp | {100*c["T0_retention_change"]["gain"]:+.1f} pp |')
        ttext+=['','\n'.join(ft),'','T0→T1 是参数经验复用；T1 阶段才开放程序更新。两阶段继承同一学习轨迹，不能计作两次独立学习。']
    else:
        ttext+=['','T1 开发预算12已用尽，两种方案分别0/4；独立确认、真实 S Agent 学习、跨任务迁移与保持均为 `NOT_RUN_GATE_FAILED`，没有成绩。']
    status_summary=('**本轮按登记的停止条件结题：真实 Agent 单任务闭环通过；P 学习空间未确认，T1 参考失败。正式两任务 Core 未验收、未发行。**'
                    if final else '此文件记录执行进度；未完成阶段明确标注，不能提前宣布验收通过。')
    model_table='\n'.join(['| 参与者计算 | 调用 | 输入 tokens | 输出 tokens |','| --- | --- | --- | --- |']+
                          [f'| {c["stage"]} | {c["calls"]} | {c["input_tokens"]:,} | {c["output_tokens"]:,} |' for c in costs]+
                          ['| 单独连通预检（非学习） | 1 | 13,507 | 15 |'])
    text=f'''# PhysicalEvoBench Core 实施报告（2026-10-27）

{status_summary}

本轮将目标转为方法中立的 Benchmark Alpha：真实模型提出候选、按预算执行物理试验、冻结产物、
由新实例独立测试，并与 Frozen、同预算上限搜索及经验删除对照比较。
P 赛道的学习效果与 S 赛道的程序学习分开报告；不能把接口跑通称为稳定自进化。

## 1. 研究契约与版本

研究问题、观测范围和统计单位见 [Benchmark Card](../../BENCHMARK_CARD.md)。
T0 保留 `state-reference-h10-v1` 的10秒及0.30秒持稳规则。T1 为独立的
`core-place-h20-v2-dev`：物体搬运后释放，在目标区域低速稳定0.50秒。
初始重置中心高度0.055m不是桌面支撑高度；T1 在任何原生执行前已改为公开目标中心 z=0.021m。
没有修改历史五秒失败或旧十秒参考成绩，也没有重新启动 PPO。

- P：两个合法参数，正常 v2 起点；本轮 B1 的参数成功范围3–4/4，身份重放也是3–4/4，故仅作接口 smoke。
- S：受限 JSON 技能图与任务库，可编辑目标、抓取判断、分支、释放及有界恢复；底层 IK、驱动和目标限速固定。
- 标签：模拟物理、状态观测、单机械臂、固定模型身份、持久可执行产物；不声称纯视觉或真机。

## 2. 方法、起点与预算

三种方法共享正常初始参考和同赛道接口。Feedback 使用实际 `gpt-6.1-terra` / Codex CLI，
也提供不依赖 ROSClaw 的通用 stdin/stdout 适配器。模型返回结构化工具请求，由评测端执行；
质量真值、seed 和留出结果不进入请求。测试期间模型调用为0，按冻结技能运行反应式控制。
API 白名单和只读进程不等于抵御恶意参赛者的安全沙箱。

本轮上限148回合：B1 48、T0 pilot32、T1开发12、独立确认12、任务流44。
Agent 可以提前冻结，因此“相同上限”不等于相同实际开销。P 首轮模型四次训练均成功后冻结
`approach_clearance_m=0.1161`、`minimum_close_s=0.40`；没有发生失败诊断或反馈后参数修正。
实际模型调用5次，输入84,474、输出371 tokens。单独连通预检1次（13,507/15 tokens）不计为学习。

## 3. 实际阶段与独立学习轨迹

| 阶段 | 状态 | 已记录回合/登记上限 | 原生源码 |
| --- | --- | --- | --- |
{chr(10).join(table)}

本轮每方法只有1条 P 学习轨迹。原计划 T1 继续继承该轨迹，但没有启动，不能计入学习样本。
完整产物身份覆盖参与者/模型、执行源码、技能、记忆、接口、任务、评分和实际学习预算；
另外报告可执行技能哈希，避免仅凭全文哈希不同宣称能力变化。

## 4. 任务成绩、学习收益、迁移与保持

{ptext}

{chr(10).join(ttext)}

T1 初版正对照0/4的失败保留。唯一四回合修正只改变新任务的释放程序：
张爪/退回期间保持现有有界积分反馈，张爪最短等待由0.35秒改为0.70秒。
这属于开发者的新任务可行性修正，不计为 Agent 学习；没有改成功阈值、时域或驱动。
任何后续任务流必须使用独立确认过的那份程序作为共同起点。

## 5. 经验归因、风险与成本

经验删除不重新训练，测试同样的条件、执行器和在线预算；P 测试只执行参数，文本记忆本身不参与控制。
预算曲线只有初始与实际冻结点，不能当成已测得完整0/16/32曲线。统计为有限 pilot 的描述结果，
不支持 Agent 优于搜索、跨独立学习稳定提高或通用递归进化。

本轮实际记录 **{total} 回合、{len(conditions)} 个不同物理条件、{steps:,} 控制步、{samples:,} 物理样本**。
原生进程{processes}个，累计进程墙钟{native_wall/60:.2f}分钟（含加载与等待，共享 GPU2，并非独占 GPU 计算量）。
登记坐标越界{violations}回合，严重边界事件{hard}回合；逐关节峰值/持续时间保存在成本账本及原始诊断。
接触只测法向分量，切向力和真实 solver 关节驱动力 `not_measured`；坐标未越界不等于完整安全。
B1 的早期掉落仍按任务失败计分，未证明其唯一原因，也未免费更换 seed 重跑。

{model_table}

共12个实际方法学习回合：Feedback4、Search8；没有 PPO 转移、权重更新或 S 模型学习。
实际冻结预算点为 Feedback0/4、Search0/8，不伪造预算8或16/32的未测快照。

## 6. 外部接入与三种复现声明

[参与者 Quickstart](../core/QUICKSTART.md) 提供：
`physicalevobench-core smoke`（CPU）、`run`（标准物理 pilot）、`audit`（离线核验）。
标准入口可复用轻量 B1 凭据，不要求先重跑校准或下载旧 PPO 数据。通用 provider 只实现 JSON 协议。

- 源码薄包约600 KiB的新目录/新虚拟环境已完成安装和初始10项 Core 测试；随后独立稀疏 checkout通过11项。
- 新稀疏目录准备了锁定的 Arena 工作树并复用原生运行时/资产缓存；因为 T1 门槛失败，**没有启动该目录的物理任务流，也没有完成新目录物理复跑**。
- 原始证据解包后的 CPU 重算是离线审计，不是新物理执行或新独立学习。最终审计收据单列交付。

NVIDIA 权重留在仓库外并保留独立许可，不随 Apache-2.0 项目代码或证据包分发。

## 7. 已证实、未证实与停止边界

已实现契约、预算登记、实际模型工具、冻结恢复、同接口基线、经验删除、受限程序及新任务评分。
各阶段是否已经取得物理证据，以本报告表格和独立审计为准。两任务门槛未过时不能宣布 Core 完成。
正式 Core 仍缺 T1 有效正参考、真实 S 学习比较、迁移/保持证据及新目录物理复跑。
P 的学习空间不足，不能仅凭四组满分把它宣布为已验证学习能力的正式基准。
算法正收益、优于搜索、稳定迁移和能力保持均未证实。
没有每轮必须接纳、每种子必须提高或某产品必须领先的验收规则。

零物理成本的取消登记、模型上下文限长修正及 B1 汇总文件就绪竞态均留有记录；
P 在任何模型学习或原生调用前退出的那次，仅恢复原登记和原条件，不算新学习种子或免费物理重试。
用户原始两份规格、所有旧负结果、每个新实际回合及失败均保留。
'''
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(text)
    return ledger


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--parent',default='/home/dell')
    p.add_argument('--output',default='docs/implementation/CORE_BENCHMARK_实施报告_20261027.md')
    p.add_argument('--final',action='store_true')
    a=p.parse_args()
    print(json.dumps(generate(Path.cwd(),Path(a.parent),Path(a.output),a.final),indent=2))


if __name__=='__main__':
    main()
