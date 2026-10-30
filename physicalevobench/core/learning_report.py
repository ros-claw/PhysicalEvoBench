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
    early_failures=[]
    model_wall_s=0.
    model_processes=0
    cache_read=cache_write=0
    cache_missing=0
    by_study = []
    for study in studies:
        count = 0
        for process_path in study.rglob('model_calls/call-*/process.json'):
            model_processes+=1
            model_wall_s+=read(process_path)['wall_s']
            usage=process_path.parent/'usage.json'
            u=read(usage) if usage.exists() else {}
            if 'cached_input_tokens' in u and 'cache_write_input_tokens' in u:
                cache_read+=u['cached_input_tokens']
                cache_write+=u['cache_write_input_tokens']
            else:
                cache_missing+=1
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
                if not row['success'] and row['steps']<=8:
                    early_failures.append({'study':study.name,'native':str(native.relative_to(study)),'episode':row['episode_id'],'steps':row['steps']})
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
    total['very_early_task_failures']=early_failures
    total['model_processes']=model_processes
    total['model_process_wall_s']=model_wall_s
    total['reported_cache_read_input_tokens']=cache_read
    total['reported_cache_write_input_tokens']=cache_write
    total['model_calls_missing_cache_usage']=cache_missing
    return total


def report(primary, extension, prospective, context2, context3, task_qualification, problem_qualification, reference_replay, studies, output):
    groups = [('原查询 / 两实例', primary, read(primary/'results.json')),
              ('组合查询 / 原两实例探索性扩展', extension, read(extension/'results.json')),
              ('组合查询 / 新目录初版上下文pilot', prospective, read(prospective/'results.json')),
              ('组合查询 / 新目录公开上下文v2 pilot',context2,read(context2/'results.json')),
              ('组合查询 / 新目录连续记忆v3 pilot',context3,read(context3/'results.json'))]
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
    lines += ['', '这轮确认了benchmark本身的两个缺口：只证明参考可达性没有发现原查询饱和；临时会话丢失试验关联和自写笔记。它们已按新版本修复，不能用修复前成绩判断Agent能力上限。反过来，某一pilot正差异也不等于稳定自进化。', '', f"探索组合中，Feedback对Frozen的表面差是{totals[1]['feedback'][0]/totals[1]['feedback'][1]-totals[1]['frozen'][0]/totals[1]['frozen'][1]:+.2%}，但对删除经验的差是{totals[1]['feedback'][0]/totals[1]['feedback'][1]-totals[1]['deletion'][0]/totals[1]['deletion'][1]:+.2%}；同初始程序重放已经出现了相应差异，因此不能把表面前后改善归因于持久经验。初版上下文前瞻pilot未显示Feedback优于无反馈。", '', '所有增益均为成功率绝对差，例如−25%表示−25个百分点。五组结果分别解释，不能合成平均分：原查询分布发现了起点饱和，保留全部结果；组合扩展在看到该缺口后定义，使用早已冻结的同两条学习产物，0新学习、0新模型调用，是探索性结果；三条新目录pilot分别对应初版、补全公开信息与修复记忆连续性的上下文，均在任务资格后用独立stream重新学习。总计5条实际学习实例分布在不同协议/上下文中，不能合并为某一协议的N=5。它们不作上下文效果的单因素因果比较；尤其不能用新旧stream的成功率差声称记忆修复本身带来多少增益。两条旧实例不会因扩展再算成两条新实例。', '',
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
              '质量、seed、条件ID、查询结果不进入参与者请求。公开发布的生成器和事后manifest不是保密评测服务器；当前结论来自受限真实provider的请求审计，不声称防御恶意外部adapter。目标是公开场景输入；解释器不硬写放置目的地。通用AND/OR、连续dwell、速度和实际开度可表达有效程序。开发者执行协议修复不是Agent学习，不能把旧0/4和新版本成绩比较为进化收益。', '',
              '## 3. 实际观察—选择—修改—冻结过程', '']
    for label, directory, data in (groups[0], groups[2], groups[3], groups[4]):
        for instance in data['instances']:
            i = instance['learning_instance']
            for name in ('designer', 'feedback'):
                sub = directory/f'instance-{i}'/name
                if (sub/'validity_failure.json').exists():
                    lines.append(f"{label} 实例{i} {name}：参与者有效性失败；固定查询分母保留，原因见validity_failure.json。")
                    continue
                before = starter_program().to_dict()
                events = []
                selected=[h.get('practice_handle') or read(sub/f'proposal-{j:02d}.json')['practice_handle'] for j,h in enumerate(read(sub/'history.json')) if h['tool']=='run_trial'] if (sub/'history.json').exists() else []
                for f in sorted(sub.glob('proposal-*.json')):
                    proposal = read(f)
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
    lines += ['同一组实际查询公开观测下，分别解释starter与冻结Feedback图的命令响应：', '', '| 证据组 | 实际查询控制步 | 目标不同步数 | 夹爪命令不同步数 | 实际执行层干预步数 |', '|---|---|---|---|---|']
    for label,directory,_ in groups:
        rows=[r for r in read(directory/'command_response.json')['episodes'] if r['native'].endswith('/test-feedback')]
        lines.append('| '+label+' | '+' | '.join(str(sum(r[k] for r in rows)) for k in ('steps',))+' | '+str(sum(r['same_observation_counterfactual']['different_target_controls'] for r in rows))+' | '+str(sum(r['same_observation_counterfactual']['different_gripper_controls'] for r in rows))+' | '+str(sum(r['actually_limited_controls'] for r in rows))+' |')
    lines += ['', '前两项差异是同观测命令映射反事实，不是另一条物理轨迹；干预来自真实applied-target日志。各产物节点数、序列化字节、笔记字符与实践成本见method_results.json的artifact_cost，无共享依赖或跨任务router。', '', '例如原实例先运行starter失败，模型之后自行修改transport/lower的状态判断与release开度判断，再次执行并在支持条件成功，随后冻结。开发者没有向请求写入失败诊断—修复规则。若模型在无反馈情况下就设计出变化、或选择保持，也按实际提案记录，不能把第一次设计能力算成物理经验收益。', '',
              '两条旧反馈实例各只使用practice-0和practice-2两个句柄，四次成功是重复实践，不能当作覆盖四个条件。审阅发现初版提示未明确“同可见目标可能有不同隐藏物理性质”；公开上下文v2已对两组统一补全这条关系，不泄漏参数/类别标签，不强制覆盖或改进。其独立pilot与旧结果分开。全部候选、真实请求/响应/usage和完整高频轨迹留档。`learning_events.json`把观察到的客观结果与之后提案对应；参与者memory仅是自己的假设。`command_response.json`在同一组公开观测上解释新旧图，核对命令变化，另存真实applied targets与限幅；命令反事实不是额外物理轨迹。', '',
              'v3进一步修复了实质性的harness缺陷：旧临时会话没有带回已选实践句柄和参与者自己的笔记，尽管最终artifact有memory字段。现在每次调用携带current_memory和历史句柄，原始笔记全量留档并逐项审计。旧版本成绩不能据以归责基础模型，v3成绩也不能追溯改写旧成绩。控制器、物理和评分均未改变。', '', '## 4. 反馈收益与持久经验收益', '', '| 证据组 / 实例 | Frozen | 无反馈 | Search | Feedback | 删除 |', '|---|---|---|---|---|---|']
    for label,_,data in groups:
        for item in data['instances']:
            lines.append('| '+label+' / '+str(item['learning_instance'])+' | '+' | '.join(f"{sum(item['scores'][n].values())}/{len(item['scores'][n])}" for n in arms)+' |')
    lines.append('')
    for (label, _, data), counts in zip(groups, totals, strict=True):
        def rate(n):
            return counts[n][0]/counts[n][1]
        lines.append(f"**{label}**：Feedback相对No-Feedback {rate('feedback')-rate('designer'):+.2%}；相对删除经验 {rate('feedback')-rate('deletion'):+.2%}；Search相对Frozen {rate('search')-rate('frozen'):+.2%}、相对删除经验 {rate('search')-rate('deletion'):+.2%}。")
        for name, value in data['paired_conditional_intervals'].items():
            lines.append(f"{name} 条件bootstrap95%区间 [{value['interval'][0]:+.2%}, {value['interval'][1]:+.2%}]。")
        lines.append('')
    lines += ['同一starter的Frozen/删除经验成败配对（不是两种学习算法）：', '', '| 证据组 | 成败不一致/条件 | 仅Frozen成功 | 仅删除重放成功 |', '|---|---|---|---|']
    for label,_,data in groups:
        pairs=[(item['scores']['frozen'][c],item['scores']['deletion'][c]) for item in data['instances'] for c in item['scores']['frozen']]
        lines.append(f'| {label} | {sum(a!=b for a,b in pairs)}/{len(pairs)} | {sum(a and not b for a,b in pairs)} | {sum(b and not a for a,b in pairs)} |')
    lines += ['', '同程序总成功率相同也可能在不同条件上成败互换；这些差异不能算进学习实例数。', '', '区间只重采样这些固定学习实例内的查询条件；N=2探索性扩展、各N=1上下文pilot不能支持学习总体稳定性，也没有单独估计物理重放噪声或服务权重变化的不确定性。Frozen/删除是同初始程序的物理重放，二者差异属于测量噪声，不是新学习。删除对照与总体before/after即使数值相同，也不是独立学习样本。', '',
              '两个模型方法使用相同推理上限，允许提前冻结；实际计算量不同。因此G_feedback比较的是给定上限下两种完整过程，不能据此排除更多实际推理本身的贡献。搜索是有限4候选族的共同小批比较，不能称为全图空间最强搜索，也不据此宣称普遍优于搜索。', '',
              '本轮只测预设B≤8这一预算档；没有多预算学习曲线，提前冻结只记实际成本。X因素仅相差2cm，小于5cm的XY成功容差，因此留出组合不是强空间OOD，不能宣称远距离几何泛化。本轮只测同类适应。跨任务迁移、共享技能抗遗忘、在线Agent、文本记忆理解、视觉与真机均未运行。旧SkillLibrary的两个参数复制明确归框架，独立槽位保留不推断共享抗遗忘。', '',
              '## 5. 实际预算、费用与风险', '',
              '| 学习组/实例/方法 | 调用 | 输入tokens | 输出tokens | 实践回合 |', '|---|---|---|---|---|']
    calls = inputs = outputs = 0
    usage_complete=True
    for label, directory, data in (groups[0], groups[2], groups[3], groups[4]):
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
              f"模型子进程合计{total['model_processes']}次、{total['model_process_wall_s']:.3f}s（CLI启动、服务推理与等待合计，不能拆出独立冷启动费用）。provider报告缓存读取{total['reported_cache_read_input_tokens']}、写入{total['reported_cache_write_input_tokens']} input tokens；{total['model_calls_missing_cache_usage']}次调用缺缓存分项。缓存读取是总input的子项，不另加总。货币账单未知，不填零。", '',
              f"本轮共{total['physical_episodes']}完成物理回合、{total['distinct_physical_conditions']}不同物理条件，{total['control_steps']}控制步、{total['physics_samples']} post-physics样本，0 PPO transitions。低层使用IK/参考执行；外置官方RSL checkpoint是复用加载链的依赖，不是本轮学习或改善的来源。{total['native_processes']}个原生模拟进程（含失败）合计{total['native_process_minutes']:.3f}进程分钟；GPU0/1/2共享环境且部分并行，进程分钟含加载与模型等待，不等于独占GPU时间或总墙钟。", '',
              f"限幅/限速干预{total['limited_controls']}/{total['control_steps']}控制步；注册硬边界事件{total['hard_boundary_episodes']}回合，位置违规{total['position_violation_episodes']}回合。基础设施失败{total['infrastructure_failures']}次：几何日志接口错误在第一回合前退出，实际0回合，已保留失败。缺失支撑接触/切向力/solver力矩不填零。", '',
              f"另有{len(total['very_early_task_failures'])}个极早失败（≤8控制步），出现在approach、夹持前，不能归责已学习的释放策略。三条既有异常的逐步Z/速度轨迹相同，与自由落体一致，穿过预期支撑高度而未停住；这是场景支撑异常的线索，不是已确定的碰撞根因（详见very_early_drop_observations.csv）。它们保留为原协议任务失败，未重抽seed或重分类。已记录初态配对一致不能证明全部隐藏solver状态一致；尚未测量桌面支撑力，唯一物理根因未知。小样本方法效应受这类差异污染；当前不适合用来作跨模型/跨框架正式排名。", '',
              '所有物理任务启动前预留、使用冻结源码；无效提交保留固定分母，基础设施故障单列。原主pilot最大72、探索扩展最大40、三个新目录单实例各最大36分别登记，未覆盖或补有利seed。新增DEV8在原DEV48工程资源上限内，新query资格另登记14，固定参考重放另登记24。', '',
              '## 6. 哪些入口真正从新目录运行了', '',
              '新目录 `/home/dell/peb-esl-fresh-20261030-001` 首先独立完成T0 smoke（1回合/500控制步/成功），不依赖T1/B1/PPO历史。随后用公开learn命令、stream2026103031、独立输出父目录 `/home/dell/peb-esl-external-runs-20261030`，真实完成初版上下文的新组合问题闭环；补全公开信息后，再以独立父目录 `/home/dell/peb-esl-context2-external-runs-20261030`、stream2026103032完成上下文v2闭环；另从新源码目录 `/home/dell/peb-esl-context3-fresh-20261030-001`、stream2026103033与独立输出父目录完成v3闭环，保留全部旧结果。', '',
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
    p.add_argument('--context3',required=True)
    p.add_argument('--task-qualification', required=True)
    p.add_argument('--problem-qualification', required=True)
    p.add_argument('--reference-replay',required=True)
    p.add_argument('--studies', nargs='+', required=True)
    p.add_argument('--output', required=True)
    a = p.parse_args()
    print(json.dumps(report(Path(a.primary), Path(a.extension), Path(a.prospective),Path(a.context2),Path(a.context3),
          Path(a.task_qualification), Path(a.problem_qualification),Path(a.reference_replay), [Path(s) for s in a.studies], a.output), indent=2))


