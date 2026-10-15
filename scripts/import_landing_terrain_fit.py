"""Copy regional materials and add bounded, runtime-only landing foundations."""
import hashlib
import json
from pathlib import Path
import unreal

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'art/western/holdings/ground-fit-smugglers-landing-v002'
CONTENT = ROOT/'game/OldWest/Content'
DEST = '/Game/Art/Western/ExpansionHoldings/LandingTerrainFitV002'
LIB, EDIT = unreal.EditorAssetLibrary, unreal.MaterialEditingLibrary
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
brief = json.loads((OUT/'render-brief.json').read_text())
assert all(sha(ROOT/p) == h for p, h in brief['source_records'].items())
before = {p: sha(p) for p in CONTENT.rglob('*') if p.is_file()}
assert not LIB.does_directory_exist(DEST), 'Preserve prior material candidates'
assets = []
PROFILE = '''
struct LandingFit {
 float2 Local(float2 P,float3 O,float3 F) {
  float2 d=P-O.xy;
  return float2(d.x*F.x+d.y*F.y,-d.x*F.y+d.y*F.x)/max(F.z,.001);
 }
 float Weight(float2 P,float3 O,float3 F) {
  if(F.z<.01)return 0;
  float2 p=Local(P,O,F);
  return (1-smoothstep(500,700,abs(p.x)))*(1-smoothstep(450,650,p.y))*(1-smoothstep(300,355,-p.y));
 }
 float Z(float2 P,float H,float3 O,float3 F) {
  return H+clamp(O.z-H,-200,200)*Weight(P,O,F);
 }
};
LandingFit fit;
'''
for region in ('Winter', 'Pine', 'River'):
    source = '/Game/Art/Western/Regions/Materials/M_Region_'+region+'Ground'
    target = DEST+'/M_LandingTerrain_'+region
    mat = LIB.duplicate_asset(source, target)
    assert mat
    mat.set_editor_property('max_world_position_offset_displacement', 200)
    world = EDIT.create_material_expression(mat, unreal.MaterialExpressionWorldPosition)
    world.set_editor_property('world_position_shader_offset', unreal.WorldPositionIncludedOffsets.WPT_EXCLUDE_ALL_SHADER_OFFSETS)
    inputs = {'World': world}
    for i in range(6):
        for prefix in ('LandingOrigin', 'LandingFrame'):
            name = prefix+str(i)
            node = EDIT.create_material_expression(mat, unreal.MaterialExpressionVectorParameter)
            node.set_editor_property('parameter_name', name)
            node.set_editor_property('default_value', unreal.LinearColor(0, 0, 0, 0))
            inputs[name] = node
    custom = EDIT.create_material_expression(mat, unreal.MaterialExpressionCustom)
    custom.set_editor_property('output_type', unreal.CustomMaterialOutputType.CMOT_FLOAT3)
    declarations = []
    for name in inputs:
        item = unreal.CustomInput(); item.set_editor_property('input_name', name); declarations.append(item)
    custom.set_editor_property('inputs', declarations)
    code = PROFILE+'float offset=0;\n'
    for i in range(6):
        # Extent.z enables a live registration. Repeated calls use separate
        # lexical scopes; no injected global state or material collection.
        code += f'''{{
offset+=fit.Z(World.xy,World.z,LandingOrigin{i},LandingFrame{i})-World.z;
}}\n'''
    custom.set_editor_property('code', code+'return float3(0,0,clamp(offset,-200,200));')
    for name, node in inputs.items():
        assert EDIT.connect_material_expressions(node, '', custom, name)
    assert EDIT.connect_material_property(custom, '', unreal.MaterialProperty.MP_WORLD_POSITION_OFFSET)
    EDIT.recompile_material(mat)
    assert LIB.save_loaded_asset(mat, only_if_is_dirty=False)
    assets.append(mat.get_path_name())

# The separate base retains its reviewed colour graph. Only the dry apron
# moves, following the exact displaced terrain triangles at its XY position.
mat = LIB.duplicate_asset('/Game/Art/Western/ExpansionHoldings/Shared/M_HoldingBase', DEST+'/M_LandingDryBank')
assert mat
mat.set_editor_property('max_world_position_offset_displacement', 200)
world = EDIT.create_material_expression(mat, unreal.MaterialExpressionWorldPosition)
world.set_editor_property('world_position_shader_offset', unreal.WorldPositionIncludedOffsets.WPT_EXCLUDE_ALL_SHADER_OFFSETS)
inputs = {'World': world}
for name in ('GroundOrigin', 'GroundFrame'):
    node = EDIT.create_material_expression(mat, unreal.MaterialExpressionVectorParameter)
    node.set_editor_property('parameter_name', name)
    node.set_editor_property('default_value', unreal.LinearColor(0,0,0,0))
    inputs[name] = node
