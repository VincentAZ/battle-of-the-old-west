"""Read-only CPU extraction and complete-bundle provenance for two staged clips.

Writes only inside the explicit isolated candidate directory. Original complete
contracts, expected poses, Content assets and runtime data are hash protected.
Freshly opens both saved blends and independently evaluates their 53 bones.
"""
import argparse,copy,json,os,shutil,sys,traceback
from pathlib import Path
import bpy
sys.path.insert(0,str(Path(__file__).resolve().parent))
from scientist_import_contract import BASE,ROOT,CONTRACT,EXPECTATIONS,DEST,sha,require,difference,check_transform,endpoint_checks

def convert(matrix):
    p,q,s=matrix.decompose()
    return {'translation_cm':[p.x*100,-p.y*100,p.z*100],'rotation_xyzw':[-q.x,q.y,-q.z,q.w],'scale':list(s)}
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--source',type=Path,required=True)
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:]);folder=args.source.resolve()
    require(folder.is_relative_to(BASE),'Candidate outside authoring directory')
    out=folder/'bundle';require(not out.exists(),'Preserve prior bundle');out.mkdir()
    original_runtime=ROOT/'game/OldWest/Content/Data/scientist-presentation.json'
    protected={str(p):sha(p) for p in (ROOT/'game/OldWest/Content').rglob('*') if p.is_file()}
    for p in (CONTRACT,EXPECTATIONS,BASE/'holster-v3/runtime-integration-contract.json'):protected[str(p)]=sha(p)
    old_complete=json.loads(CONTRACT.read_text());replacement_path=folder/'runtime-integration-contract.json';replacement=json.loads(replacement_path.read_text())
    complete=copy.deepcopy(old_complete);complete['status']='staged corrected two-animation bundle; native readback/visual review pending'
    complete['replaces_complete_contract']={'path':str(CONTRACT),'sha256':sha(CONTRACT)}
    for row in complete['contracts']:
        if Path(row['path']).name=='runtime-integration-contract.json' and 'holster-v3' in row['path']:
            row.update(path=str(replacement_path),sha256=sha(replacement_path))
    clips={c['asset']:c for c in replacement['clips']};require(len(clips)==2,'Only two replacement clips')
    for row in complete['animations']:
        if row['asset'] in clips:
            c=clips[row['asset']];require(sha(c['path'])==c['sha256'],'Changed export')
            row.update(source_fbx=c['path'],source_fbx_sha256=c['sha256'],expected_contract=str(replacement_path),seconds=c['duration_seconds'])
    require(complete['static_props']==old_complete['static_props'],'Props changed')
    complete_path=out/'complete-candidate-contract.json';complete_path.write_text(json.dumps(complete,indent=2)+'\n')
    dense=json.loads(EXPECTATIONS.read_text());old_dense=copy.deepcopy(dense)
    dense['status']='fresh CPU two-clip extraction; other11 clips and11props retained from accepted expectations; native readback pending'
    dense['complete_contract_sha256']=sha(complete_path);dense['extractor_sha256']=sha(__file__)
    provenance=dict(dense['provenance'])
    for p in [complete_path,replacement_path,folder/'manual-review.json',folder/'cloth-subframe-audit.json',folder/'untouched-dense-clock-audit.json']:
        provenance[str(p)]=sha(p)
    max_cm=max_angle=0.
    for name in ('Holster','Unholster'):
        blend=folder/f'Scientist_{name}_Candidate.blend';before=sha(blend);provenance[str(blend)]=before
        bpy.ops.wm.open_mainfile(filepath=str(blend),use_scripts=False)
        arm=bpy.data.objects['Survivor_Rig'];scene=bpy.context.scene
        require([b.name.removeprefix('mixamorig:') for b in arm.data.bones]==dense['bone_names'],'Rig bone identity/order')
        for b in arm.data.bones:
            n=b.name.removeprefix('mixamorig:');parent=b.parent.name.removeprefix('mixamorig:') if b.parent else 'Survivor_Rig'
            require(parent==dense['reference'][n]['parent'],'Rig parent changed',n)
            cm,degrees=difference(convert(arm.matrix_world@b.matrix_local),dense['reference'][n]['component_rest'])
            require(cm<.001 and degrees<.001,'Rig reference changed',n,cm,degrees)
        rows=[]
        for frame in range(1,92):
            scene.frame_set(frame);bpy.context.view_layer.update()
            bones={b.name.removeprefix('mixamorig:'):convert(arm.matrix_world@b.matrix) for b in arm.pose.bones}
            published=replacement['dense_expected_native_samples'][name][frame-1]
            for n,t in bones.items():
                check_transform(t,n);cm,degrees=difference(t,published['bones'][n]);max_cm=max(max_cm,cm);max_angle=max(max_angle,degrees)
                require(cm<.01 and degrees<.1,'Saved blend differs from exported expectation',name,frame,n,cm,degrees)
            rows.append({'frame':frame,'seconds':(frame-1)/30,'bones':bones})
        require(sha(blend)==before,'Source saved during extraction');dense['clips'][DEST+'/Animations/A_Scientist_'+name+'_Cm']=rows
        provenance[clips[DEST+'/Animations/A_Scientist_'+name+'_Cm']['path']]=clips[DEST+'/Animations/A_Scientist_'+name+'_Cm']['sha256']
    dense['provenance']=provenance
    endpoints=endpoint_checks(dense['clips'])
    for asset,rows in old_dense['clips'].items():
        if asset not in clips:require(dense['clips'][asset]==rows,'Unrelated clip expectation changed',asset)
    require(dense['props']==old_dense['props'],'Prop expectations changed')
    # Reversal checks use freshly evaluated poses rather than a reversed label.
    h=dense['clips'][DEST+'/Animations/A_Scientist_Holster_Cm'];u=dense['clips'][DEST+'/Animations/A_Scientist_Unholster_Cm']
    max_reverse_cm=max_reverse_angle=0.
    for a,b in zip(h,reversed(u)):
        for n,t in a['bones'].items():
            cm,degrees=difference(t,b['bones'][n]);max_reverse_cm=max(max_reverse_cm,cm);max_reverse_angle=max(max_reverse_angle,degrees)
            require(cm<.001 and degrees<.01,'Reverse pose changed',a['frame'],n)
    expectations_path=out/'import-expectations-v1.json';expectations_path.write_text(json.dumps(dense,separators=(',',':'))+'\n')
    runtime=json.loads(original_runtime.read_text());before_data=copy.deepcopy(runtime)
    runtime['complete_contract_sha256']=sha(complete_path)
    check=copy.deepcopy(runtime);check['complete_contract_sha256']=before_data['complete_contract_sha256'];require(check==before_data,'Runtime track/prop change')
    runtime_path=out/'scientist-presentation.json';runtime_path.write_text(json.dumps(runtime,separators=(',',':'))+'\n')
    backup=out/'protected-live-inputs';backup.mkdir();backups=[]
    for p in [original_runtime,*[ROOT/'game/OldWest/Content/Art/Survivors/ScientistAnalysis/Animations'/f'A_Scientist_{n}_Cm.uasset' for n in ('Holster','Unholster')]]:
        target=backup/p.name;shutil.copyfile(p,target);require(sha(p)==sha(target),'Backup mismatch')
        backups.append({'live':str(p),'backup':str(target),'sha256':sha(p)})
    require(all(sha(p)==h for p,h in protected.items()),'Protected original changed')
    manifest={'schema':'oldwest.scientist.two-clip-bundle.v1','status':'staged import-ready expectations; no native import or visual acceptance',
        'complete_contract':{'path':str(complete_path),'sha256':sha(complete_path)},'expectations':{'path':str(expectations_path),'sha256':sha(expectations_path)},
        'runtime_provenance_update':{'path':str(runtime_path),'sha256':sha(runtime_path),'only_semantic_change':'complete_contract_sha256'},
        'replacement_clips':replacement['clips'],'fresh_source_pose_checks':182*53,'source_expected_error_cm':max_cm,'source_expected_error_degrees':max_angle,
        'reverse_error_cm':max_reverse_cm,'reverse_error_degrees':max_reverse_angle,'endpoint_checks':endpoints,
        'retained_clips':11,'retained_props':11,'retained_rig_bones':53,'required_native_bones':54,
        'backup_inputs':backups,'protected_originals_unchanged':True,'protected_files':len(protected),'stager_sha256':sha(__file__)}
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print('SCIENTIST_REPLACEMENT_BUNDLE_STAGED '+json.dumps({k:v for k,v in manifest.items() if k not in ('endpoint_checks','replacement_clips','backup_inputs')}),flush=True)
try:main();code=0
except BaseException:traceback.print_exc();code=1
sys.stdout.flush();sys.stderr.flush();os._exit(code)
