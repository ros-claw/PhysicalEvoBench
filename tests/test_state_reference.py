from physicalevobench.v02.reference import ReferenceFSM


def observation(**changes):
    return {'ee_position':[.5,0,.12], 'object_position':[.5,0,.02],
            'goal_position':[.5,0,.3], 'object_velocity':[0,0,0],
            'finger_position':[.04,.04], 'cube_contact_force':[0,0],
            'orientation_error':0., **changes}


def advance(fsm, obs, count=3):
    for _ in range(count):
        result = fsm.update(obs,.02)
    return result


def test_time_alone_cannot_close_or_lift_before_reaching_grasp():
    fsm = ReferenceFSM()
    result = advance(fsm,observation(ee_position=[0,0,.8]),250)
    assert result['phase']=='approach' and result['gripper']=='open'
    assert advance(fsm,observation())['phase']=='descend'
    assert advance(fsm,observation(),100)['phase']=='descend'
    assert advance(fsm,observation(ee_position=[.5,0,.025]))['phase']=='close'


def test_single_contact_or_empty_closed_fingers_are_not_a_verified_grasp():
    fsm = ReferenceFSM()
    advance(fsm,observation())
    advance(fsm,observation(ee_position=[.5,0,.025]))
    assert advance(fsm,observation(ee_position=[.5,0,.025],finger_position=[0,0],cube_contact_force=[10,10]),20)['phase']=='close'
    assert advance(fsm,observation(ee_position=[.5,0,.025],finger_position=[.02,.02],cube_contact_force=[10,0]),5)['phase']=='close'


def test_contact_enters_probe_but_object_follow_is_required_before_goal_lift():
    fsm = ReferenceFSM()
    advance(fsm,observation())
    advance(fsm,observation(ee_position=[.5,0,.025]))
    grasp=observation(ee_position=[.5,0,.025],finger_position=[.02,.02],cube_contact_force=[10,10])
    result=advance(fsm,grasp,14)
    assert result['phase']=='probe'
    assert advance(fsm,{**grasp,'ee_position':[.5,0,.075]},5)['phase']=='probe'
    result=advance(fsm,{**grasp,'ee_position':[.5,0,.075],'object_position':[.5,0,.07]})
    assert result['phase']=='lift'
    assert result['transition_reason']=='object_follows_probe_not_contact_alone'


def test_reference_freezes_and_loads_only_the_same_controller_and_task(tmp_path):
    import json
    from dataclasses import asdict

    import pytest

    from physicalevobench.v02.reference import ReferenceConfig
    from physicalevobench.v02.reference_artifact import freeze, load

    payload={'schema':'state-reference-artifact-1','source_commit':'a'*40,
             'reference_config':asdict(ReferenceConfig()),'horizon_s':10.,
             'task_version':'state-reference-h10-v1','checkpoint_sha256':'b'*64}
    path=tmp_path/'skill.json'
    freeze(payload,path)
    assert load(path)==payload
    value=json.loads(path.read_text())
    value['payload']['horizon_s']=5.
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError,match='digest'):
        load(path)
