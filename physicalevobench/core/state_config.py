"""No actor weights: state IK configuration and explicit non-checkpoint identity."""

import hashlib
from dataclasses import dataclass

import yaml

from physicalevobench.v02.reference_artifact import digest

PROFILE='support-probe-restore-2'
TASK='core-place-public-v5-ready2'


class UnusedPolicy:
    def reset(self):
        pass

    def get_action(self,*args):
        raise RuntimeError('State-only execution must install an explicit program/reference; no PPO actor exists')


@dataclass(frozen=True)
class StateExecutionSkill:
    state_execution_sha256:str
    arm_action_gain:float=1.

    def to_dict(self):
        return {'schema':'state-execution-skill-1','state_execution_sha256':self.state_execution_sha256,
                'arm_action_gain':self.arm_action_gain}

    @property
    def sha256(self):
        return digest(self.to_dict())


def reference(old):
    return {'schema':'state-program-reference-1','reference_config':old['reference_config'],
            'task_version':TASK,'horizon_s':20.,'control_profile':'contact-integral-v1',
            'initialization_profile':PROFILE,'backend_commit':'c7edf3a9d5d8276565208f72422f8f8a0806d6cf',
            'weight_dependency':None,'scoring':'core-place-score-1'}


def worker_config(base,budget):
    context={'schema':'state-policy-context-1','reference':base}
    text=yaml.safe_dump(context,sort_keys=True)
    return {'state_policy_context':context,'state_execution_sha256':digest(context),
            'policy_config_sha256':hashlib.sha256(text.encode()).hexdigest(),
            'mode':'FixedHorizonDiagnostic','execution_layer':'TargetBounded',
            'reference_controller':'StateBasedReference','reference_config':base['reference_config'],
            'horizon_s':base['horizon_s'],'task_version':base['task_version'],
            'core_task':'initialization_diagnostic' if base['task_version']=='esl-initialization-diagnostic-v1' else 'place','physical_budget':budget,
            'control_profile':'contact-integral-v1','initialization_profile':PROFILE,
            'public_goal':[.62,.12,.021]}
