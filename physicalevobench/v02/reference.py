"""Observable-state reference FSM; teacher calibration, never Agent learning.

No mass/seed/evaluator result input. Guards use geometry, bilateral cube contact
and object motion; force readings alone do not certify a successful grasp.
"""

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class ReferenceConfig:
    approach_clearance_m: float = .10
    grasp_offset_m: float = .005
    approach_tolerance_m: float = .025
    descend_tolerance_m: float = .015
    orientation_tolerance_rad: float = .15
    dwell_s: float = .06
    minimum_close_s: float = .20
    contact_force_n: float = .5
    probe_lift_m: float = .05
    object_follow_m: float = .02
    relative_drift_m: float = .025
    close_timeout_s: float = 1.2
    maximum_recoveries: int = 1
    joint_integral_gain_s: float = 0.
    joint_integral_limit_rad: float = .12


class BoundedJointIntegral:
    def __init__(self,gain,limit):
        if not math.isfinite(gain) or not math.isfinite(limit) or gain<0 or not 0<limit<=.2:
            raise ValueError('Finite nonnegative feedback gain and bounded joint offset required')
        self.gain,self.limit,self.value=gain,limit,[0.]*7

    def update(self,error,dt,active):
        if len(error)!=7 or not all(math.isfinite(v) for v in error) or not math.isfinite(dt) or dt<=0:
            raise ValueError('Seven finite joint errors and positive interval required')
        self.value = ([max(-self.limit,min(self.limit,value+self.gain*dt*delta))
                       for value,delta in zip(self.value,error,strict=True)] if active else [0.]*7)
        return list(self.value)


class ReferenceFSM:
    def __init__(self, config=None):
        self.cfg = config or ReferenceConfig()
        self.phase, self.age, self.dwell = 'approach', 0., 0.
        self.anchor = self.probe_object = self.offset = None
        self.recoveries = 0

    def target(self, obs):
        obj = obs['object_position']
        if self.phase == 'approach':
            return [*obj[:2], obj[2]+self.cfg.approach_clearance_m]
        if self.phase == 'descend':
            return [*obj[:2], obj[2]+self.cfg.grasp_offset_m]
        if self.phase == 'close':
            return list(self.anchor)
        if self.phase == 'probe':
            return [*self.anchor[:2], self.anchor[2]+self.cfg.probe_lift_m]
        if self.phase in ('lift','hold'):
            return [a+b for a,b in zip(obs['goal_position'],self.offset,strict=True)]
        return list(self.anchor)

    def update(self, obs, dt):
        if not math.isfinite(dt) or dt <= 0:
            raise ValueError('Positive observation interval required')
        for key in ('ee_position','object_position','goal_position','object_velocity','finger_position','cube_contact_force'):
            if not all(math.isfinite(v) for v in obs[key]):
                raise ValueError('Finite public reference observations required')
        if not math.isfinite(obs['orientation_error']):
            raise ValueError('Finite orientation error required')
        cfg, old = self.cfg, self.phase
        target = self.target(obs)
        position_error = math.dist(obs['ee_position'],target)
        aligned = obs['orientation_error'] <= cfg.orientation_tolerance_rad
        bilateral = min(obs['cube_contact_force']) >= cfg.contact_force_n
        width = sum(obs['finger_position'])/2
        qualified = False
        reason = None
        if old == 'approach':
            qualified = position_error <= cfg.approach_tolerance_m and aligned
            reason = 'pregrasp_pose_reached'
        elif old == 'descend':
            qualified = position_error <= cfg.descend_tolerance_m and aligned
            reason = 'grasp_pose_reached'
        elif old == 'close':
            qualified = self.age >= cfg.minimum_close_s and bilateral and .005 < width < .035
            reason = 'bilateral_cube_contact_with_nonempty_aperture'
        elif old == 'probe':
            object_lift = obs['object_position'][2]-self.probe_object[2]
            relative = [a-b for a,b in zip(obs['ee_position'],obs['object_position'],strict=True)]
            qualified = object_lift >= cfg.object_follow_m and math.dist(relative,self.offset) <= cfg.relative_drift_m
            reason = 'object_follows_probe_not_contact_alone'
        elif old == 'lift':
            qualified = math.dist(obs['object_position'],obs['goal_position']) < .04
            reason = 'object_enters_goal_region'
        self.dwell = self.dwell+dt if qualified else 0.
        if qualified and self.dwell >= cfg.dwell_s-1e-12:
            self.phase = {'approach':'descend','descend':'close','close':'probe','probe':'lift','lift':'hold'}[old]
            if self.phase == 'close':
                self.anchor = list(obs['ee_position'])
            if self.phase == 'probe':
                self.probe_object = list(obs['object_position'])
                self.offset = [a-b for a,b in zip(obs['ee_position'],obs['object_position'],strict=True)]
            if self.phase == 'lift':
                self.offset = [a-b for a,b in zip(obs['ee_position'],obs['object_position'],strict=True)]
        elif old == 'close' and self.age >= cfg.close_timeout_s:
            self._recover(obs)
            reason = 'close_timeout_without_verified_contact'
        elif old in ('probe','lift','hold') and math.dist(
                [a-b for a,b in zip(obs['ee_position'],obs['object_position'],strict=True)],self.offset) > .06:
            self._recover(obs)
            reason = 'lost_object_relative_pose'
        elif old == 'recover' and position_error <= cfg.approach_tolerance_m:
            self.phase = 'approach' if self.recoveries <= cfg.maximum_recoveries else 'failed'
            reason = 'retreat_reached'
        changed = old != self.phase
        if changed:
            self.age, self.dwell = 0., 0.
        else:
            self.age += dt
        target = self.target(obs)
        return {'phase':self.phase,'previous_phase':old,'phase_age_s':self.age,
                'transition_reason':reason if changed else None,'target_position':target,
                'position_error_m':math.dist(obs['ee_position'],target),
                'orientation_error_rad':obs['orientation_error'], 'bilateral_contact':bilateral,
                'gripper':'close' if self.phase in ('close','probe','lift','hold') else 'open',
                'recoveries':self.recoveries}

    def _recover(self, obs):
        self.recoveries += 1
        self.phase = 'recover'
        self.anchor = [*obs['ee_position'][:2],obs['ee_position'][2]+.08]