enabled = EDIT.create_material_expression(mat, unreal.MaterialExpressionScalarParameter)
enabled.set_editor_property('parameter_name', 'FitEnabled'); enabled.set_editor_property('default_value', 0)
inputs['Enabled'] = enabled
height = EDIT.create_material_expression(mat, unreal.MaterialExpressionTextureObject)
height.set_editor_property('texture', LIB.load_asset('/Game/Art/Western/ExpansionHoldings/GroundFitV001/T_ArenaGroundHeight'))
height.set_editor_property('sampler_type', unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR)
inputs['Height'] = height
custom = EDIT.create_material_expression(mat, unreal.MaterialExpressionCustom)
custom.set_editor_property('output_type', unreal.CustomMaterialOutputType.CMOT_FLOAT3)
declarations = []
for name in inputs:
    item = unreal.CustomInput(); item.set_editor_property('input_name', name); declarations.append(item)
custom.set_editor_property('inputs', declarations)
custom.set_editor_property('code', PROFILE+'''
if(Enabled<.5 || GroundFrame.z<.01)return float3(0,0,0);
float2 local=fit.Local(World.xy,GroundOrigin,GroundFrame);
float dry=smoothstep(270,280,-local.y);
float2 p=clamp((World.xy+6500)/50,0,259.9999),cell=floor(p),f=frac(p);
float4 a=Texture2DSampleLevel(Height,HeightSampler,(cell+.5)/261,0);
float4 b=Texture2DSampleLevel(Height,HeightSampler,(cell+float2(1.5,.5))/261,0);
float4 c=Texture2DSampleLevel(Height,HeightSampler,(cell+float2(.5,1.5))/261,0);
float4 d=Texture2DSampleLevel(Height,HeightSampler,(cell+1.5)/261,0);
float4 h=(round(float4(a.r,b.r,c.r,d.r)*255)*256+round(float4(a.g,b.g,c.g,d.g)*255)-32768)/16;
float2 corner=cell*50-6500;
h.x=fit.Z(corner,h.x,GroundOrigin,GroundFrame);
h.y=fit.Z(corner+float2(50,0),h.y,GroundOrigin,GroundFrame);
h.z=fit.Z(corner+float2(0,50),h.z,GroundOrigin,GroundFrame);
h.w=fit.Z(corner+50,h.w,GroundOrigin,GroundFrame);
float z;
if(a.b>.5) {
 z=f.y<=f.x?h.x+(h.y-h.x)*f.x+(h.w-h.y)*f.y:h.x+(h.w-h.z)*f.x+(h.z-h.x)*f.y;
} else {
 z=f.x+f.y<=1?h.x+(h.y-h.x)*f.x+(h.z-h.x)*f.y:h.w+(h.z-h.w)*(1-f.x)+(h.y-h.w)*(1-f.y);
}
return float3(0,0,(z-GroundOrigin.z)*dry+1.5*smoothstep(280,355,-local.y));
''')
for name, node in inputs.items():
    assert EDIT.connect_material_expressions(node, '', custom, name)
assert EDIT.connect_material_property(custom, '', unreal.MaterialProperty.MP_WORLD_POSITION_OFFSET)
EDIT.recompile_material(mat)
assert LIB.save_loaded_asset(mat, only_if_is_dirty=False)
assets.append(mat.get_path_name())
assert all(sha(p) == h for p, h in before.items())
report = dict(ok=True, assets=assets, existing_content_unchanged=len(before),
    source_records=brief['source_records'], brief_sha256=sha(OUT/'render-brief.json'),
    content_sha256={str(p.relative_to(ROOT)):sha(p) for p in (CONTENT/DEST.removeprefix('/Game/')).glob('*.uasset')},
    importer_sha256=sha(Path(__file__)), native_review='pending')
(OUT/'unreal-import.json').write_text(json.dumps(report, indent=2)+'\n')
(OUT/'source-script.py').write_bytes(Path(__file__).read_bytes())
unreal.log('LANDING_TERRAIN_MATERIALS_CREATED')
