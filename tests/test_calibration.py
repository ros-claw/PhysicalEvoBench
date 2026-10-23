from physicalevobench.calibration.safety import summarize_safety


def test_coordinate_safety_exposure_and_depth():
    result = summarize_safety([[0., -.002], [1.01, 0.]], [[0., 1.], [0., .04]],
                              ['panda_joint1', 'panda_finger_joint1'], .02)
    assert result['violation_joint_samples'] == 2
    assert result['violations_per_1000_joint_samples'] == 500
    assert result['per_joint'][0]['maximum_depth'] > .0099
    assert result['per_joint'][1]['unit'] == 'm'
    assert result['per_joint'][1]['duration_over_tolerance_s'] == .02
    assert result['collision'] == 'NOT_MEASURED'


def test_training_schema_rejects_hidden_truth():
    import pytest
    from physicalevobench.calibration.public_schema import learner_feedback

    public = {'observations':{'policy':[], 'task_obs':[]}, 'rewards':[], 'dones':[], 'time_outs':[]}
    assert learner_feedback(public) is public
    for key in ('mass', 'seed', 'heldout_results', 'environment'):
        with pytest.raises(ValueError):
            learner_feedback({**public,key:123})
    with pytest.raises(ValueError):
        learner_feedback({**public,'observations':{'policy':[], 'task_obs':[], 'mass':[]}})


def test_exact_power_all_discordances_favor_update():
    import math
    from physicalevobench.calibration.power import paired_power

    # At one-sided alpha=.05, at least five wins with no losses are needed.
    expected=1-sum(math.comb(32,k)*.2**k*.8**(32-k) for k in range(5))
    assert abs(paired_power(32,.2,.2)-expected)<1e-12
    assert paired_power(32,0,.3)<=.05


def test_published_seed_registry_recovers_diagnostic_and_training_seeds(tmp_path):
    import io
    import json
    import tarfile
    from physicalevobench.evaluation.seed_registry import published_seeds

    evidence=tmp_path/'docs/evidence'
    evidence.mkdir(parents=True)
    # Metadata fixture only; this does not stand in for any physical result.
    payload=json.dumps({'jobs':[{'condition':{'seed':12345}}], 'environment_seed':98765}).encode()
    with tarfile.open(evidence/'metadata.tar.gz','w:gz') as archive:
        member=tarfile.TarInfo('study/child/config.json')
        member.size=len(payload)
        archive.addfile(member,io.BytesIO(payload))
    assert {12345,98765}.issubset(published_seeds(tmp_path))


def test_runtime_source_ignores_live_worktree_and_rejects_cache_mutation(tmp_path):
    import subprocess
    import pytest
    from physicalevobench.calibration.source_snapshot import snapshot_source

    def git(*args):
        return subprocess.check_output(['git',*args],cwd=tmp_path,text=True).strip()

    git('init','-q')
    package=tmp_path/'physicalevobench'
    package.mkdir()
    module=package/'demo.py'
    module.write_text('VALUE = 1\n')
    git('add','physicalevobench')
    git('-c','user.name=Test','-c','user.email=test@example.invalid','commit','-qm','fixture')
    ref=git('rev-parse','HEAD')
    frozen,hashes=snapshot_source(tmp_path,ref)
    module.write_text('VALUE = 2\n')
    assert snapshot_source(tmp_path,ref)==(frozen,hashes)
    assert (frozen/'physicalevobench/demo.py').read_text()=='VALUE = 1\n'
    (frozen/'physicalevobench/demo.py').write_text('VALUE = 3\n')
    with pytest.raises(ValueError,match='cache changed'):
        snapshot_source(tmp_path,ref)


def _extract_real_study(tmp_path, name):
    import tarfile
    from pathlib import Path

    archive=Path(__file__).resolve().parents[1]/'docs/evidence/calibration-learning-20261023-001'/f'{name}.tar.gz'
    with tarfile.open(archive,'r:gz') as stream:
        stream.extractall(tmp_path,filter='data')
    return tmp_path/name


def test_real_measurement_trace_rejects_action_tampering(tmp_path):
    import json
    import pytest
    from physicalevobench.calibration.audit import audit_run,lines

    run=_extract_real_study(tmp_path,'calibration-measurement-20261023-002')
    assert audit_run(run)['measurement_control']['pass'] is True
    row=lines(run/'episodes.jsonl')[0]
    path=run/row['trace_artifact']
    trace=lines(path)
    trace[0]['applied_action'][0][0]+=1
    path.write_text(''.join(json.dumps(r)+'\n' for r in trace))
    with pytest.raises(ValueError,match='identity-skill calibration actions'):
        audit_run(run)


def test_real_measurement_rejects_score_changes_even_in_both_indexes(tmp_path):
    import json
    import pytest
    from physicalevobench.calibration.audit import audit_run,lines
    from physicalevobench.doctor import save_json

    run=_extract_real_study(tmp_path,'calibration-measurement-20261023-002')
    rows=lines(run/'episodes.jsonl')
    rows[0]['success']=not rows[0]['success']
    save_json(run/'episodes'/rows[0]['episode_id']/'episode.json',rows[0])
    (run/'episodes.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
    with pytest.raises(ValueError,match='Official success differs'):
        audit_run(run)


def test_real_heldout_cannot_relabel_original_weights_as_updated(tmp_path):
    import json
    import pytest
    from physicalevobench.calibration.audit import audit_run,lines,load
    from physicalevobench.doctor import save_json

    run=_extract_real_study(tmp_path,'calibration-ppo-heldout-20261023-001')
    assert audit_run(run)['arms']['candidate']['successes']==10
    rows=lines(run/'episodes.jsonl')
    candidate=next(r for r in rows if r['agent_id']=='candidate')
    candidate['base_checkpoint_sha256']=load(run/'config.json')['checkpoint_sha256']
    save_json(run/'episodes'/candidate['episode_id']/'episode.json',candidate)
    (run/'episodes.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
    with pytest.raises(ValueError,match='model hash differs'):
        audit_run(run)


def test_real_isolated_confirmation_rejects_gpu_assignment_changes(tmp_path,monkeypatch):
    import pytest
    from physicalevobench.calibration.isolated_audit import main
    from physicalevobench.calibration.audit import load
    from physicalevobench.doctor import save_json

    run=_extract_real_study(tmp_path,'calibration-isolated-confirmation-20261023-001')
    monkeypatch.setattr('sys.argv',['isolated_audit','--run-dir',str(run)])
    main()
    audit=load(run/'audit.json')
    assert audit['physical_episodes']==96
    assert audit['arms']['candidate']['successes']==15
    assert audit['matched_initial_observation_pairs']==48
    launch_path=run/'block-0-candidate/launch.json'
    launch=load(launch_path)
    launch['gpu']=0
    save_json(launch_path,launch)
    with pytest.raises(ValueError,match='Crossed GPU allocation mismatch'):
        main()
