"""Strict bounded public-state skill graph. No eval, imports, or arbitrary code."""

import math
from dataclasses import dataclass

from physicalevobench.v02.reference_artifact import digest

TARGETS={'object_above','object_grasp','anchor','probe','goal_offset','lift_initial',
         'place_above','place_lower','place_retreat','retreat_anchor'}
GUARDS={'pose','bilateral','follow','object_goal','elapsed','always'}
MODES={'approach','descend','close','probe','lift','hold','release','recover','failed'}
NODE_FIELDS={'id','target','gripper','guard','tolerance','dwell_s','minimum_s','timeout_s',
             'next','timeout','mode','offset_m'}


@dataclass(frozen=True)
class Program:
    nodes: tuple
    start: str='approach'
    max_retries: int=1

    def __post_init__(self):
        if not 1<=len(self.nodes)<=16 or type(self.max_retries) is not int or not 0<=self.max_retries<=2:
            raise ValueError('Bounded graph/retries required')
        ids=[]
        for n in self.nodes:
            if not isinstance(n,dict) or set(n)!=NODE_FIELDS:
                raise ValueError('Unknown node fields')
            if not isinstance(n['id'],str) or not n['id'].isidentifier() or len(n['id'])>32:
                raise ValueError('Short named node required')
            ids.append(n['id'])
            if (n['target'] not in TARGETS or n['guard'] not in GUARDS or n['mode'] not in MODES or
                    n['gripper'] not in ('open','close')):
                raise ValueError('Unknown public primitive')
            for key,lo,hi in [('tolerance',.005,.06),('dwell_s',.02,.5),('minimum_s',0.,1.),
                              ('timeout_s',.1,20.),('offset_m',0.,.15)]:
                v=n[key]
                if type(v) not in (int,float) or not math.isfinite(v) or not lo<=v<=hi:
                    raise ValueError('Program scalar outside bounded public range')
        if len(set(ids))!=len(ids) or self.start not in ids:
            raise ValueError('Unique nodes and defined entry required')
        if any(n[k] not in ids for n in self.nodes for k in ('next','timeout')):
            raise ValueError('Dangling program edge')
        object.__setattr__(self,'nodes',tuple(dict(n) for n in self.nodes))

    def to_dict(self):
        return {'schema':'core-skill-graph-1','start':self.start,'max_retries':self.max_retries,
                'nodes':[dict(n) for n in self.nodes]}

    @classmethod
    def from_dict(cls,value):
        if set(value)!={'schema','start','max_retries','nodes'} or value['schema']!='core-skill-graph-1':
            raise ValueError('Unsupported program schema')
        return cls(tuple(value['nodes']),value['start'],value['max_retries'])

    @property
    def sha256(self):
        return digest(self.to_dict())


def node(name,target,gripper,guard,next_node,mode=None,offset=0.,minimum=0.,timeout=20.,
         tolerance=.025,dwell=.06,on_timeout='failed'):
    return {'id':name,'target':target,'gripper':gripper,'guard':guard,'next':next_node,
            'timeout':on_timeout,'mode':mode or name,'offset_m':offset,'minimum_s':minimum,
            'timeout_s':timeout,'tolerance':tolerance,'dwell_s':dwell}


def initial_program(place=False):
    nodes=[node('approach','object_above','open','pose','descend',offset=.10),
           node('descend','object_grasp','open','pose','close',offset=.005,tolerance=.015),
           node('close','anchor','close','bilateral','probe',minimum=.20,timeout=1.2,on_timeout='recover'),
           node('probe','probe','close','follow','lift',offset=.05),
           node('lift','lift_initial' if place else 'goal_offset','close',
                'pose' if place else 'object_goal','transport' if place else 'hold',offset=.12),
           node('hold','goal_offset','close','always','hold',mode='hold'),
           node('recover','retreat_anchor','open','pose','approach',mode='recover',offset=.08),
           node('failed','anchor','open','always','failed',mode='failed')]
    if place:
        nodes.extend([node('transport','place_above','close','pose','lower',mode='lift',offset=.12),
                      node('lower','place_lower','close','pose','release',mode='lift',offset=.008,tolerance=.015),
                      node('release','place_lower','open','elapsed','retreat',mode='release',offset=.008,minimum=.35),
                      node('retreat','place_retreat','open','pose','done',mode='release',offset=.12),
                      node('done','place_retreat','open','always','done',mode='release',offset=.12)])
    return Program(tuple(nodes))


