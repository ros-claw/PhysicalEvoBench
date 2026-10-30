"""Optional lossless evidence bundles, independently extractable without weights."""

import argparse
import hashlib
import json
import tarfile
from pathlib import Path, PurePosixPath

from physicalevobench.doctor import save_json, sha256
from physicalevobench.v02.reference_artifact import digest


def safe_members(archive):
    for member in archive.getmembers():
        p=PurePosixPath(member.name)
        if p.is_absolute() or '..' in p.parts or not member.isfile():
            raise ValueError('Only safe regular evidence members are accepted')
        yield member


def package(root,out,studies):
    import subprocess

    out.mkdir(parents=True,exist_ok=False)
    files=[]
    commits=set()
    for study in studies:
        for f in sorted(study.rglob('*')):
            if not f.is_file() or f.is_symlink() or any(x in f.parts for x in ('recorder','__pycache__')):
                continue
            if f.suffix in ('.hdf5','.pt','.onnx','.mp4'):
                continue
            name=study.name+'/'+str(f.relative_to(study))
            files.append({'path':name,'sha256':sha256(f),'size':f.stat().st_size,'local':f})
            if f.name=='registration.json':
                data=json.loads(f.read_text())
                for key in ('source_commit','launcher_commit','scheduler_source_commit'):
                    if data.get(key):
                        commits.add(data[key])
            if f.name=='prelaunch_recovery.json':
                commits.add(json.loads(f.read_text())['recovery_launcher_commit'])
            if f.name=='source_identity.json':
                commits.add(json.loads(f.read_text())['commit'])
    groups=[]
    group=[]
    size=0
    for f in files:
        if group and size+f['size']>40*1024**2:
            groups.append(group)
            group=[]
            size=0
        group.append(f)
        size+=f['size']
    if group:
        groups.append(group)
    archives=[]
    for i,group in enumerate(groups):
        dest=out/f'data-{i:02d}.tar.gz'
        with tarfile.open(dest,'w:gz') as archive:
            for f in group:
                archive.add(f['local'],arcname=f['path'],recursive=False)
        archives.append({'file':dest.name,'sha256':sha256(dest),'size':dest.stat().st_size})
    sources=[]
    for commit in sorted(commits):
        dest=out/f'source-{commit[:12]}.tar.gz'
        # Export the exact registered source, not the current modified worktree.
        data=subprocess.check_output(['git','archive','--format=tar.gz',commit,'physicalevobench'],cwd=root)
        dest.write_bytes(data)
        sources.append({'commit':commit,'file':dest.name,'sha256':sha256(dest)})
    manifest={'schema':'core-evidence-delivery-1','studies':[s.name for s in studies],
              'files':[{k:v for k,v in f.items() if k!='local'} for f in files],
              'archives':archives,'sources':sources,
              'scope':'Raw physics and model/tool evidence; no licensed weights. Offline audit is not new physics.'}
    save_json(out/'manifest.json',manifest)
    checks=[p for p in sorted(out.iterdir()) if p.is_file()]
    (out/'SHA256SUMS').write_text(''.join(f'{sha256(p)}  {p.name}\n' for p in checks))
    return {'files':len(files),'archives':len(archives),'sources':len(sources),
            'bytes':sum(a['size'] for a in archives)}


