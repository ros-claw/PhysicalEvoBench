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


def report(primary, extension, prospective, context2, task_qualification, problem_qualification, reference_replay, studies, output):
    groups = [('原查询 / 两实例', primary, read(primary/'results.json')),
              ('组合查询 / 原两实例探索性扩展', extension, read(extension/'results.json')),
              ('组合查询 / 新目录初版上下文pilot', prospective, read(prospective/'results.json')),
              ('组合查询 / 新目录公开上下文v2 pilot',context2,read(context2/'results.json'))]
    q = read(problem_qualification)
    task_q=read(task_qualification)
    old_q_count=sum(map(len,task_q['scores'].values()))
    new_q_count=sum(map(len,q['scores'].values()))
    reference=read(reference_replay/'results.json')
    total = costs(studies)
    arms = ('frozen', 'designer', 'search', 'feedback', 'deletion')
    totals = []
    for label, directory, data in groups:
        counts = {name: (sum(sum(i['scores'][name].values()) for i in data['instances']),
                         sum(len(i['scores'][name]) for i in data['instances'])) for name in arms}
        totals.append(counts)
    lines = ['# PhysicalEvoBench：研究纠偏与有效学习题实施报告（2026-10-30）', '',
             '**已建立一个查询族经过物理资格验证的学习问题，并从新目录真实运行了标准学习入口。稳定自进化仍未证明。** 本轮测量的是固定模型标识与执行层下，Agent能否产出可复用的可执行技能。', '',
             '题目是 Place–Release Factorial v2：支持目标(.62,+.12)/(.60,-.12)，查询目标(.60,+.12)/(.62,-.12)，共享夹持/卸载机制，留出X/Y组合；质量类别重复但隐藏，reset seed分离。旧正常抓取/探升能力保留，未故意损坏原成功技能。', '',
             '| 证据组 | Frozen | 无物理反馈设计 | 共同条件搜索 | Feedback | 删除经验 |',
             '|---|---|---|---|---|---|']
    for (label, _, _), counts in zip(groups, totals, strict=True):
        lines.append('| '+label+' | '+' | '.join(f'{counts[n][0]}/{counts[n][1]}' for n in arms)+' |')
    lines += ['', f"探索组合中，Feedback对Frozen的表面差是{totals[1]['feedback'][0]/totals[1]['feedback'][1]-totals[1]['frozen'][0]/totals[1]['frozen'][1]:+.2%}，但对删除经验的差是{totals[1]['feedback'][0]/totals[1]['feedback'][1]-totals[1]['deletion'][0]/totals[1]['deletion'][1]:+.2%}；同初始程序重放已经出现了相应差异，因此不能把表面前后改善归因于持久经验。初版上下文前瞻pilot未显示Feedback优于无反馈。", '', '所有增益均为成功率绝对差，例如−25%表示−25个百分点。四组结果分别解释，不能合成平均分：原查询分布发现了起点饱和，保留全部结果；组合扩展在看到该缺口后定义，使用早已冻结的同两条学习产物，0新学习、0新模型调用，是探索性结果；两条新目录pilot分别对应初版与补全公开信息的上下文，均在任务资格后用独立stream重新学习。它们不作上下文效果的单因素因果比较。两条旧实例不会因扩展再算成两条新实例。', '',
              '## 1. 为什么这是一道有效学习题', '',
              '| 新组合资格对照 | 成功/回合 |', '|---|---|']
    for name, values in q['scores'].items():
        lines.append(f'| {name} | {sum(values)}/{len(values)} |')
    lines += ['', '另在实际组合查询条件上复跑同一个已冻结强参考：', '', '| 查询组 | 强参考 | 相同参考重放 |', '|---|---|---|']
    for group,value in reference['groups'].items():
        lines.append('| '+group+' | '+' | '.join(f'{sum(v)}/{len(v)}' for v in value.values())+' |')
    lines += ['', '这是12个既有查询条件、各两次物理执行，共24回合，不是24条学习轨迹。参考不再调整，初始状态与原查询配对；同时保留Frozen/删除的重放差异，不能仅因看见一次提升就宣称经验有效。']
    lines += ['', f"强参考与起点相差{q['strategy_gap_count']}个成功，同参考重放相差{q['identity_gap_count']}个。这支持当前版本的有限查询族资格，不能替代总体显著性。资格不要求某个Agent取胜，不要求起点在30%–70%。", '',
              f'开发响应从普通起点2/4、实际开度守卫4/4，推进到新组合起点3/4、参考4/4。原先只在支持几何验证能力差异、在查询几何只验证参考可达性，仍会把容易查询送入比较；本轮发现并纠正了这个设计缺口。旧{old_q_count}回合可达性资格与原学习结果未改写，新组合另以{new_q_count}个新条件执行回合核对。', '',
              '释放工程诊断支持检查实际开度和物体运动，但不支持唯一根因：严格低速门限可拖到19.72s才释放；先要求接触归零会在单侧接触下死锁。CPU解析碰撞资产显示场景Cube半高约.024m、桌面碰撞Mesh顶面约-.003m，预期落稳中心.021m与物理轨迹一致。支撑力仍not_measured，作者几何不是live cooked hull。', '',
              '## 2. Agent能看、能改、能继承什么', '',
              '| 角色 | 本轮内容 |', '|---|---|',
              '| 固定执行层 | 相同IK/驱动/TargetBounded；按实测双指接触启用既有有界积分、失接触平滑卸载；新协议不由phase名切换补偿 |',
              '| 共同起点 | 正常抓取/探升及直接放置扩展图；所有方法相同，不自动注入完整强参考 |',
              '| 公开观测 | 仿真位置/速度、实际双指坐标、指物法向力、任务目标；不是视觉赛道 |',
              '| 可编辑产物 | graph-v2的目标、守卫、图结构，16节点/64转移/2恢复及固定20s时限；不允许改物理、评分或任意代码 |',
              '| 继承与删除 | 新实例只读取冻结图与来源记忆；删除恢复精确starter；文本memory不参与控制 |', '',
              '质量、seed、条件ID、查询结果不进入参与者请求。目标是公开场景输入；解释器不硬写放置目的地。通用AND/OR、连续dwell、速度和实际开度可表达有效程序。开发者执行协议修复不是Agent学习，不能把旧0/4和新版本成绩比较为进化收益。', '',
              '## 3. 实际观察—选择—修改—冻结过程', '']
    for label, directory, data in (groups[0], groups[2], groups[3]):
        for instance in data['instances']:
            i = instance['learning_instance']
            for name in ('designer', 'feedback'):
                sub = directory/f'instance-{i}'/name
                if (sub/'validity_failure.json').exists():
                    lines.append(f"{label} 实例{i} {name}：参与者有效性失败；固定查询分母保留，原因见validity_failure.json。")
                    continue
                before = starter_program().to_dict()
                events = []
                selected=[]
                for f in sorted(sub.glob('proposal-*.json')):
                    proposal = read(f)
                    if proposal.get('tool')=='run_trial':
                        selected.append(proposal['practice_handle'])
                    try:
                        program = Program.from_dict(json.loads(proposal['program_json'])).to_dict()
                    except (ValueError, TypeError, KeyError):
                        events.append(f'{f.stem}:格式错误')
                        continue
                    old = {n['id']: n for n in before['nodes']}
                    changed = [n['id'] for n in program['nodes'] if old.get(n['id']) != n]
                    events.append(f"{proposal['tool']}[{','.join(changed) or '保持'}]")
                    before = program
                art = read(sub/'artifact.json')
                lines += [f"**{label} 实例{i} {name}**："+' → '.join(events)+f"；实际实践{art['payload']['budget_used']}回合，覆盖{len(set(selected))}/4个句柄；选择顺序{','.join(selected) or '无实践'}。", '']
    lines += ['例如原实例先运行starter失败，模型之后自行修改transport/lower的状态判断与release开度判断，再次执行并在支持条件成功，随后冻结。开发者没有向请求写入失败诊断—修复规则。若模型在无反馈情况下就设计出变化、或选择保持，也按实际提案记录，不能把第一次设计能力算成物理经验收益。', '',
              '两条旧反馈实例各只使用0/2两个句柄，四次成功是重复实践，不能当作覆盖四个条件。审阅发现初版提示未明确“同可见目标可能有不同隐藏物理性质”；公开上下文v2已对两组统一补全这条关系，不泄漏参数/类别标签，不强制覆盖或改进。其独立pilot与旧结果分开。全部候选、真实请求/响应/usage和完整高频轨迹留档。`learning_events.json`把观察到的客观结果与之后提案对应；参与者memory仅是自己的假设。`command_response.json`在同一组公开观测上解释新旧图，核对命令变化，另存真实applied targets与限幅；命令反事实不是额外物理轨迹。', '',
              '## 4. 反馈收益与持久经验收益', '']
    for (label, _, data), counts in zip(groups, totals, strict=True):
        def rate(n):
            return counts[n][0]/counts[n][1]
        lines.append(f"**{label}**：Feedback相对No-Feedback {rate('feedback')-rate('designer'):+.2%}；相对删除经验 {rate('feedback')-rate('deletion'):+.2%}；Search相对Frozen {rate('search')-rate('frozen'):+.2%}、相对删除经验 {rate('search')-rate('deletion'):+.2%}。")
        for name, value in data['paired_conditional_intervals'].items():
            lines.append(f"{name} 条件bootstrap95%区间 [{value['interval'][0]:+.2%}, {value['interval'][1]:+.2%}]。")
        lines.append('')
    lines += ['区间只重采样这些固定学习实例内的查询条件；N=2探索性扩展、各N=1上下文pilot不能支持学习总体稳定性。Frozen/删除是同初始程序的物理重放，二者差异属于测量噪声，不是新学习。删除对照与总体before/after即使数值相同，也不是独立学习样本。', '',
              '两个模型方法使用相同推理上限，允许提前冻结；实际计算量不同。因此G_feedback比较的是给定上限下两种完整过程，不能据此排除更多实际推理本身的贡献。搜索是有限4候选族的共同小批比较，不能称为全图空间最强搜索，也不据此宣称普遍优于搜索。', '',
              '本轮只测同类适应。跨任务迁移、共享技能抗遗忘、在线Agent、文本记忆理解、视觉与真机均未运行。旧SkillLibrary的两个参数复制明确归框架，独立槽位保留不推断共享抗遗忘。', '',
              '## 5. 实际预算、费用与风险', '',
              '| 学习组/实例/方法 | 调用 | 输入tokens | 输出tokens | 实践回合 |', '|---|---|---|---|---|']
    calls = inputs = outputs = 0
    usage_complete=True
    for label, directory, data in (groups[0], groups[2], groups[3]):
        for instance in data['instances']:
            for name, c in instance['model_cost'].items():
                budget = instance['artifact_cost'].get(name, {}).get('physical_learning_episodes', 'unknown')
                lines.append(f"| {label}/{instance['learning_instance']}/{name} | {c.get('calls','unknown')} | {c.get('input_tokens','unknown')} | {c.get('output_tokens','unknown')} | {budget} |")
                calls += c.get('calls', 0)
                if type(c.get('input_tokens')) is int and type(c.get('output_tokens')) is int:
                    inputs+=c['input_tokens']
                    outputs+=c['output_tokens']
                else:
                    usage_complete=False
    lines += ['', f'真实模型合计{calls}调用、{inputs if usage_complete else str(inputs)+"（仅已报告；其余unknown）"}输入/{outputs if usage_complete else str(outputs)+"（仅已报告；其余unknown）"}输出tokens；探索性扩展没有重复计学习费用。模型标识gpt-6.1-terra、参考CLI0.165.0；服务基础权重revision未暴露，不能声称已哈希固定。每方法最多10调用/300k输入/48k输出，Feedback最多8实践，Search实际8。', '',
              f"本轮共{total['physical_episodes']}完成物理回合、{total['distinct_physical_conditions']}不同物理条件，{total['control_steps']}控制步、{total['physics_samples']} post-physics样本，0 PPO transitions。{total['native_processes']}个原生模拟进程（含失败）合计{total['native_process_minutes']:.3f}进程分钟；GPU0/1/2共享环境且部分并行，进程分钟含加载与模型等待，不等于独占GPU时间或总墙钟。", '',
              f"限幅/限速干预{total['limited_controls']}/{total['control_steps']}控制步；注册硬边界事件{total['hard_boundary_episodes']}回合，位置违规{total['position_violation_episodes']}回合。基础设施失败{total['infrastructure_failures']}次：几何日志接口错误在第一回合前退出，实际0回合，已保留失败。缺失支撑接触/切向力/solver力矩不填零。", '',
              '所有物理任务启动前预留、使用冻结源码；无效提交保留固定分母，基础设施故障单列。原主pilot最大72、探索扩展最大40、两个新目录单实例各最大36分别登记，未覆盖或补有利seed。新增DEV8在原DEV48工程资源上限内，新query资格另登记14，固定参考重放另登记24。', '',
              '## 6. 哪些入口真正从新目录运行了', '',
              '新目录 `/home/dell/peb-esl-fresh-20261030-001` 首先独立完成T0 smoke（1回合/500控制步/成功），不依赖T1/B1/PPO历史。随后用公开learn命令、stream2026103031、独立输出父目录 `/home/dell/peb-esl-external-runs-20261030`，真实完成初版上下文的新组合问题闭环；补全公开信息后，再以独立父目录 `/home/dell/peb-esl-context2-external-runs-20261030`、stream2026103032完成当前上下文v2闭环，保留全部旧结果。', '',
              '新目录使用新CPU venv与独立源码目录；原生依赖、资产缓存和外置许可模型复用本机固定安装，不是另一台机器或全新原生安装。另有无旧Git对象的轻量源码包CPU重建与执行内容哈希验证；它不冒充物理重跑。通用stdin JSON adapter无需ROSClaw，当前实际方法仍是同一个参考provider，不宣称已验证多框架。', '',
              '轻量任务资格同时绑定支持/查询profile、starter与执行内容；无需开发者旧运行目录。源码/小样例与完整原始轨迹分别交付，许可权重及资产不分发。查看 [参与指南](../core/QUICKSTART.md)、[当前协议](../core/LEARNING_PROBLEM_V2_PROTOCOL_20261030.md)、[开发响应表](../development/DEVELOPMENT_RESPONSE_20261030.csv) 和 [证据目录](../evidence/executable-skill-20261030)。', '',
              '可用实验Alpha与稳定自进化是不同结论。本轮可交付的是范围明确、能测得差异并保留负结果的单问题入口；总体稳定性、广泛迁移和完整安全仍未证明。旧双任务Core未因此追认为验收通过。', '']
    Path(output).write_text('\n'.join(lines))
    return total


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--primary', required=True)
    p.add_argument('--extension', required=True)
    p.add_argument('--prospective', required=True)
    p.add_argument('--context2',required=True)
    p.add_argument('--task-qualification', required=True)
    p.add_argument('--problem-qualification', required=True)
    p.add_argument('--reference-replay',required=True)
    p.add_argument('--studies', nargs='+', required=True)
    p.add_argument('--output', required=True)
    a = p.parse_args()
    print(json.dumps(report(Path(a.primary), Path(a.extension), Path(a.prospective),Path(a.context2),
          Path(a.task_qualification), Path(a.problem_qualification),Path(a.reference_replay), [Path(s) for s in a.studies], a.output), indent=2))


if __name__ == '__main__':
    main()
