"""Versioned desert replacement, retaining approved woodland/river branches."""
import ast
import hashlib
import json
import shutil
import sys
from pathlib import Path
import unreal

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import import_regional_scenery as regional

OUT = ROOT/'art/western/regions/desert-v001'
CONTENT = ROOT/'game/OldWest/Content'
LIB, EDIT = unreal.EditorAssetLibrary, unreal.MaterialEditingLibrary
BRIEF = ROOT/'research/western-presentation/desert-v001.json'
DESERT = '''
float band=.5+.5*sin(World.z/160+patch*3.1);
float3 clay=lerp(float3(.24,.075,.025),float3(.46,.245,.095),saturate(patch*.9+band*.25));
float wash=smoothstep(.48,.72,patch)*.65;
float3 sand=float3(.48,.32,.16);
float grains=clamp(.64+detail*1.15,.64,1.45);
return lerp(clay,sand,wash)*grains*(.85+variation*.3);
'''

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()

def expressions(mat):
    seen=set()
    def walk(node):
        if not node or node.get_path_name() in seen:return
        seen.add(node.get_path_name())
        yield node
        for child in EDIT.get_inputs_for_material_expression(mat,node):yield from walk(child)
    for prop in (unreal.MaterialProperty.MP_BASE_COLOR, unreal.MaterialProperty.MP_WORLD_POSITION_OFFSET):
        yield from walk(EDIT.get_material_property_input_node(mat,prop))

def main():
    assert json.loads(BRIEF.read_text())['sources']
    OUT.mkdir(parents=True,exist_ok=True)
    source=ast.parse((ROOT/'scripts/import_regional_scenery.py').read_text())
    fn=next(n for n in source.body if isinstance(n,ast.FunctionDef) and n.name=='ground')
    cases=next(ast.literal_eval(n.value.value) for n in fn.body if isinstance(n,ast.Assign) and n.targets[0].id=='code')
    winter=cases['winter']
    originals={p:sha(p) for p in CONTENT.rglob('*.uasset')}
    def revise(mat):
        count=0
        for node in expressions(mat):
            if isinstance(node,unreal.MaterialExpressionCustom):
                code=node.get_editor_property('code')
                if winter in code:
                    node.set_editor_property('code',code.replace(winter,DESERT));count+=1
        if count:
            EDIT.recompile_material(mat)
            assert LIB.save_loaded_asset(mat,only_if_is_dirty=False)
        return count
    new=[]
    for src,dst in [
      ('/Game/Art/Western/Regions/Materials/M_Region_WinterGround','/Game/Art/Western/Regions/Materials/M_Region_DesertGround'),
      ('/Game/Art/Western/ExpansionHoldings/LandingTerrainFitV002/M_LandingTerrain_Winter','/Game/Art/Western/ExpansionHoldings/LandingTerrainFitV002/M_LandingTerrain_Desert')]:
        assert not LIB.does_asset_exist(dst),dst
        mat=LIB.duplicate_asset(src,dst);assert mat
        assert revise(mat)==1,dst
        new.append(dst)
    changed=[]
    for path in LIB.list_assets('/Game/Art/Western/ExpansionHoldings',recursive=True):
        if 'GroundFit' not in path:continue
        mat=LIB.load_asset(path)
        if not isinstance(mat,unreal.Material):continue
        if not any(isinstance(n,unreal.MaterialExpressionCustom) and winter in n.get_editor_property('code') for n in expressions(mat)):continue
        disk=CONTENT/(mat.get_path_name().split('.')[0].removeprefix('/Game/')+'.uasset')
        backup=OUT/'before'/disk.relative_to(CONTENT)
        backup.parent.mkdir(parents=True,exist_ok=True)
        assert not backup.exists()
        shutil.copy2(disk,backup)
        assert revise(mat)==1,path
        changed.append(dict(asset=path,before=sha(backup),after=sha(disk)))
    modified={p for p,h in originals.items() if sha(p)!=h}
    assert len(modified)==len(changed),(len(modified),len(changed))
    report=dict(ok=True,brief_sha256=sha(BRIEF),new_assets=new,shared_fit_materials=changed,
                unchanged_existing_assets=len(originals)-len(modified),visual_review='pending')
    (OUT/'unreal-import.json').write_text(json.dumps(report,indent=2)+'\n')
    unreal.log('DESERT_IMPORTED '+str(len(changed)))

if __name__=='__main__':main()
