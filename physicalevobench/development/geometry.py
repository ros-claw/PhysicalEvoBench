"""Read authored cached USD collision metadata without loading PhysX or changing assets."""

import argparse
import json
from pathlib import Path

from physicalevobench.doctor import save_json, sha256


def inspect(path):
    from pxr import Gf, Usd, UsdGeom, UsdPhysics
    stage = Usd.Stage.Open(str(path))
    if not stage:
        raise ValueError('Could not compose cached USD')
    cache = UsdGeom.BBoxCache(Usd.TimeCode.Default(), [UsdGeom.Tokens.default_,
                             UsdGeom.Tokens.render, UsdGeom.Tokens.proxy],False,True)
    colliders = []
    for prim in Usd.PrimRange(stage.GetPseudoRoot(), Usd.TraverseInstanceProxies()):
        if not prim.HasAPI(UsdPhysics.CollisionAPI):
            continue
        box = cache.ComputeWorldBound(prim).ComputeAlignedRange()
        attributes = {a.GetName(): str(a.Get()) for a in prim.GetAttributes()
                      if any(s in a.GetName().lower() for s in ('collision', 'contactoffset',
                              'restoffset', 'approximation', 'size', 'extent', 'radius', 'xform'))}
        matrix=UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
        vertices=[]
        if prim.GetTypeName()=='Cube':
            half=float(UsdGeom.Cube(prim).GetSizeAttr().Get())/2
            vertices=[Gf.Vec3d(x,y,z) for x in (-half,half) for y in (-half,half) for z in (-half,half)]
        elif prim.GetTypeName()=='Mesh':
            vertices=[Gf.Vec3d(v) for v in UsdGeom.Mesh(prim).GetPointsAttr().Get()]
        transformed=[matrix.Transform(v) for v in vertices]
        analytic={'min':[min(v[i] for v in transformed) for i in range(3)],
                  'max':[max(v[i] for v in transformed) for i in range(3)],
                  'vertices':len(vertices)} if transformed else None
        colliders.append({'analytic_primitive_or_mesh_bound':analytic,'path': str(prim.GetPath()), 'type': prim.GetTypeName(),
                          'schemas': list(prim.GetAppliedSchemas()),
                          'world_transform':str(UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(Usd.TimeCode.Default())),
                          'bboxcache_empty':box.IsEmpty(),'authored_stage_bound_min': None if box.IsEmpty() else list(box.GetMin()),
                          'authored_stage_bound_max': None if box.IsEmpty() else list(box.GetMax()), 'attributes': attributes})
    return {'file': str(path), 'sha256': sha256(path), 'metres_per_unit': UsdGeom.GetStageMetersPerUnit(stage),
            'colliders': colliders, 'scope': 'Authored USD collider API/geometry and offsets; not live cooked PhysX hull or measured support contact'}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--assets', nargs='+', required=True)
    p.add_argument('--output', required=True)
    a = p.parse_args()
    value = {'schema': 'authored-usd-collision-inspection-1', 'physical_episodes': 0,
             'assets': [inspect(Path(path)) for path in a.assets],
             'scene_transform_note': 'Arena scales DexCube by (.8,.8,.8); table world pose adds (.5,0,0) and rotates 90deg about Z. These asset-stage bounds do not include that outer scene transform.'}
    save_json(a.output, value)
    print(json.dumps({'physical_episodes': 0, 'colliders': [len(x['colliders']) for x in value['assets']]}))


if __name__ == '__main__':
    main()
