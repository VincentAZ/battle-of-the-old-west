"""Export reviewed expansion ruins and measure healthy fire supports in one pass."""
import sys,json,hashlib,math,shutil
from pathlib import Path
import bpy
from mathutils import Vector,Matrix
from mathutils.bvhtree import BVHTree
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'scripts'));import export_holdings_mixar as ex
O=R/'art/western/holdings/expansion-review-v001';G=R/'art/western/holdings/expansion-game-v001';roster=json.loads((O/'roster-status.json').read_text());slugs=json.loads((R/'research/western-presentation/implementation-status.json').read_text())['assistant_owned']['2_expansion_holdings']['static_only_native_pending'];sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
for slug in slugs:
 a=roster['assets'][slug];name=ex.asset_name(slug);out=G/slug/'completion-exports-v001';out.mkdir(exist_ok=True)
 v=R/a['review_directory'];m=json.loads((v/'manifest.json').read_text());bpy.ops.wm.open_mainfile(filepath=str(v/m['project']),use_scripts=False);o=bpy.data.objects[m['mesh_object']];pts=[o.matrix_world@p.co for p in o.data.vertices];tree=BVHTree.FromPolygons(pts,[list(f.vertices)for f in o.data.polygons]);hi=max(p.z for p in pts);fires=[]
 for side in[-1,1]:
  x=side*.6;y=side*.4;hit=tree.ray_cast(Vector((x,y,hi+1)),Vector((0,0,-1)))[0]
  if hit is None:hit=min(pts,key=lambda p:(p.x-x)**2+(p.y-y)**2-.01*p.z)
  fires.append([-hit.x*100,-hit.y*100,hit.z*100])
 report=dict(slug=slug,fire_points_cm=fires,healthy_project_sha256=m['project_sha256'])
 if a.get('ruin_review'):
  d=(R/a['ruin_review']).parent;p=d/(name+'-Ruin.blend');auth=json.loads((d/'authoring.json').read_text());assert sha(p)==auth['project_sha256'];bpy.ops.wm.open_mainfile(filepath=str(p),use_scripts=False);meshes=[o for o in bpy.context.scene.objects if o.type=='MESH'];assert len(meshes)==1,(slug,[o.name for o in meshes]);o=meshes[0];o.data.transform(Matrix.Rotation(math.pi,4,'Z')@o.matrix_world);o.matrix_world=Matrix.Identity(4);o.name='SM_HoldingRuin_'+name;bpy.ops.object.select_all(action='DESELECT');o.select_set(True);bpy.context.view_layer.objects.active=o;fbx=out/(o.name+'.fbx');ex.export_fbx(fbx);t=next(d.glob('*Ruin_BaseColor.png'));shutil.copy2(t,out/t.name);o.data.calc_loop_triangles();report.update(fbx=fbx.name,fbx_sha256=sha(fbx),texture=t.name,texture_sha256=sha(t),triangles=len(o.data.loop_triangles),source_project=str(p.relative_to(R)),source_project_sha256=sha(p))
 (out/'export.json').write_text(json.dumps(report,indent=2)+'\n');print('COMPLETION_EXPORT',slug,flush=True)
