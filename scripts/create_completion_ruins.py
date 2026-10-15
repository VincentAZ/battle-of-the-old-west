"""Simple charred lower structures for the final four playable holding states."""
import sys,json,hashlib,math
from pathlib import Path
import bpy,bmesh
from mathutils import Vector,Matrix
from PIL import Image,ImageEnhance
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'scripts'));import export_holdings_mixar as ex
O=R/'art/western/holdings/expansion-review-v001';G=R/'art/western/holdings/expansion-game-v001';roster=json.loads((O/'roster-status.json').read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
for slug in ['crimp-house','rustlers-corral','quaker-settlement','dance-hall']:
 a=roster['assets'][slug];A=O/slug;E=json.loads((A/'historical-evidence.json').read_text());D=A/'ruin-completion-v001';assert not D.exists();D.mkdir();V=R/a['review_directory'];m=json.loads((V/'manifest.json').read_text());bpy.ops.wm.open_mainfile(filepath=str(V/m['project']),use_scripts=False);o=bpy.data.objects[m['mesh_object']];name=ex.asset_name(slug);o.name='SM_HoldingRuin_'+name
 # The ruin is a separate source. Cut away upper walls/roof; retain original
 # ground-level geometry and cap the surviving masonry/timber remnants.
 bm=bmesh.new();bm.from_mesh(o.data);z=.64 if slug!='rustlers-corral'else .52
 bmesh.ops.bisect_plane(bm,geom=list(bm.verts)+list(bm.edges)+list(bm.faces),dist=.00001,plane_co=(0,0,z),plane_no=(0,0,1),clear_outer=True,clear_inner=False)
 edges=[e for e in bm.edges if e.is_boundary];bmesh.ops.holes_fill(bm,edges=edges,sides=0);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(o.data);bm.free();o.data.update();o.data.calc_loop_triangles();assert len(o.data.loop_triangles)>0
 mat=o.data.materials[0].copy();o.data.materials.clear();o.data.materials.append(mat);base=next(x for x in m['textures']if x['channel']=='BaseColor');im=Image.open(V/base['file']).convert('RGB');im=ImageEnhance.Color(im).enhance(.25);im=ImageEnhance.Brightness(im).enhance(.24);texture=D/(name+'_Ruin_BaseColor.png');im.save(texture)
 for n in mat.node_tree.nodes:
  if n.type=='TEX_IMAGE'and n.image and Path(n.image.filepath).name==Path(base['file']).name:n.image=bpy.data.images.load(str(texture));n.image.pack()
 project=D/(name+'-Ruin-Review.blend');bpy.ops.wm.save_as_mainfile(filepath=str(project));scene=bpy.context.scene;scene.cycles.samples=12;views={}
 for key in['three-quarter','overhead']:
  cam=next(c for c in scene.objects if c.type=='CAMERA'and c.name.startswith('Review_'+key));scene.camera=cam;scene.render.filepath=str(D/(key+'.png'));bpy.ops.render.render(write_still=True);views[key]=sha(D/(key+'.png'))
 out=G/slug/'completion-exports-v002';out.mkdir(parents=True);bpy.ops.object.select_all(action='DESELECT');o.select_set(True);bpy.context.view_layer.objects.active=o;o.data.transform(Matrix.Rotation(math.pi,4,'Z'));fbx=out/(o.name+'.fbx');ex.export_fbx(fbx);(out/texture.name).write_bytes(texture.read_bytes());d=dict(slug=slug,fbx=fbx.name,fbx_sha256=sha(fbx),texture=texture.name,texture_sha256=sha(texture),triangles=len(o.data.loop_triangles),source_project=str(project.relative_to(R)),source_project_sha256=sha(project),views=views,scope='First-pass fictional charred lower structure; bespoke jagged collapse detail deferred.');(out/'export.json').write_text(json.dumps(d,indent=2)+'\n');(D/'authoring.json').write_text(json.dumps(d,indent=2)+'\n');print('FIRST_PASS_RUIN',slug,flush=True)
