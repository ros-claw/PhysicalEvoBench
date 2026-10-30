"""Local implementation report led by the learning question and actual outcomes."""

import argparse
import json
from datetime import datetime
from pathlib import Path

from physicalevobench.core.program import Program
from physicalevobench.development.place import starter_program


def read(path):
    return json.loads(Path(path).read_text())


def costs(studies):
    total = {'physical_episodes': 0, 'control_steps': 0, 'physics_samples': 0,
             'native_processes': 0, 'native_process_minutes': 0., 'infrastructure_failures': 0,
             'limited_controls': 0, 'hard_boundary_episodes': 0, 'position_violation_episodes': 0}
    conditions = set()
    by_study = []
    for study in studies:
        count = 0
        for identity in sorted(study.rglob('source_identity.json')):
            native = identity.parent
            total['native_processes'] += 1
            process = read(native/'process.json') if (native/'process.json').exists() else {}
            if process.get('returncode') not in (0, None):
                total['infrastructure_failures'] += 1
            if process.get('finished_at'):
                total['native_process_minutes'] += (datetime.fromisoformat(process['finished_at'])-
                    datetime.fromisoformat(read(native/'launch.json')['started_at'])).total_seconds()/60
            ledger = native/'episodes.jsonl'
            if not ledger.exists():
                continue
            rows = [json.loads(line) for line in ledger.read_text().splitlines()]
            for i, row in enumerate(rows):
                count += 1
                total['physical_episodes'] += 1
                total['control_steps'] += row['steps']
                total['physics_samples'] += row['diagnostic']['physics_samples']
                total['hard_boundary_episodes'] += row['diagnostic']['hard_boundary_terminated']
                total['position_violation_episodes'] += row['diagnostic']['first_violation'] is not None
                job = read(native/'requests'/f'{i:03d}.json')
                c = job['condition']
                conditions.add((c['seed'], c['object_mass_kg'], tuple(job.get('public_goal', []))))
                from physicalevobench.v02.audit import records
                controls = records(native/'episodes'/row['episode_id']/'controls.jsonl.gz')
                total['limited_controls'] += sum(bool(c['limited_joints']) for c in controls)
        by_study.append({'study': study.name, 'completed_episodes': count})
    total['distinct_physical_conditions'] = len(conditions)
    total['by_study'] = by_study
    return total


