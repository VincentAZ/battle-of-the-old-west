"""Explicit sediment-colour water with world-space ripples; expansion only."""
import hashlib,json
from pathlib import Path
import unreal
ROOT=Path(__file__).resolve().parents[1]
P=ROOT/'art/western/holdings/expansion-game-v001/smugglers-landing/water-v003'
C=ROOT/'game/OldWest/Content'
D='/Game/Art/Western/ExpansionHoldings/SmugglersLanding'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
snapshot=lambda:{str(p.relative_to(C)):sha(p) for p in C.rglob('*') if p.is_file()}
before=snapshot();lib=unreal.EditorAssetLibrary;ml=unreal.MaterialEditingLibrary
assert not lib.does_asset_exist(D+'/M_SmugglersWaterV003')
mat=unreal.AssetToolsHelpers.get_asset_tools().create_asset('M_SmugglersWaterV003',D,unreal.Material,unreal.MaterialFactoryNew())
mat.set_editor_property('tangent_space_normal',False)
def node(kind,x,y,**props):
 n=ml.create_material_expression(mat,getattr(unreal,kind),x,y)
 for k,v in props.items():n.set_editor_property(k,v)
 return n
linear=lambda x:((x+.055)/1.055)**2.4 if x>.04045 else x/12.92
colour=node('MaterialExpressionVectorParameter',-500,-250,parameter_name='WaterColor',default_value=unreal.LinearColor(*[linear(x)for x in [.44,.37,.23]],1))
assert ml.connect_material_property(colour,'RGB',unreal.MaterialProperty.MP_BASE_COLOR)
for prop,value,y in [(unreal.MaterialProperty.MP_ROUGHNESS,.25,-100),(unreal.MaterialProperty.MP_SPECULAR,.5,0)]:
 assert ml.connect_material_property(node('MaterialExpressionConstant',-500,y,r=value),'',prop)
world=node('MaterialExpressionWorldPosition',-900,200)
time=node('MaterialExpressionTime',-900,400)
normal=node('MaterialExpressionCustom',-500,220,description='Horizontal river: small world-space ripple slopes',output_type=unreal.CustomMaterialOutputType.CMOT_FLOAT3)
entries=[]
for name in ['P','T']:
 e=unreal.CustomInput();e.set_editor_property('input_name',name);entries.append(e)
normal.set_editor_property('inputs',entries)
normal.set_editor_property('code','return normalize(float3(0.04*cos(P.x*0.12+T*0.8),0.025*sin(P.y*0.19-T*0.6),1.0));')
assert ml.connect_material_expressions(world,'',normal,'P')
assert ml.connect_material_expressions(time,'',normal,'T')
assert ml.connect_material_property(normal,'',unreal.MaterialProperty.MP_NORMAL)
ml.recompile_material(mat);assert lib.save_loaded_asset(mat,only_if_is_dirty=False)
mesh=lib.load_asset(D+'/SM_HoldingWater_SmugglersLanding');mesh.set_material(0,mat)
assert lib.save_loaded_asset(mesh,only_if_is_dirty=False)
after=snapshot();changed={p for p,h in before.items() if after.get(p)!=h}
assert changed=={'Art/Western/ExpansionHoldings/SmugglersLanding/SM_HoldingWater_SmugglersLanding.uasset'},changed
(P/'unreal-change.json').write_text(json.dumps(dict(ok=True,material=mat.get_path_name(),colour_linear=[linear(x)for x in [.44,.37,.23]],changed={p:{'before':before[p],'after':after[p]}for p in changed},added={p:h for p,h in after.items()if p not in before},all_other_existing_content_unchanged=True),indent=2)+'\n')
print('SMUGGLERS_WATER_V003_AUTHORED',flush=True)
