"""Check saved dune winding/contact and central-board scenery clearance."""
import hashlib
import json
from pathlib import Path
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'art/western/regions/desert-v004'
SOURCE=ROOT/'art/world/ContinuousTerrain.blend'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    manifest=json.loads((OUT/'manifest.json').read_text())
    assert sha(SOURCE)==manifest['source_terrain_sha256']
    assert sha(OUT/'DesertScenery.blend')==manifest['source_sha256']
    bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
    terrain=next(o for o in bpy.context.scene.objects if o.type=='MESH')
    bvh=BVHTree.FromObject(terrain,bpy.context.evaluated_depsgraph_get())
    bpy.ops.wm.open_mainfile(filepath=str(OUT/'DesertScenery.blend'))
    results=[]
    for ob in bpy.data.objects:
        if ob.type!='MESH':continue
        intrusions=[v.index for v in ob.data.vertices if abs(v.co.x)<28 and -3 < -v.co.y < 58]
        assert not intrusions,(ob.name,len(intrusions))
        record=dict(name=ob.name,vertices=len(ob.data.vertices),central_board_intrusions=0)
        if 'Dune' in ob.name:
            nz=min(p.normal.z for p in ob.data.polygons);assert nz>0,(ob.name,nz)
            delta=[]
            for v in ob.data.vertices:
                hit,_,_,_=bvh.ray_cast(Vector((v.co.x,v.co.y,400)),Vector((0,0,-1)),800)
                assert hit is not None
                delta.append(v.co.z-hit.z)
            assert min(delta)>-.009 and max(delta)>4,(ob.name,min(delta),max(delta))
            xs=[v.co.x for v in ob.data.vertices];ys=[v.co.y for v in ob.data.vertices]
            boundary=[v.index for v in ob.data.vertices if min(abs(v.co.x-min(xs)),abs(v.co.x-max(xs)),
                      abs(v.co.y-min(ys)),abs(v.co.y-max(ys)))<.0001]
            assert max(abs(delta[i]) for i in boundary)<.009
            record.update(minimum_upward_normal_z=nz,minimum_surface_offset_m=min(delta),
                          maximum_dune_height_m=max(delta),maximum_boundary_gap_m=max(abs(delta[i]) for i in boundary))
        results.append(record)
    assert len(results)==3
    (OUT/'geometry-validation.json').write_text(json.dumps(dict(ok=True,source_sha256=manifest['source_sha256'],
        original_terrain_sha256=sha(SOURCE),central_clear_rectangle_native_metres=[-28,28,-3,58],meshes=results),indent=2)+'\n')
    print('DESERT_GEOMETRY_VALIDATED',results)

if __name__=='__main__':main()
