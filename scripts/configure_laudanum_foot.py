"""Place missing/correct malformed foot joints against the approved Doctor boots."""
import bpy, json, sys
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from weather_drifter_review import geometry_hash
OUT=ROOT/'art/western/crew/playable-v001/laudanum-doctor'
approval=json.loads((OUT.parent.parent/'review-v003/appearance-approval.json').read_text())['projects']['laudanum-doctor']
bpy.ops.wm.open_mainfile(filepath=str(ROOT/approval['path']),use_scripts=False)
obj=bpy.data.objects['laudanum_doctor_Appearance_Review']
points=[obj.matrix_world@v.co for v in obj.data.vertices]
settings=json.loads((OUT/'rig-settings.json').read_text())
settings['source_geometry_uv_sha256']=geometry_hash(obj)
settings['override_existing_rest_bones']=True
settings['additional_rest_bones']={}
overrides=[];measurements={}
for side,sign in [('Left',1),('Right',-1)]:
    foot=[p for p in points if p.x*sign>0 and p.z<.14]
    lo=Vector([min(p[i] for p in foot) for i in range(3)])
    hi=Vector([max(p[i] for p in foot) for i in range(3)])
    x=(lo.x+hi.x)/2
    # Heel/ankle lies toward +Y; toes point toward -Y in the approved source.
    ankle=Vector((x,hi.y-.035,.115))
    toe=Vector((x,lo.y+.045,.045))
    settings['additional_rest_bones'][side+'Foot']={'head':list(ankle),'tail':list(toe)}
    settings['additional_rest_bones'][side+'ToeBase']={'head':list(toe),'tail':list(toe+Vector((0,-.04,0)))}
    count=0
    for i,p in enumerate(points):
        if p.x*sign<=0 or p.z>=.205:continue
        # All shoe vertices move rigidly; distribute ankle rotation smoothly
        # over the trouser cuff above the shoe, with no mesh edits.
        t=max(0,min(1,(p.z-.105)/.100));t=t*t*(3-2*t)
        weights={side+'Foot':1-t,side+'Leg':t}
        overrides.append({'vertex_indices':[i],'weights':weights});count+=1
    measurements[side]={'lower_mesh_min':list(lo),'lower_mesh_max':list(hi),'ankle':list(ankle),'toe':list(toe),'painted_vertices':count}
settings['weight_overrides']=overrides
settings.setdefault('motion_constraints',[]).append('Locally placed weighted feet and smooth ankle cuffs; independent toe articulation remains frozen at bind. Validate walk floor contact and ankle bends in Unreal.')
settings['mapping_notes']=settings.get('mapping_notes',[])+['Provider omitted RightFoot and both toes; provider LeftFoot endpoint was below ground. Foot joints locally reconstructed from approved boot geometry, with source-preserving ankle weights.']
(OUT/'rig-settings.json').write_text(json.dumps(settings,indent=2)+'\n')
(OUT/'foot-placement.json').write_text(json.dumps(measurements,indent=2)+'\n')
print(json.dumps(measurements,indent=2))