def verify(evidence,out):
    from physicalevobench.core.audit import audit_pilot, audit_session
    from physicalevobench.core.flow import summarize as summarize_flow
    from physicalevobench.core.parameter_space import summarize

    manifest=json.loads((evidence/'manifest.json').read_text())
    out.mkdir(parents=True,exist_ok=False)
    for a in manifest['archives']:
        path=evidence/a['file']
        if sha256(path)!=a['sha256']:
            raise ValueError('Archive hash changed')
        with tarfile.open(path,'r:gz') as archive:
            for member in safe_members(archive):
                target=out/member.name
                if target.exists():
                    raise ValueError('Duplicate evidence file')
                target.parent.mkdir(parents=True,exist_ok=True)
                target.write_bytes(archive.extractfile(member).read())
    for f in manifest['files']:
        path=out/f['path']
        if path.stat().st_size!=f['size'] or sha256(path)!=f['sha256']:
            raise ValueError('Raw evidence digest changed')
    sources={}
    for a in manifest['sources']:
        path=evidence/a['file']
        if sha256(path)!=a['sha256']:
            raise ValueError('Source archive changed')
        with tarfile.open(path,'r:gz') as archive:
            sources[a['commit']]={m.name:hashlib.sha256(archive.extractfile(m).read()).hexdigest()
                                   for m in archive.getmembers() if m.isfile() and m.name.endswith('.py')}
    source_checks=0
    results={}
    for name in manifest['studies']:
        study=out/name
        reg=json.loads((study/'registration.json').read_text())
        status=json.loads((study/'status.json').read_text())
        identities=list(study.rglob('source_identity.json'))
        if reg.get('source_sha256'):
            identities.append(None)
        for path in identities:
            identity=json.loads(path.read_text()) if path else {'commit':reg['source_commit'],'files':reg['source_sha256']}
            for file,expected_digest in identity['files'].items():
                if sources[identity['commit']].get(file)!=expected_digest:
                    raise ValueError('Registered source differs from bundled immutable source')
                source_checks+=1
        if status['status']=='CANCELLED_BEFORE_LAUNCH':
            if status['actual_episodes']!=0 or list(study.rglob('launch.json')):
                raise ValueError('Cancelled reservation executed physics')
            results[name]={'status':'CANCELLED_BEFORE_LAUNCH','episodes':0}
        elif status['status']!='COMPLETED':
            # Failure evidence stays published, but never becomes a passed study.
            results[name]={'status':status['status'],'scope':'Incomplete attempts retained; no completed study claim'}
        elif reg['schema']=='esl-learning-1':
            from physicalevobench.core.learning import summarize as summarize_learning
            recorded=json.loads((study/'results.json').read_text())
            results[name]=summarize_learning(study)
            if results[name]!=recorded:
                raise ValueError('Stored executable-skill results differ from recomputation')
        elif reg['schema'] in ('esl-development-1','esl-qualification-1','core-standalone-smoke-1'):
            data=audit_session(study/'native')
            for i,row in enumerate(data):
                original=reg['job'] if reg['schema']=='core-standalone-smoke-1' else reg['jobs'][i]
                actual=json.loads((study/'native/requests'/f'{i:03d}.json').read_text())
                if original!=actual:
                    raise ValueError('Executed task differs from original registration')
            scores={}
            for r in data:
                scores.setdefault(r['core_identity'].get('method','smoke'),[]).append(r['success'])
            if reg['schema']=='esl-qualification-1':
                q=json.loads((study/'qualification.json').read_text())
                gap=sum(scores['strong'])-sum(scores['starter'])
                noise=abs(sum(scores['strong'])-sum(scores['identity_strong']))
                qualified=(all(scores['strong']) and all(scores['query_geometry_reference']) and
                           not any(scores['force_open']) and gap>noise and
                           not any(r['diagnostic']['hard_boundary_terminated'] for r in data))
                if (q['scores']!=scores or q['status']!=('QUALIFIED' if qualified else 'DEV') or
                        q['registration_sha256']!=digest(reg)):
                    raise ValueError('Stored qualification differs from raw measured response')
            elif reg['schema']=='esl-development-1':
                recorded=json.loads((study/'result.json').read_text())
                for method,booleans in scores.items():
                    if (recorded['methods'][method]['successes']!=sum(booleans) or
                            recorded['methods'][method]['episodes']!=len(booleans)):
                        raise ValueError('Stored development response differs from raw outcomes')
            else:
                if (study/'imported_artifact.json').exists():
                    from physicalevobench.core.artifact import load as load_imported
                    imported=load_imported(study/'imported_artifact.json')
                    if (reg['job']['program']!=imported['payload']['skill'] or
                            reg['job']['identity']['effective_artifact_hash']!=imported['effective_artifact_hash']):
                        raise ValueError('Imported smoke artifact differs from actual executed program')
                recorded=json.loads((study/'result.json').read_text())
                if recorded['task_success']!=data[0]['success'] or recorded['steps']!=data[0]['steps']:
                    raise ValueError('Standalone result differs from raw physics')
            results[name]={'audit':'PASS','episodes':len(data),'successes':sum(r['success'] for r in data),
                           'scores':scores}
        elif reg['schema']=='v02-diagnostics-1':
            recorded=json.loads((study/'parameter_space_results.json').read_text())
            results[name]=summarize(study)
            if results[name]!=recorded:
                raise ValueError('Stored B1 analysis differs from independent recomputation')
        elif reg['schema']=='core-pilot-1':
            recorded=json.loads((study/'pilot_results.json').read_text())
            results[name]=audit_pilot(study)
            if results[name]!=recorded:
                raise ValueError('Stored Agent comparison differs from independent recomputation')
            if (study/'lift_followup.json').exists():
                from physicalevobench.core.metrics import lift_followup
                from physicalevobench.v02.audit import records
                extra={}
                for arm in reg['evaluation_order']:
                    worker=study/('test-'+arm)
                    data=[json.loads(line) for line in (worker/'episodes.jsonl').read_text().splitlines()]
                    extra[arm]=[{'condition_id':r['condition_id'],**lift_followup(
                        records(worker/'episodes'/r['episode_id']/'physics.jsonl.gz'))} for r in data]
                if json.loads((study/'lift_followup.json').read_text())!={'schema':'core-T0-followup-report-1','arms':extra}:
                    raise ValueError('Additive T0 terminal/departure conclusions changed')
        elif reg['schema']=='core-flow-1':
            recorded=json.loads((study/'flow_results.json').read_text())
            results[name]=summarize_flow(study)
            if results[name]!=recorded:
                raise ValueError('Stored task-flow conclusions differ from independent recomputation')
        elif reg['schema']=='core-place-study-1':
            data=audit_session(study/'native')
            recorded=json.loads((study/'place_results.json').read_text())
            positive=[r for r,j in zip(data,reg['jobs'],strict=True) if not j['force_open']]
            negative=[r for r,j in zip(data,reg['jobs'],strict=True) if j['force_open']]
            for key,group in [('positive',positive),('negative',negative)]:
                if recorded[key]!={'successes':sum(r['success'] for r in group),'episodes':len(group)}:
                    raise ValueError('Stored task calibration counts differ from raw state scoring')
            if reg['phase']=='development':
                gate=sum(r['success'] for r in positive)>=3 and not any(
                    r['success'] for r in negative) and not any(r['diagnostic']['hard_boundary_terminated'] for r in data)
                if recorded['development_qualified']!=gate:
                    raise ValueError('Development qualification changed')
            else:
                gate=(not any(r['success'] for r in negative) and
                      not any(r['diagnostic']['hard_boundary_terminated'] for r in data) and
                      all(sum(r['success'] for r,j in zip(data,reg['jobs'],strict=True) if
                              not j['force_open'] and j['condition']['object_mass_kg']==m)>=2 for m in (.1,.4)))
                if recorded['independent_gate_passed']!=gate:
                    raise ValueError('Independent confirmation decision changed')
            if (study/'release_diagnosis.json').exists():
                from physicalevobench.core.details import release_details
                if json.loads((study/'release_diagnosis.json').read_text())!=release_details(study,write=False):
                    raise ValueError('Release failure observations differ from actual physical trace')
            results[name]={'audit':'PASS','episodes':len(data),'successes':sum(r['success'] for r in data)}
        else:
            raise ValueError('Unknown completed Core study')
    receipt={'schema':'core-delivery-audit-1','status':'PASS','raw_files':len(manifest['files']),
             'registered_source_checks':source_checks,'studies':results,
             'scope':'Independent extraction and CPU recomputation; no new model, training or physics.'}
    save_json(out/'public_delivery_audit.json',receipt)
    return receipt


def main():
    p=argparse.ArgumentParser()
    sub=p.add_subparsers(dest='command',required=True)
    pack=sub.add_parser('package')
    pack.add_argument('--output',required=True)
    pack.add_argument('--studies',nargs='+',required=True)
    check=sub.add_parser('verify')
    check.add_argument('--evidence',required=True)
    check.add_argument('--output',required=True)
    a=p.parse_args()
    if a.command=='package':
        result=package(Path.cwd(),Path(a.output),[Path(s) for s in a.studies])
    else:
        result=verify(Path(a.evidence),Path(a.output))
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    main()