def report(learning, qualification, studies, output):
    q = read(qualification)
    results = read(learning/'results.json') if learning and (learning/'results.json').exists() else None
    total = costs(studies)
    lines = ['# PhysicalEvoBench：研究纠偏与有效学习题实施报告（2026-10-30）', '',
             f"**当前学习题资格：{q['status']}。** 本轮研究的是“正常抓取/搬运程序能否通过实践形成有效释放程序，并用于新目标位置”。这与旧饱和 T0 参数题不同；新程序使用公开目标和真实开度/速度守卫，旧失败未补记为通过，也不能把旧0/4与新2/4当成Agent学习增益。", '',
             '## 1. 哪道题成立了，证据是什么', '',
             '| 资格对照 | 成功/回合 |', '|---|---|']
    for name, scores in q['scores'].items():
        lines.append(f'| {name} | {sum(scores)}/{len(scores)} |')
    lines += ['', f"普通起点与强参考相差 {q['strategy_gap_count']} 个成功，同参考 identity 相差 {q['identity_gap_count']} 个。新目标参考检查是题目可达性，不能作为 Agent 泛化成绩。资格只覆盖当前版本的有限条件；不是学习效应显著性的检验。", '',
              'DEV 响应表：第一批 starter/open/settle/settle_open 各1/2；移除先失接触的死锁条件后，在两方向、两质量上 starter2/4、actual-aperture4/4。严格低速条件可能到19.7s才满足，赶不上后续释放。以上均为开发者干预。', '',
              '旧事件对齐发现：开始张爪时仍有明显横向速度，进入撤离时真实指坐标未必达标。单侧接触可以在开度完成后持续，因此不能要求接触必须先归零。没有将某个因素认定为唯一原因。支撑接触、切向力、solver真实力矩仍 not_measured。另行CPU解析作者碰撞几何：场景Cube半高约.024m，桌面碰撞Mesh顶面约-.003m，几何预期落稳中心.021m与轨迹一致；这不是live cooked hull或支撑力测量。USD visual/proxy AABB 不等于碰撞形状或桌面支撑平面；公开目标中心Z=.021通过真实落稳可达性验证，不从reset中心推断支撑面。', '',
              '## 2. Agent 看什么、改什么、继承什么', '',
              '所有方法使用相同正常 starter、固定 IK/驱动/动作包络。新固定执行协议依据实测双指接触启用既有有界积分，失接触以0.2s平滑卸载；不由phase名字控制。这是开发者公开执行协议修复，不能计为 Agent 学习。旧 phase 协议保留供历史复现。', '',
              '允许 graph-v2 最多16节点/64转移/2恢复、公开 frame 相对目标与 AND/OR 状态比较。真实位置、物体速度、双指坐标、指物法向力、目标公开；质量、seed、条件ID和查询结果不进入参与者。模型自行选实践句柄，可改完整程序或不改；没有开发者代写诊断反馈。', '',
              '强参考单独用于题目资格，未注入模型上下文。测试只加载冻结程序，模型调用为零，文本memory是来源记录，不参与执行。本轮是 Executable-Skill Learning，不是在线具身 Agent 全能力测评、权重自更新或文本记忆理解测评。', '']
    if results:
        lines += ['## 3. 同模型无反馈与有反馈分别做了什么', '',
                  '| 学习实例 | Frozen | No-Feedback | Score Search | Feedback | 删除经验 |',
                  '|---|---|---|---|---|---|']
        for instance in results['instances']:
            cells = [str(instance['learning_instance'])]
            for name in ('frozen', 'designer', 'search', 'feedback', 'deletion'):
                scores = instance['scores'][name]
                cells.append(f'{sum(scores.values())}/{len(scores)}')
            lines.append('| '+' | '.join(cells)+' |')
        lines += ['', '无反馈与反馈使用相同模型和计算上限。无反馈只 revise/freeze，不能调用物理实践；反馈组可读真实事件/轨迹片段后再次提案。所有实例全部冻结后才运行查询，新原生进程读取持久产物。', '']
        reg = read(learning/'registration.json')
        for i in range(reg['instances']):
            for name in ('designer', 'feedback'):
                directory = learning/f'instance-{i}'/name
                proposals = sorted(directory.glob('proposal-*.json'))
                if (directory/'validity_failure.json').exists():
                    lines.append(f"实例{i} {name}：参与者有效性失败，原因 `{read(directory/'validity_failure.json')['reason']}`；按固定查询分母记零，未当成物理任务失败。")
                    continue
                prior = starter_program().to_dict()
                changes = []
                for proposal in proposals:
                    value = read(proposal)
                    program = json.loads(value['program_json'])
                    old = {n['id']: n for n in prior['nodes']}
                    changed = [n['id'] for n in program['nodes'] if old.get(n['id']) != n]
                    changes.append(f"{proposal.stem}:{value['tool']}[{','.join(changed) or '保持'}]")
                    prior = program
                art = read(directory/'artifact.json')
                lines += [f"实例{i} {name}："+' → '.join(changes)+f"。冻结程序 `{Program.from_dict(art['payload']['skill']).sha256[:12]}`，实际实践 {art['payload']['budget_used']} 回合。", '']
        lines += ['## 4. 新条件作用与经验删除', '']
        for instance in results['instances']:
            lines.append(f"实例{instance['learning_instance']}：反馈相对无反馈 {instance['feedback_gain']['gain']:+.2%}；反馈相对删除经验 {instance['artifact_gain']['gain']:+.2%}。")
        for key, interval in results['paired_conditional_intervals'].items():
            lines.append(f"{key} 平均差 {interval['difference']:+.2%}，条件bootstrap95%区间 [{interval['interval'][0]:+.2%}, {interval['interval'][1]:+.2%}]。")
        lines += ['', '这些区间固定了两条学习轨迹，只重采样各自查询条件；不能推断学习总体稳定性。删除经验恢复精确starter，是持久程序依赖对照，不是新增独立学习实例。同程序 Frozen/删除重放差异用于观察噪声，不能算进化。', '',
                  '`command_response.json` 用相同公开观测重算新旧程序命令差异，并另报真实执行层限幅。命令映射反事实不冒充另一条物理轨迹。跨任务迁移、共享技能保持、在线 Agent/纯视觉/真机均 NOT_RUN。', '',
                  '## 5. 实际费用与风险', '',
                  '| 实例/方法 | 调用 | 输入tokens | 输出tokens |', '|---|---|---|---|']
        for instance in results['instances']:
            for name, cost in instance['model_cost'].items():
                lines.append(f"| {instance['learning_instance']}/{name} | {cost.get('calls','unknown')} | {cost.get('input_tokens','unknown')} | {cost.get('output_tokens','unknown')} |")
        lines += ['', 'Search实际每实例8回合，4候选均在相同两个支持条件比较；它是有限提案族，不能代表整个图空间最强优化器。两模型方法上限相同，实际花费不同，不宣称费用完全匹配。因此反馈组与无反馈组的差异是该预算下两种完整过程的比较，不能单凭这一次对照把额外实际推理的贡献排除掉。模型冷启动/等待保留于每次process记录；原生进程墙钟含加载、共享GPU干扰和等待，不等于独占GPU计算时间。', '']
    else:
        lines += ['## 3–5. 学习与对照', '', '**NOT_RUN**：当前没有完成实际方法比较，不能依据接口或开发响应宣称学习能力。', '']
    lines += [f"本轮实际共 {total['physical_episodes']} 物理回合、{total['distinct_physical_conditions']} 个不同物理条件、{total['control_steps']} 控制步、{total['physics_samples']} post-physics样本。{total['native_processes']} 个原生进程（含失败）合计 {total['native_process_minutes']:.3f} 进程分钟。", '',
              f"执行层干预 {total['limited_controls']}/{total['control_steps']} 步；硬边界事件 {total['hard_boundary_episodes']} 回合，注册位置违规 {total['position_violation_episodes']} 回合。基础设施失败 {total['infrastructure_failures']} 次；已知几何记录错误发生于第一物理回合之前，0回合，失败日志保留。0 PPO transitions。", '',
              '## 6. 外部入口与交付边界', '',
              '新目录 `/home/dell/peb-esl-fresh-20261030-001` 已完成真实T0 smoke：1回合、500控制步、成功。没有T1/B1/PPO历史依赖。新CPU venv及独立源码目录，原生环境和缓存复用本机固定安装、模型在仓库外；不宣称另一台机器或全新原生安装验证。', '',
              '入口：`physicalevobench-core physical-smoke`、`qualify`、`learn`、`audit`；标准JSON provider无需ROSClaw。源码/任务卡/轻量资格文件不携带完整历史轨迹或权重，原始数据独立打包。离线审计不产生新学习或物理证据。', '',
              '历史1027报告与停止记录保持不变。新版本的可用性与自进化有效性分开：零或负收益可以是正确协议的结果；跨学习稳定进化仍未证明。feature PR供审阅，不自动合并或发布acceptance release。', '',
              '附录：本机分项成本和每次预留、原始过程、源快照、产物/动作绑定审计见证据包；正文不以哈希或CPU数量替代物理学习结论。', '']
    Path(output).write_text('\n'.join(lines))
    return total


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--learning')
    p.add_argument('--qualification', required=True)
    p.add_argument('--studies', nargs='+', required=True)
    p.add_argument('--output', required=True)
    a = p.parse_args()
    print(json.dumps(report(Path(a.learning) if a.learning else None, Path(a.qualification),
                            [Path(s) for s in a.studies], Path(a.output)), indent=2))


if __name__ == '__main__':
    main()
