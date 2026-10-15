"""Audit recorded Con Man analysis playback; no Prospector skin/sole claim.

Reuses the immutable native pose/prop/rifle checks. Con Man has the shared rig but
uses SurvivorA geometry, so the Scientist-specific vertex tables are not used.
"""
import argparse,copy,hashlib,json
from pathlib import Path
import audit_scientist_native_contacts as base

def main():
    parser=argparse.ArgumentParser();parser.add_argument('run',type=Path);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();base.require(not args.output.exists(),'Preserve previous report')
    ref=base.Reference();ref.landmarks={'points':[]}
    audit=base.Auditor(ref);inputs=[];mesh_evidence=[]
    empty_probes=[]
    def observe_without_inapplicable_probe(raw):
        row=copy.deepcopy(raw);p=row['playback'];key='unit_manual' if p['active'] else 'last_sample_unit_manual';m=p[key]
        probe=m.get('ground_probe')
        if probe:
            # Native deliberately returns a nonmatching empty placeholder for
            # other meshes. Preserve that evidence, without treating it as12
            # actual Prospector sole vertices or applying the wrong geometry.
            audit.check(probe.get('source_mesh_matches') is False and probe.get('points')==[],
                'mimic_ground_probe_explicitly_inapplicable')
            empty_probes.append({'sample_frame':probe.get('sample_frame'),'query_frame':probe.get('query_frame'),
                'source_mesh_matches':probe.get('source_mesh_matches'),'points':len(probe.get('points',[]))})
            m.pop('ground_probe')
        audit.observe(row)
    files=list(args.run.glob('*/scientist-samples.jsonl'));base.require(len(files)==1,'Expected one recorded resolution')
    path=files[0];data=path.read_bytes();inputs.append({'path':str(path.resolve()),'sha256':hashlib.sha256(data).hexdigest()})
    for line in data.decode().splitlines():
        if not line.strip():continue
        observe_without_inapplicable_probe(json.loads(line))
    result_path=args.run/'result.json';final=base.read(result_path)['scientist_final']
    observe_without_inapplicable_probe({'playback':final['playback'],'analysis':{'active':[],'history':[final]}})
    inputs.append({'path':str(result_path.resolve()),'sha256':base.sha(result_path)})
    wanted='/Game/Art/Survivors/SurvivorA/SKM_Survivor_A_Cm.SKM_Survivor_A_Cm'
    for path in sorted(files[0].parent.glob('scientist-*.bracket.json')):
        data=base.read(path)
        for when in ('before','after'):
            state=data[when]['cinematic']
            for p in state['scientist_analysis']['playbacks']:
                units=[u for u in state['units'] if u['id']==p['performer_id'] and u['side']==p['performer_side']]
                audit.check(len(units)==1,'capture_actual_mimic_present',path=str(path),when=when)
                if len(units)!=1:continue
                u=units[0];m=u['manual_presentation'];pm=p['unit_manual']
                audit.check(u['card_id']=='con_man' and u['visual_mesh']==wanted,'capture_actual_mimic_mesh',card=u['card_id'],mesh=u['visual_mesh'])
                audit.check(m['sample_frame']==pm['sample_frame'] and m['body_bone_revision']==pm['body_bone_revision'],
                    'capture_same_manual_bone_frame',path=str(path),when=when)
                mesh_evidence.append({'path':str(path.resolve()),'sha256':base.sha(path),'when':when,'id':u['id'],'side':u['side'],
                    'card_id':u['card_id'],'visual_mesh':u['visual_mesh'],'phase':p['phase'],'sample_frame':m['sample_frame']})
    audit.check(bool(mesh_evidence),'mimic_capture_mesh_evidence_present')
    report=audit.report();report['schema']='oldwest.scientist.mimic-native-contact-audit.v1'
    report['methods']['skin']='Not evaluated: Scientist-specific source landmarks do not describe the Con Man SurvivorA mesh.'
    report['ground_probe']={'evaluated':False,'reason':'Scientist-specific sole landmarks intentionally not applied to Mimic.',
        'explicit_empty_nonmatching_placeholders':len(empty_probes),'all_placeholders_empty_nonmatching':all(p['points']==0 and p['source_mesh_matches'] is False for p in empty_probes)}
    report['capture_mesh_identity']=mesh_evidence;report['inputs']=inputs
    report['auditor_sha256']=base.sha(Path(base.__file__));report['mimic_observer_sha256']=base.sha(__file__)
    report['limitations']+=['No source-skin, costume clearance, sole support or Con Man material acceptance. Actual images require separate review.']
    report['observed_input_files_unchanged_at_finish']=all(base.sha(i['path'])==i['sha256'] for i in inputs)
    report['retained_completion']={'reason':final['completion_reason'],'path':str(result_path.resolve())}
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'ok':report['ok'],'compared_rows':report['compared_rows'],'failures':report['failures_count'],'report':str(args.output)}))
    return 0 if report['ok'] else 1
if __name__=='__main__':raise SystemExit(main())
