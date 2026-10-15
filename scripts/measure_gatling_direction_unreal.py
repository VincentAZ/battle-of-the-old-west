"""Read-only GeometryScript audit of corrected imported Gatling mesh. Enable GeometryScripting."""
import hashlib,itertools,json,math,traceback
from pathlib import Path
import unreal
ROOT=Path(__file__).resolve().parents[1];out=ROOT/'art/western/crew/playable-v001/gatling-gunner'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
report={'status':'failed','scope':'actual imported LOD0 geometry; both Configure facing transforms, not two-peer side coverage'}
try:
 source=json.loads((out/'gatling-direction-landmarks.json').read_text());rig=json.loads((out/'rig-validation.json').read_text());assets=json.loads((out/'unreal-assets.json').read_text())
 assert assets['rig_project_sha256']==rig['project_sha256']
 assert assets['approved_source_sha256']==source['source_project_sha256']
 asset='/Game/Art/Western/Crew/GatlingGunner/SK_GatlingGunner';mesh=unreal.load_asset(asset);dynamic=unreal.DynamicMesh()
 result=unreal.GeometryScript_AssetUtils.copy_mesh_from_skeletal_mesh(mesh,dynamic,unreal.GeometryScriptCopyMeshFromAssetOptions(),unreal.GeometryScriptMeshReadLOD())
 print('GATLING_COPY_RESULT',result,flush=True)
 q=unreal.GeometryScript_MeshQueries;count=q.get_vertex_count(dynamic);assert count>10000
 points=[]
 for i in range(count):
  v,valid=q.get_vertex_position(dynamic,i);assert valid
  points.append((v.x,v.y,v.z))
 # Infer axis conversion from actual imported points; do not assume FBX axis conventions.
 grid={}
 for v in points:grid.setdefault(tuple(math.floor(x/.1) for x in v),[]).append(v)
 def nearest(p):
  cell=tuple(math.floor(x/.1) for x in p);candidates=[]
  for delta in itertools.product((-1,0,1),repeat=3):candidates.extend(grid.get(tuple(cell[j]+delta[j] for j in range(3)),()))
  return min(candidates,key=lambda v:math.dist(v,p)) if candidates else None
 sourcepoints=source['vertices_m'];sample=sourcepoints[::max(1,len(sourcepoints)//200)]
 fits=[]
 for perm in itertools.permutations(range(3)):
  for signs in itertools.product((-1,1),repeat=3):
   errors=[]
   for v in sample:
    p=[100*v[perm[j]]*signs[j] for j in range(3)];n=nearest(p);errors.append(math.dist(n,p) if n else 999.)
   fits.append((sum(e<.01 for e in errors),max(errors),perm,signs))
 fits.sort(reverse=True);matched,error,perm,signs=fits[0];assert matched==len(sample) and error<.01,(matched,error,len(sample),fits[:3])
 def point(v):return [100*v[perm[j]]*signs[j] for j in range(3)]
 def center(ids):
  matched=[]
  for i in ids:
   expected=point(sourcepoints[i]);actual=nearest(expected);assert actual and math.dist(actual,expected)<.01
   matched.append(actual)
  return [sum(v[j] for v in matched)/len(matched) for j in range(3)]
 front=center(source['muzzle_front_vertices']);rear=center(source['barrel_rear_vertices']);direction=[front[j]-rear[j] for j in range(3)];length=math.sqrt(sum(x*x for x in direction));direction=[x/length for x in direction]
 checks=[]
 for side,yaw,target in [(0,180,[0,-1,0]),(1,0,[0,1,0])]:
  angle=math.radians(yaw);x,y,z=direction;world=[math.cos(angle)*x-math.sin(angle)*y,math.sin(angle)*x+math.cos(angle)*y,z];dot=sum(a*b for a,b in zip(world,target));assert dot>.98,(side,world,dot)
  checks.append({'side':side,'configure_yaw_degrees':yaw,'world_muzzle_direction':world,'opposing_camp_direction':target,'alignment_cosine':dot})
 file=ROOT/'game/OldWest/Content/Art/Western/Crew/GatlingGunner/SK_GatlingGunner.uasset'
 report.update(status='passed',mesh_asset=asset,mesh_package_sha256=sha(file),rig_project_sha256=rig['project_sha256'],approved_source_sha256=source['source_project_sha256'],landmarks_sha256=sha(out/'gatling-direction-landmarks.json'),imported_vertex_count=count,basis_source_axis_indices=list(perm),basis_axis_signs=list(signs),basis_sample_count=len(sample),basis_sample_max_error_cm=error,muzzle_center_local_cm=front,barrel_rear_center_local_cm=rear,muzzle_direction_mesh_local=direction,configure_side_checks=checks,content_modified=False)
except Exception:
 report['error']=traceback.format_exc();raise
finally:
 (out/'unreal-gatling-direction.json').write_text(json.dumps(report,indent=2)+'\n');print('GATLING_DIRECTION',json.dumps(report),flush=True)
