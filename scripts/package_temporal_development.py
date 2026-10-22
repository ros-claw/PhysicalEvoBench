"""Publish audited training exploration and validation without calling them test evidence."""

import argparse
import json
import tarfile
from pathlib import Path

from physicalevobench.doctor import save_json, sha256
from physicalevobench.evaluation.confirmation_audit import load


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--exploration',required=True)
    parser.add_argument('--validation',required=True)
    parser.add_argument('--destination',required=True)
    parser.add_argument('--report',required=True)
    args=parser.parse_args()
    exploration,validation=Path(args.exploration),Path(args.validation)
    if load(exploration/'audit.json')['status']!='PASS' or load(validation/'audit.json')['status']!='PASS':
        raise ValueError('Require both independent audits before delivery')
    destination=Path(args.destination)
    destination.mkdir(parents=True,exist_ok=False)
    inventory=[]
    for name,source in [('exploration',exploration),('validation',validation)]:
        archive=destination/f'{name}.tar.gz'
        with tarfile.open(archive,'w:gz',compresslevel=6) as tar:
            for p in sorted(source.rglob('*')):
                if p.is_file() and p.suffix in {'.json','.jsonl','.log','.lock'}:
                    tar.add(p,arcname=Path(name)/p.relative_to(source),recursive=False)
        inventory.append({'file':archive.name,'bytes':archive.stat().st_size,'sha256':sha256(archive)})
    selection,decision=load(exploration/'training_selection.json'),load(validation/'decision.json')
    save_json(destination/'summary.json',{'training_episodes':96,'validation_episodes':32,
              'heldout_test_episodes':0,'selection':selection,'validation_decision':decision,
              'scientific_scope':'Training-side development and independent validation, not heldout efficacy'})
    save_json(destination/'archive_inventory.json',inventory)
    (destination/'README.md').write_text('''# Temporal skill development evidence

96 real training exploration episodes, 32 independent validation episodes, zero heldout test episodes.
All 128 raw action/state traces, upstream outcomes, parameter snapshots, source hashes and budgets
are in the archives. No model weights are distributed. No actuator strength, mass distribution,
robot model, official success predicate or timeout was changed.

Verify `sha256sum -c SHA256SUMS`, then extract both archives into the same fresh directory:

```bash
mkdir unpacked
tar -xzf exploration.tar.gz -C unpacked
tar -xzf validation.tar.gz -C unpacked
uv run python scripts/audit_temporal_exploration.py --study-dir unpacked/exploration
uv run python scripts/audit_temporal_gate.py --run-dir unpacked/validation --exploration unpacked/exploration
```

Training success gains are not a heldout self-improvement result. The predeclared gate and all
failed candidates are preserved. Original checkpoint and all historical evidence are unchanged.
''')
    files=sorted(p for p in destination.iterdir() if p.is_file())
    (destination/'SHA256SUMS').write_text(''.join(f'{sha256(p)}  {p.name}\n' for p in files))
    lines=['# 时序技能开发：训练探索与独立验证','',
           '**本阶段共完成 128 个真实物理 episode：96 个训练探索、32 个独立验证；留出测试为 0。**', '',
           '新增可学习参数是夹爪闭合保持步数和机械臂动作指数平滑系数。默认值严格复现原策略。'
           '闭爪保持只依据公开动作指令及步数触发，不读取质量、种子或测试结果。机器人驱动力限、质量分布、'
           '任务成功条件、控制频率和 5 秒时限均未修改。','',
           '## 训练探索','', '| 候选 | 成功 / 8 | 关节越限采样 |', '| --- | --- | --- |']
    for r in selection['ranking']:
        lines.append(f"| {r['trial']} | {r['successes']:g}/8 | {r['joint_limit_samples']:g} |")
    lines += ['', f"原策略在三个工作进程中各执行 8 次，共 {selection['original_replay_successes']}/24 成功；上表原策略按每 8 条件平均显示，"
              '并非 24 个不同训练条件。候选在同样的 8 个训练条件执行，按训练成功数、越限采样及改动幅度排序。', '',
              f"训练选择 `{selection['selected']['trial']}`，其参数哈希和选择结果在验证前冻结。", '',
              '## 独立验证','', '| 组别 | 成功 / 16 | 关节越限采样 |', '| --- | --- | --- |',
              f"| 原策略 | {decision['original_successes']}/16 | {decision['original_joint_limit_samples']} |",
              f"| 候选 | {decision['candidate_successes']}/16 | {decision['candidate_joint_limit_samples']} |", '',
              f"**预先固定的 gate：{decision['decision']}。** 晋级条件是候选成功次数严格增加，且越限采样总数不增加。"
              '16 对条件使用全新种子、相同配对初始状态、随机平衡执行顺序。候选依据训练结果选定，验证数据未进入更新器。', '',
              ('候选通过了开发验证，可以据此登记后续前瞻性测试；本阶段本身尚不是留出自进化证明。'
               if decision['decision']=='promote' else
               '候选未能通过预先固定的独立验证，已回滚；按计划不进入正式留出测试。本阶段没有支持该更新可泛化。'), '',
              '## 验证与证据','',
              '两个阶段均独立重建每一步动作，核对 float32 平滑状态、闭爪保持时长、技能哈希、'
              '官方分数、物理质量读回、关节计数、配对初始状态、预算和 train/validation 隔离，审计 PASS。', '',
              '关节越限采样不等于事故次数；碰撞仍未测量。不得据此建立完整安全结论。'
              '全部失败候选与负结果保留，不将最优训练成绩冒充测试成绩。', '',
              '[固定探索计划](TEMPORAL_EXPLORATION_PLAN.md) · '
              '[完整证据包](../evidence/temporal-development-20261022-001/)', '']
    Path(args.report).write_text('\n'.join(lines))
    print(json.dumps(inventory,indent=2))


if __name__=='__main__':
    main()
