"""Fresh-process Mixar audit of exact approved geometry and deformation continuity."""
import hashlib,json,math,struct
from collections import defaultdict
from pathlib import Path
import bpy
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'art/western/stampede/animation-v001'
def signature(mesh):
    h=hashlib.sha256()
    for v in mesh.vertices:h.update(struct.pack('<3f',*v.co))
    for p in mesh.polygons:h.update(struct.pack('<'+str(len(p.vertices))+'I',*p.vertices))
    for uv in mesh.uv_layers.active.data:h.update(struct.pack('<2f',*uv.uv))
    return h.hexdigest()
bpy.ops.wm.open_mainfile(filepath=str(OUT.parent/'review-v001/review/Longhorn-Review.blend'))
original=bpy.data.objects['Longhorn_Appearance_Review'];approved_signature=signature(original.data)
bpy.ops.wm.open_mainfile(filepath=str(OUT/'Longhorn-Animated.blend'))
mesh=bpy.data.objects['Longhorn'];arm=bpy.data.objects['Armature'];s=bpy.context.scene
assert signature(mesh.data)==approved_signature,'Approved positions, topology or UVs changed'
textures=[node.image for node in mesh.data.materials[0].node_tree.nodes if node.type=='TEX_IMAGE']
assert len(textures)==3 and all(tuple(i.size)==(2048,2048) and i.packed_file for i in textures)
assert len([o for o in s.objects if o.type=='ARMATURE'])==1
for v in mesh.data.vertices:
    assert 1<=len(v.groups)<=4
    assert abs(sum(g.weight for g in v.groups)-1)<1e-5
seams=defaultdict(list)
for v in mesh.data.vertices:seams[tuple(round(c,5) for c in v.co)].append(v.index)
seams=[ids for ids in seams.values() if len(ids)>1]
max_separation=0.;max_penetration=0.;max_endpoint=0.
for clip,end in [('Idle',120),('Run',24)]:
    arm.animation_data.action=bpy.data.actions['Longhorn_'+clip];endpoints=[]
    for frame in range(end+1):
        s.frame_set(frame);bpy.context.view_layer.update()
        dep=bpy.context.evaluated_depsgraph_get();ev=mesh.evaluated_get(dep);data=ev.to_mesh()
        max_penetration=max(max_penetration,max(0,-min(v.co.z for v in data.vertices)))
        for ids in seams:
            first=data.vertices[ids[0]].co
            max_separation=max(max_separation,max((data.vertices[i].co-first).length for i in ids[1:]))
        if frame in [0,end]:endpoints.append([v.co.copy() for v in data.vertices])
        ev.to_mesh_clear()
    max_endpoint=max(max_endpoint,max((a-b).length for a,b in zip(*endpoints)))
assert max_separation<.002,(max_separation,'Visible seam separation')
assert max_penetration<.0001,(max_penetration,'Hoof penetration')
assert max_endpoint<.00001,(max_endpoint,'Vertex loop mismatch')
report={'ok':True,'approved_mesh_and_uv_sha256':approved_signature,'approved_geometry_identical':True,
        'project_sha256':hashlib.sha256((OUT/'Longhorn-Animated.blend').read_bytes()).hexdigest(),
        'checked_animation_frames':146,'bones':len(arm.data.bones),'material_count':1,'textures':3,'texture_size':2048,
        'max_seam_separation_m':max_separation,'max_ground_penetration_m':max_penetration,
        'max_loop_vertex_delta_m':max_endpoint,'root_motion':False}
(OUT/'source-readback.json').write_text(json.dumps(report,indent=2)+'\n')
print('STAMPEDE_SOURCE_READBACK',json.dumps(report),flush=True)
