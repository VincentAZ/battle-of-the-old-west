"""Ground distant scenery against the original visual terrain, not its smaller collider."""
import hashlib
import json
import math
import random
from pathlib import Path
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'art/world/ContinuousTerrain.blend'
OUT=ROOT/'art/western/regions/terrain-v001'
HEADER=ROOT/'game/OldWest/Source/OldWestGame/Private/OldWestRegionalPlacements.inl'


def main():
    bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
    terrain=next(o for o in bpy.context.scene.objects if o.type=='MESH')
    bvh=BVHTree.FromObject(terrain,bpy.context.evaluated_depsgraph_get())
    regions={}
    for region,seed in [('Pine',1887),('River',1879)]:
        rng=random.Random(seed);placed=[]
        for attempt in range(10000):
            if len(placed)==180:break
            x,y=rng.uniform(-230,230),rng.uniform(-200,250)
            if abs(x)<47 and -28<y<78:continue
            if math.hypot(x,y)>270:continue
            bank=abs(x-(127-18*math.sin(y/130)-8*math.sin(y/57)))
            if region=='River' and not 44<bank<95:continue
            if any(math.hypot(x-p['x']/100,y-p['y']/100)<11 for p in placed):continue
            hit,normal,index,distance=bvh.ray_cast(Vector((x,-y,400)),Vector((0,0,-1)),800)
            assert hit is not None,(x,y)
            variant=2 if region=='River' and bank<52 else rng.randint(0,2 if region=='Pine' else 1)
            # FBX -Y forward gives Unreal the same X and reflected Y.
            # Existing Unreal terrain bounds do not reveal handedness; source
            # placement is converted by the same FBX coordinate convention.
            placed.append(dict(x=x*100,y=y*100,z=hit.z*100,scale=rng.uniform(.7,1.25),yaw=rng.uniform(0,360),variant=variant))
        regions[region]=placed
    lines=['// Generated from original terrain by scripts/author_regional_placements.py.',
           '// Scenery only: no collision, rules or public-state fields.',
           'struct FRegionalTreePlacement { float X,Y,Z,Scale,Yaw; int32 Variant; };']
    for name,placements in regions.items():
        lines.append('static const FRegionalTreePlacement '+name+'Trees[] = {')
        for p in placements:lines.append('    {'+', '.join(f'{p[k]:.5f}f' for k in ('x','y','z','scale','yaw'))+f", {p['variant']}"+'},')
        lines.append('};')
    HEADER.write_text('\n'.join(lines)+'\n')
    (OUT/'tree-placements.json').write_text(json.dumps(dict(source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),regions=regions),indent=2)+'\n')
    print('REGIONAL_PLACEMENTS_AUTHORED',[(k,len(v)) for k,v in regions.items()])


if __name__=='__main__':main()
