"""Task-dispatched persistent library: preserve T0 while learning a T1 program."""

from dataclasses import dataclass

from physicalevobench.core.program import Program, initial_program
from physicalevobench.v02.reference_artifact import ReferenceSkill, digest


@dataclass(frozen=True)
class SkillLibrary:
    lift: ReferenceSkill
    place: Program

    def to_dict(self):
        return {'schema':'core-skill-library-1','tasks':{'lift':self.lift.to_dict(),
                                                       'place':self.place.to_dict()}}

    @classmethod
    def from_dict(cls,value):
        if (set(value)!={'schema','tasks'} or value['schema']!='core-skill-library-1' or
                set(value['tasks'])!={'lift','place'}):
            raise ValueError('Unknown task library fields')
        return cls(ReferenceSkill.from_dict(value['tasks']['lift']),Program.from_dict(value['tasks']['place']))

    @property
    def sha256(self):
        return digest(self.to_dict())


def from_reference_skill(skill,place_program=None):
    value=(Program.from_dict(place_program).to_dict() if place_program is not None
           else initial_program(True).to_dict())
    for n in value['nodes']:
        if n['id']=='approach':
            n['offset_m']=skill.approach_clearance_m
        if n['id']=='close':
            n['minimum_s']=skill.minimum_close_s
    return SkillLibrary(skill,Program.from_dict(value))


def call_schema():
    node_fields={
        'id':{'type':'string'},'target':{'type':'string'},'gripper':{'type':'string','enum':['open','close']},
        'guard':{'type':'string'},'mode':{'type':'string'},'next':{'type':'string'},'timeout':{'type':'string'},
        **{k:{'type':'number'} for k in ('tolerance','dwell_s','minimum_s','timeout_s','offset_m')}}
    program={'type':'object','additionalProperties':False,
             'properties':{'schema':{'type':'string','enum':['core-skill-graph-1']},'start':{'type':'string'},
                           'max_retries':{'type':'integer','minimum':0,'maximum':2},
                           'nodes':{'type':'array','minItems':1,'maxItems':16,'items':{
                               'type':'object','properties':node_fields,'required':list(node_fields),'additionalProperties':False}}},
             'required':['schema','start','max_retries','nodes']}
    skill={'type':'object','additionalProperties':False,
           'properties':{'schema':{'type':'string','enum':['reference-skill-1']},
                         'base_reference_sha256':{'type':'string'},
                         'approach_clearance_m':{'type':'number','minimum':.08,'maximum':.12},
                         'minimum_close_s':{'type':'number','minimum':.2,'maximum':.7}},
           'required':['schema','base_reference_sha256','approach_clearance_m','minimum_close_s']}
    library={'type':'object','additionalProperties':False,
             'properties':{'schema':{'type':'string','enum':['core-skill-library-1']},
                           'tasks':{'type':'object','properties':{'lift':skill,'place':program},
                                    'required':['lift','place'],'additionalProperties':False}},
             'required':['schema','tasks']}
    properties={'tool':{'type':'string','enum':['run_trial','freeze']},'library':library,
                'training_condition_handle':{'type':'string'},'memory':{'type':'string','maxLength':4000}}
    return {'type':'object','additionalProperties':False,'properties':properties,'required':list(properties)}