if __name__ == '__main__':
    main()


def reliability_report(study,qualification,conformance,output,adapter=None):
    """Source-backed Markdown for the three independent acceptance decisions."""
    from physicalevobench.core.replication_metrics import ARMS,LABELS

    reg=read(study/'registration.json')
    data=read(study/'results.json')
    q=read(qualification/'qualification.json')
    con=read(conformance/'results.json')
    summary=data['summary']
    def percent(v):
        return '未估计' if v is None else f'{100*v:+.2f} pp'
    valid_feedback=sum('feedback' in b['retained_artifacts'] for b in data['blocks'])
    lines=['# PhysicalEvoBench ESL：可靠性与独立重复实施报告','',
           f'预登记8个独立学习block，其中{valid_feedback}个形成合法Feedback冻结产物；缺失、INIT_INVALID和参与者错误分别保留，不能把未完成方法写成算法零分。', '',
           '本轮保留 Place–Release Factorial v2，公开上下文固定 public-context-v3，执行版本固定 core-place-public-v5-ready2。独立学习8个block，每block16个配对query，五方法；全部产物先冻结，再开始查询。旧Alpha及其失败不改判、不池化。','',
           '| 方法 | 已知成功 / 全部分配 | 有效任务执行成功 | 学习物理尝试 | 实际模型调用 | 输入 / 输出 tokens |',
           '|---|---:|---:|---:|---:|---:|']
    for arm in ARMS:
        a=summary['arms'][arm]
        costs=[b['model_cost'].get(arm,{}) for b in data['blocks']]
        calls=sum(c.get('calls',0) for c in costs)
        tokens=[]
        for key in ('input_tokens','output_tokens'):
            tokens.append(str(sum(c.get(key,0) for c in costs)) if all(isinstance(c.get(key,0),int) for c in costs) else 'unknown')
        practice=sum(b['learning_physical_attempts'].get(arm,0) for b in data['blocks'])
        lines.append(f"| {LABELS[arm]} | {a['successes']}/{a['assigned']} | {a['successes']}/{a['valid_task_executions']} | {practice} | {calls} | {' / '.join(tokens)} |")
    lines+=['','全分配列是已观察到的成功产出，缺失/服务故障不会补成模型能力零分；下表列出缺失和归因。有效执行分母另列。Deletion恢复共同starter，其配套学习成本已在Feedback计费，不重复计费。','',
            '| 验收维度 | 判断与边界 |','|---|---|',
            '| 工程 | 纯状态执行、冻结恢复、通用stdin接入及证据重算分别验证；同机新目录验证见下文。没有第二机器/独立外部人复现结论。 |',
            f"| 测量 | Ready正常/有效故障注入 {con['status']}；固定8-block尝试的完成/缺失见逐block表；同图discordance保留。旧异常唯一因果归属尚未完全确定，已证实的参数传输缺陷已修复；运行期未知掉落不自动归基础设施。 |",
            '| 算法 | 依据以下原始计数、block效果和区间判断，零/负收益不使基准失败。工程/审计通过不等于方法有效，也不证明广泛或递归自进化。 |','',
            '## 固定方法比较与逐block结果','',
            '这是budget-cap comparison：NoFeedback和Feedback共享最大预算，但允许自然提前冻结，实际tokens/调用可以不同。TemplateSearch-4是人工专家候选先验加score-only选择，4候选×共同2支持条件；不是无先验盲搜，也不等于全图空间最优搜索。','',
            '| 比较 | block均值差 | 分层95%区间 |','|---|---:|---|']
    for arm,value in summary['comparisons'].items():
        ci=value['hierarchical_95_interval']
        lines.append(f"| Feedback − {LABELS[arm]} | {percent(value['mean_block_effect'])} | {('['+percent(ci[0])+', '+percent(ci[1])+']') if ci else value['interval_status']} |")
    lines+=['','| Block | Frozen | NoFeedback | TemplateSearch-4 | Feedback | Deletion | F−NoFeedback | F−Deletion | F−Template | 同图不一致 |','|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for i,b in enumerate(data['blocks']):
        counts=[]
        for arm in ARMS:
            values=list(b['scores'][arm].values())
            known=sum(v is not None for v in values)
            success=sum(v is True for v in values)
            counts.append(f'{success}/{known}'+(f'（缺失{16-known}）' if known<16 else ''))
        gains=[percent(summary['comparisons'][arm]['block_points'][i]['feedback_minus_baseline']) for arm in ('designer','deletion','search')]
        noise=summary['identity_replays'][i]
        lines.append('| '+str(i)+' | '+' | '.join(counts+gains+[f"{noise['discordant_pairs']}/{noise['paired_valid']}"])+' |')
    lines+=['','统计以独立学习block为最外层，内部在goal×mass cell内配对抽样；本研究只有一个有限物理问题，128个query不是128个独立任务族。每方法/条件通常只有一次物理执行，Frozen/Deletion同图重放用于显示不一致，无法完全分离每个学习产物的物理重放方差。8个block也不保证总体显著性。','',
            '| Block | Frozen独胜 | Deletion独胜 | 不一致对 / 有效配对 |','|---|---:|---:|---:|']
    for n in summary['identity_replays']:
        lines.append(f"| {n['block']} | {n['frozen_only_success']} | {n['deletion_only_success']} | {n['discordant_pairs']}/{n['paired_valid']} |")
    lines+=['','不能用净成功差代替重放噪声；相反方向的交换会抵消。历史v2 N=1的三个同向不一致对精确双侧配对二项p=0.25，v3一个不一致对p=1；它们只说明小样本分辨力，不与本轮合并，也不把p阈值当验收条件。','',
            '## 学到了什么、实际执行是否受到影响','',
            '以下仅记录产物和真实执行链，不能凭文件diff、笔记不同或节点增加判为能力增长。是否值得继承，要同时看Feedback−Deletion、参考方法比较、成本与独立block不确定性。','',
            '| Block | Feedback实践数 | 覆盖支持句柄 | 图与starter行为指纹是否不同 | 最终节点数 | NoFeedback调用数 | Feedback调用数 |','|---|---:|---|---|---:|---:|---:|']
    for b in data['blocks']:
        i=b['block']
        directory=study/f'instance-{i}'
        history=read(directory/'feedback/history.json') if (directory/'feedback/history.json').exists() else []
        handles=[h['practice_handle'] for h in history if h.get('tool')=='run_trial']
        f=b['retained_artifacts'].get('feedback',{})
        starter=b['retained_artifacts']['frozen']
        changed=(f.get('executable_fingerprint')!=starter['executable_fingerprint']) if f else '无合法产物'
        lines.append(f"| {i} | {b['learning_physical_attempts'].get('feedback',0)} | {handles} | {changed} | {f.get('nodes','missing')} | {b['model_cost']['designer']['calls']} | {b['model_cost']['feedback']['calls']} |")
    lines+=['','| 查询方法 | GUARD_EVALUATED | BRANCH_TAKEN | COMMAND_CHANGED | APPLIED_TARGET_CHANGED |','|---|---:|---:|---:|---:|']
    for arm in ARMS:
        chain=[b['execution_effects'].get(arm,{}).get('counts',{}) for b in data['blocks']]
        counts=[sum(c.get(k,0) for c in chain) for k in ('GUARD_EVALUATED','BRANCH_TAKEN','COMMAND_CHANGED','APPLIED_TARGET_CHANGED')]
        lines.append('| '+LABELS[arm]+' | '+' | '.join(map(str,counts))+' |')
    lines+=['','这些是嵌套的真实轨迹计数：实际评估守卫→发生转移→高层命令变化→实际有界关节目标变化。超时转移与守卫转移在原始结果JSON中分列；它们不单独证明改动造成任务收益。例证固定展示block0，未按最高成绩选择：','']
    first=data['blocks'][0]['execution_effects'].get('feedback',{}).get('example')
    if first:
        lines+=['```json',json.dumps(first,ensure_ascii=False,indent=2),'```','']
    else:
        lines+=['block0没有完整链例证，保留缺失。','']
    lines+=['## 参数传输缺陷、初始化边界与尚未确定的因果归属','',
            '三条旧异常对预选同条件正常对照，首次明显分离均在记录的第17个物理子步（0.085s）：异常z≈0.01943m、vz≈−0.83385m/s；正常z≈0.02100m、vz≈−0.00535m/s，指物法向接触为0。它发生在夹持之前，支持支撑异常层面的判断。旧协议未测cube–table配对接触，不能追溯断言某个collider/cooking/API是唯一根因。','',
            '18次固定关节/开指、无接近交叉诊断：旧异常条件轮换首/二/三槽位，有/无额外readback，均未复现穿桌；不足以证明普通随机噪声，也不能据此排除初始化时序问题。并发源码导出曾发生半写入误判；已完成9次保留，仅9个未启动槽位恢复，源码缓存导出改为跨线程/进程锁。','',
            'Ready采用固定200子步（1秒）无候选支撑预演，检查PhysX静态桌面shape ray hits、Cube实测净法向力、速度/高度、有限状态、shape/body数量及质量读回；恢复同一条件原始关节/物体状态、朝向和速度，不换seed、不再随机、不改任务时钟/评分。任务起点仍是原始cube高度0.055m，相对抬升门槛未放宽。求解器/接触历史被预演，属于新执行分布。','',
            '实际静态桌面碰撞路径为 /World/envs/env_0/table/Collisions/Cube，运行时查询顶部约−0.003m；Cube落稳中心约0.021m。Cube net_normal_forces_w是世界轴牛顿值（轻质量约0.981N），不是精确cube–table配对力。静态桌面不能直接用旧的刚体ContactSensor正则过滤；该错误启动尝试保留。PhysX配对report当前为空/未测，不能把净力冒充配对力。GPU动态Cube ray返回曾显示滞后姿态，因此Ready仅用静态桌面查询，不声称所有动态查询已同步。','',
            '| 诊断/尝试 | 实际物理尝试 | 结果 |','|---|---:|---|',
            '| 固定姿态交叉（含仅未启动槽位恢复） | 18 | 0次自发异常复现；根因未定 |',
            '| Ready-001 | 0 | 静态表面传感器filter构建失败，原生设置失败 |',
            '| Ready-002 | 6 | 原碰撞配置未生效，负例无效，不能作检测证明 |',
            '| Ready-003 | 6 | 4正常READY，2个已确认移除碰撞体的负例INIT_INVALID，任务控制0步 |',
            '| 参数传输独立诊断 | 6 | GPU缓存0.4kg而PhysX模型0.1kg/惯量不一致；同值同步重写组未发现不一致 |',
            '| Ready-004（Ready2） | 6 | 4正常READY且真实模型参数匹配，2确认支撑缺失INIT_INVALID，任务控制0步 |',
            f"| 新执行参考资格 | 14 | {q['status']}；starter {sum(q['scores']['starter'])}/4，strong {sum(q['scores']['strong'])}/4，同图 {sum(q['scores']['identity_strong'])}/4，force-open {sum(q['scores']['force_open'])}/2 |",'',
            '短诊断总计42次，低于48上限；两版参考资格各14次另列。无故障注入冒称自发故障复现。正常检查与明确支撑缺失负例的离线原始重算一致；这限定了当前可检测边界，不能保证所有仿真错误均可识别。Ready失败不生成任务标签；原因不明的运行期掉落仍保留任务失败/UNKNOWN，不自动免责。','',
            '已确认的参数传输缺陷：固定Lab的indexed setter把GPU数据异步wp.copy到pinned CPU mass/inertia/index scratch，随后CPU PhysX setter可能消费未完成的旧数据。直接PhysX getter与GPU shadow读回分离的诊断复现了这一点；同值同步重写消除该诊断中的不一致。Ready2只在Cube对应的set_masses/set_inertias入口等待当前上下文传输完成，保留原采样与惯量比例。预演前后及恢复后都用PhysX get_masses/get_inertias验证真实模型值，不能靠缓存自证。固定Arena/Lab文件没有修改。','',
            '首次Ready1 cohort因此在所有query开始前整体停止，未挑有利block回收：59次已完成物理尝试、41次真实模型调用、0query，全部成本单列保留。这不是负算法成绩，也不是一次正式8-block结果。新Ready2从所有方法共同starter/空记忆重新登记完整8-block；提示仍是原v3，没有把新诊断写进Agent上下文。旧Ready1资格卡保留，但其缓存核验不能追认为真实质量已验证。','',
            '## 故障、分母和真实成本','',
            '| 方法 | 全部分配 | 有效任务执行 | INIT_INVALID | 参与者非法 | 结果缺失 |','|---|---:|---:|---:|---:|---:|']
    for arm,a in summary['arms'].items():
        lines.append(f"| {LABELS[arm]} | {a['assigned']} | {a['valid_task_executions']} | {a['init_invalid']} | {a['participant_invalid']} | {a['missing']} |")
    failures=[{'block':b['block'],'method':a,**v} for b in data['blocks'] for a,v in b['method_failures'].items()]
    lines+=['',f'服务/基础设施导致的未完成方法记录：{json.dumps(failures,ensure_ascii=False)}。自动provider/物理重试均为0；usage缺失为unknown。参与者格式错误可在原预算内自行修正，评测器不代修图。','',
            '主研究实际物理成本（诊断、参考资格、外部接入另列）：','',
            '```json',json.dumps(data['physical_cost'],ensure_ascii=False,indent=2),'```','',
            '任务物理时长按实际子步×0.005s，Ready时长另列；模型缓存是输入的子集，不与输入重复相加。原生进程时间含启动、空闲等待模型和退出，不等于GPU独占时长。货币费用无账单为unknown。安全只报告已测硬边界、坐标越界与限幅，不宣称全接触/真机安全。','']
    for name in ('designer','feedback'):
        costs=[b['model_cost'][name] for b in data['blocks']]
        aggregate={}
        for key in ('calls','input_tokens','output_tokens','cached_input_tokens','cache_write_input_tokens','wall_seconds'):
            aggregate[key]=sum(c[key] for c in costs) if all(isinstance(c[key],(int,float)) for c in costs) else 'unknown'
        lines+=['```json',json.dumps({'method':LABELS[name],**aggregate,'money':'unknown'},ensure_ascii=False,indent=2),'```','']
    lines+=['## 外部接入与复现范围','']
    if adapter and (adapter/'result.json').exists():
        lines+=['同机新源码目录、新CPU venv，复用固定原生安装/资产缓存；通用stdin adapter走实际模型调用，设计并冻结后在新原生进程执行：','',
                '```json',json.dumps(read(adapter/'result.json'),ensure_ascii=False,indent=2),'```','']
    else:
        lines+=['新目录stdin实际物理接入结果尚未提供，不能声称已完成。','']
    lines+=['适配器仍经同一个Codex CLI和同一请求模型，不是第二个独立框架或模型。第二兼容RTX机器与未参与开发的外部人员复现均未验证；本轮不冒称完成。新状态执行无需下载/加载未使用的PPO checkpoint，身份为代码/执行配置哈希，旧模型接口保留。资产与原生依赖许可单独遵守。','',
            '最小入口见 [Quickstart](../reliability/QUICKSTART.md)，源码/固定局部样例与完整轨迹分开。默认不下载历史证据。DeliberationOnly-9与额外B2/B4查询曲线在主研究开始前登记为NOT_RUN，本轮优先完成固定主研究；B2/4/8快照只留档，不伪造未测学习曲线。','',
            '## 证据与适用范围','',
            f'- 主研究注册与完整结果：[{study.name}]({study})，注册源码 `{reg["source_commit"]}`。',
            f'- 新执行资格：[{qualification.name}]({qualification})；故障边界：[{conformance.name}]({conformance})。',
            '- 旧异常首次分离：[原始来源与SHA](../evidence/esl-reliability-20261030/old_first_divergence.json)。',
            '- 任务书：[ESL下一阶段实施任务书](../../PhysicalEvoBench_ESL_下一阶段实施任务书_20261030.md)。','',
            '物理命令/返回码见每个native的launch.json与process.json；请求、保留预算、模型真实usage、公开反馈、Ready预演、逐子步轨迹、产物SHA、逐block图与实际执行链保留。离线重算不会产生新的独立学习或物理回合。服务标识gpt-6.1-terra，具体基础权重哈希、effort与fingerprint unavailable，结论限定于本实验窗口。','',
            '查询X差仅2cm，小于5cm成功容差，称留出因素组合而非强空间OOD。结论不外推到跨任务迁移、视觉、在线任意代码、权重学习、多智能体或递归自进化。旧双任务Core不因此追认验收。未按成绩换题、换提示、追加直到显著；PR #10与旧Alpha保留，新合并/发布不在本轮授权范围。','']
    Path(output).write_text('\n'.join(lines))
    return {'report':str(output),'blocks':len(data['blocks'])}


def reliability_costs(studies):
    """All incurred attempts, including initialization/transport/aborted-cohort costs."""
    summaries=[]
    for study in studies:
        totals={'study':str(study),'completed_physical_attempts':0,'reserved_attempts':0,
                'init_invalid':0,'task_controls':0,'task_physics_substeps':0,'ready_physics_substeps':0,
                'native_processes':0,'known_native_seconds':0.,'native_processes_unknown_exit_or_duration':0,
                'model_calls':0,'known_input_tokens':0,'known_output_tokens':0,'unknown_usage_calls':0}
        recovered={}
        receipt=study/'stopped_model_cost_receipts.json'
        if receipt.exists():
            recovered={r['call']:r['usage'] for r in read(receipt)['calls']}
        for source in sorted(study.rglob('source_identity.json')):
            native=source.parent
            if not (native/'launch.json').exists():
                continue
            totals['native_processes']+=1
            process=read(native/'process.json') if (native/'process.json').exists() else {}
            start=read(native/'launch.json')['started_at']
            if process.get('finished_at'):
                totals['known_native_seconds']+=(datetime.fromisoformat(process['finished_at'])-datetime.fromisoformat(start)).total_seconds()
            else:
                totals['native_processes_unknown_exit_or_duration']+=1
            totals['reserved_attempts']+=len(list((native/'requests').glob('*.json')))
            ledger=native/'episodes.jsonl'
            rows=[json.loads(line) for line in ledger.read_text().splitlines()] if ledger.exists() else []
            for row in rows:
                totals['completed_physical_attempts']+=1
                totals['init_invalid']+=row['execution_status']=='INIT_INVALID'
                totals['task_controls']+=row['steps']
                totals['task_physics_substeps']+=row.get('diagnostic',{}).get('physics_samples',0)
                ready=native/'episodes'/row['episode_id']/'readiness.json'
                if ready.exists():
                    totals['ready_physics_substeps']+=read(ready)['physical_substeps']
        for call in sorted(study.glob('**/model_calls/call-*')):
            if not call.is_dir():
                continue
            totals['model_calls']+=1
            usage=read(call/'usage.json') if (call/'usage.json').exists() else recovered.get(str(call.relative_to(study)))
            if usage is None:
                totals['unknown_usage_calls']+=1
            else:
                totals['known_input_tokens']+=usage['input_tokens']
                totals['known_output_tokens']+=usage['output_tokens']
        summaries.append(totals)
    return {'schema':'esl-reliability-all-incurred-cost-1','studies':summaries,
            'totals':{key:sum(s[key] for s in summaries) for key in summaries[0] if key!='study'},
            'scope':'Known actual costs, including stopped measurement cohort. Unknown process durations/exits remain unknown, not zero; simulator startup/internal build steps outside recorded task/probe are not fully measured. Cache tokens are a subset of input; currency unknown.'}


def export_replication(study,output):
    """Every allocation, physical validity and graph diff, without extra model/physics calls."""
    import csv

    from physicalevobench.core.artifact import load as load_artifact
    from physicalevobench.core.replication import artifact_path
    from physicalevobench.core.replication_metrics import ARMS
    from physicalevobench.doctor import save_json

    output.mkdir(parents=True,exist_ok=True)
    reg=read(study/'registration.json')
    result=read(study/'results.json')
    allocations=[]
    differences=[]
    for b,group in zip(result['blocks'],reg['conditions'],strict=True):
        directory=study/f"instance-{b['block']}"
        initial=load_artifact(directory/'frozen.json')['payload']['skill']
        initial_nodes={n['id']:n for n in initial['nodes']}
        for arm in ARMS:
            native=directory/f'test-{arm}'
            actual={}
            for request in sorted((native/'requests').glob('*.json')):
                job=read(request)
                ep=native/'episodes'/job['episode_id']
                if (ep/'episode.json').exists():
                    actual[job['condition']['condition_id']]=(ep,read(ep/'episode.json'))
            path=artifact_path(directory,arm)
            if path.exists():
                payload=load_artifact(path)['payload']
                changes=[]
                for node in payload['skill']['nodes']:
                    old=initial_nodes.get(node['id'],{})
                    changed={k:{'before':old.get(k,'not_present'),'after':v} for k,v in node.items() if k!='id' and old.get(k)!=v}
                    if changed:
                        changes.append({'node':node['id'],'fields':changed})
                removed=sorted(set(initial_nodes)-{n['id'] for n in payload['skill']['nodes']})
                differences.append({'block':b['block'],'method':arm,'changes':changes,'removed_nodes':removed,
                    'actual_self_written_memory':payload['memory'],'practice_cost':payload['budget_used'],
                    'scope':'Representational diff and participant notes only; functional control response is independently recomputed, not inferred from this diff.'})
            for c in group['query']:
                key=c['condition_id']
                item={'block':b['block'],'method':arm,'condition_id':key,'goal_x':c['public_goal'][0],
                      'goal_y':c['public_goal'][1],'evaluator_requested_mass_kg':c['object_mass_kg'],
                      'execution_status':b['execution_statuses'][arm][key],'success':b['scores'][arm][key],
                      'task_controls':None,'physx_model_mass_kg':None,'ready_status':None,
                      'lift_observed':None,'transport_observed':None,'maximum_stable_span_s':None,
                      'first_success_time_s':None,'left_after_first_success':None,
                      'terminal_xy_error_m':None,'terminal_z_error_m':None,'terminal_speed_m_s':None,
                      'terminal_finger_min_m':None,'artifact_hash':b['retained_artifacts'].get(arm,{}).get('effective_artifact_hash')}
                if key in actual:
                    ep,row=actual[key]
                    item['task_controls']=row['steps']
                    ready=read(ep/'readiness.json')
                    item['ready_status']=ready['status']
                    model=ready.get('physx_model_at_task_start',ready.get('physx_model_before_probe',{}))
                    if model.get('status')=='MEASURED':
                        item['physx_model_mass_kg']=model['mass'][0][0]
                    place=row.get('place',{})
                    for name in ('lift_observed','transport_observed','maximum_stable_span_s','first_success_time_s','left_after_first_success'):
                        item[name]=place.get(name)
                    terminal=ep/'terminal_pre_reset.json'
                    if terminal.exists():
                        t=read(terminal)
                        import math
                        item.update(terminal_xy_error_m=math.dist(t['object_position'][0][:2],c['public_goal'][:2]),
                                    terminal_z_error_m=abs(t['object_position'][0][2]-c['public_goal'][2]),
                                    terminal_speed_m_s=math.sqrt(sum(v*v for v in t['object_velocity'][0][:3])),
                                    terminal_finger_min_m=min(t['finger_position']))
                allocations.append(item)
    with (output/'per_condition.csv').open('w') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(allocations[0]),lineterminator='\n')
        writer.writeheader()
        writer.writerows(allocations)
    save_json(output/'artifact_differences.json',{'schema':'esl-actual-graph-diff-1','artifacts':differences})
    cells=[]
    for goal in reg['learning_problem']['query_goal_positions']:
        for mass in (.1,.4):
            values=[r for r in allocations if r['goal_x']==goal[0] and r['goal_y']==goal[1] and r['evaluator_requested_mass_kg']==mass]
            cells.append({'goal':goal,'mass_kg':mass,'arms':{a:{'successes':sum(r['success'] is True for r in values if r['method']==a),
                          'assigned':sum(r['method']==a for r in values),'unknown':sum(r['success'] is None for r in values if r['method']==a)} for a in ARMS}})
    save_json(output/'goal_mass_cells.json',{'cells':cells,'scope':'Descriptive predefined cells; not independent task families or population confidence intervals'})
    return {'allocated_rows':len(allocations),'artifact_diffs':len(differences),'extra_model_calls':0,'extra_physical_episodes':0}