class ProgramFSM:
    def __init__(self,program):
        self.program=Program.from_dict(program.to_dict())
        self.nodes={n['id']:n for n in self.program.nodes}
        self.current=self.program.start
        self.age=self.dwell=0.
        self.anchor=self.offset=self.initial=self.probe_object=None
        self.retries=0
        self.transitions=0
        self.exhausted=False

    def target(self,n,obs):
        obj=obs['object_position']
        if self.initial is None:
            self.initial=list(obj)
            self.anchor=list(obs['ee_position'])
            self.offset=[a-b for a,b in zip(obs['ee_position'],obj,strict=True)]
        name,dz=n['target'],n['offset_m']
        if name in ('object_above','object_grasp'):
            return [*obj[:2],obj[2]+dz]
        if name=='anchor':
            return list(self.anchor)
        if name in ('probe','retreat_anchor'):
            return [*self.anchor[:2],self.anchor[2]+dz]
        if name=='goal_offset':
            return [a+b for a,b in zip(obs['goal_position'],self.offset,strict=True)]
        if name=='lift_initial':
            return [self.initial[0]+self.offset[0],self.initial[1]+self.offset[1],self.initial[2]+dz+self.offset[2]]
        # Public task geometry, defined from initial object position and held fixed.
        return [self.initial[0]+.12+self.offset[0],self.initial[1]+.12+self.offset[1],
                .021+dz+self.offset[2]]

    def update(self,obs,dt):
        if not math.isfinite(dt) or dt<=0:
            raise ValueError('Positive timestep required')
        for key in ('ee_position','object_position','goal_position','object_velocity','finger_position','cube_contact_force'):
            if not all(math.isfinite(x) for x in obs[key]):
                raise ValueError('Nonfinite public observation')
        if self.exhausted:
            return {'phase':'failed','program_node':self.current,'gripper':'open',
                    'target_position':list(obs['ee_position']),'transition_reason':'graph_budget_exhausted'}
        n=self.nodes[self.current]
        target=self.target(n,obs)
        relative=[a-b for a,b in zip(obs['ee_position'],obs['object_position'],strict=True)]
        bilateral=min(obs['cube_contact_force'])>=.5 and .005<sum(obs['finger_position'])/2<.035
        guard=n['guard']
        qualified={
            'pose':math.dist(obs['ee_position'],target)<=n['tolerance'] and obs['orientation_error']<=.15,
            'bilateral':bilateral,
            'follow':self.probe_object is not None and obs['object_position'][2]-self.probe_object[2]>=.02
                     and math.dist(relative,self.offset)<=.025,
            'object_goal':math.dist(obs['object_position'],obs['goal_position'])<.04,
            'elapsed':True,'always':True}[guard] and self.age>=n['minimum_s']
        self.dwell=self.dwell+dt if qualified else 0.
        next_id=self.current
        reason=None
        if self.dwell>=n['dwell_s']-1e-12:
            next_id=n['next']
            reason='public_guard_'+guard
        elif self.age>=n['timeout_s']:
            next_id=n['timeout']
            reason='bounded_node_timeout'
        if next_id!=self.current:
            self.transitions+=1
            # Global transition cap closes arbitrary cyclic-graph loopholes.
            if self.nodes[next_id]['mode']=='recover':
                self.retries+=1
            if self.retries>self.program.max_retries or self.transitions>64:
                self.exhausted=True
                return {'phase':'failed','program_node':self.current,'gripper':'open',
                        'target_position':list(obs['ee_position']),'transition_reason':'graph_budget_exhausted'}
            next_n=self.nodes[next_id]
            if next_n['mode'] in ('close','recover'):
                self.anchor=list(obs['ee_position'])
            if next_n['mode']=='probe':
                self.probe_object=list(obs['object_position'])
                self.offset=relative
            if n['mode'] in ('close','probe') and next_n['mode']=='lift':
                self.offset=relative
            self.current=next_id
            self.age=self.dwell=0.
            n=next_n
        else:
            self.age+=dt
        return {'phase':n['mode'],'program_node':self.current,'target_position':self.target(n,obs),
                'gripper':n['gripper'],'transition_reason':reason,
                'phase_age_s':self.age,'recoveries':self.retries}
