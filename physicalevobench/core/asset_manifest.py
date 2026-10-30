"""Hash resolved USD dependency layer contents; no task episode or asset redistribution."""

import argparse
import hashlib
import json
from pathlib import Path

from physicalevobench.doctor import save_json


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--run-dir',required=True)
    out=Path(p.parse_args().run_dir)
    cfg=json.loads((out/'config.json').read_text())
    from isaaclab_arena.cli.isaaclab_arena_cli import get_isaaclab_arena_cli_parser
    from isaaclab_arena.utils.isaaclab_utils.simulation_app import SimulationAppContext

    app=get_isaaclab_arena_cli_parser().parse_args(['--device','cuda:0'])
    with SimulationAppContext(app):
        from pxr import UsdUtils
        layers={}
        roots=[]
        for uri in cfg['usd_roots']:
            try:
                loaded,assets,unresolved=UsdUtils.ComputeAllDependencies(uri)
                keys=[]
                for layer in loaded:
                    name=layer.identifier
                    if name not in layers:
                        content=layer.ExportToString().encode()
                        layers[name]={'identifier':name,'resolved_path':str(layer.resolvedPath),
                                      'serialized_usda_sha256':hashlib.sha256(content).hexdigest(),
                                      'serialized_bytes':len(content)}
                    keys.append(name)
                roots.append({'uri':uri,'status':'RESOLVED' if loaded and not unresolved else 'INCOMPLETE',
                              'layer_identifiers':keys,'non_layer_asset_references':list(map(str,assets)),
                              'unresolved':list(map(str,unresolved))})
            except Exception as error:
                roots.append({'uri':uri,'status':'not_measured','reason':str(error)[:300]})
        save_json(out/'asset_manifest.json',{'schema':'esl-usd-dependency-content-1','roots':roots,'layers':layers,
                  'physical_episodes':0,'PPO_weights_used':False,
                  'hash_kind':'SHA256 of each dependency layer serialized to USDA by the pinned runtime; not original binary bytes. Texture/non-layer asset content not hashed; no vision claim.',
                  'scope':'Resolved USD physics/geometry dependency provenance; hashes only, no licensed asset content redistributed. Same-machine snapshot, not a second-machine verification.'})


if __name__=='__main__':
    main()
