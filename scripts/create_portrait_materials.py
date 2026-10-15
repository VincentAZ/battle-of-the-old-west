"""Author small, self-contained shaders for the native animated card portraits.

Run with UnrealEditor -run=pythonscript -script=<this file> -nullrhi. Only assets
under /Game/Art/CardPortraits are created/updated; no level or shared camp material
is changed. Shader animation is a four-second periodic function, not a video.
"""
import json
from pathlib import Path
import unreal

ROOT=Path(__file__).resolve().parents[1]
DEST='/Game/Art/CardPortraits'
LIB=unreal.EditorAssetLibrary
EDIT=unreal.MaterialEditingLibrary
TOOLS=unreal.AssetToolsHelpers.get_asset_tools()


def material(name,translucent=False):
    path=DEST+'/'+name
    mat=LIB.load_asset(path) if LIB.does_asset_exist(path) else TOOLS.create_asset(name,DEST,unreal.Material,unreal.MaterialFactoryNew())
    assert mat, path
    EDIT.delete_all_material_expressions(mat)
    mat.set_editor_property('two_sided',True)
    mat.set_editor_property('blend_mode',unreal.BlendMode.BLEND_TRANSLUCENT if translucent else unreal.BlendMode.BLEND_OPAQUE)
    mat.set_editor_property('shading_model',unreal.MaterialShadingModel.MSM_UNLIT)
    return mat


def scalar(mat,name,value,x=-650,y=220):
    node=EDIT.create_material_expression(mat,unreal.MaterialExpressionScalarParameter,x,y)
    node.set_editor_property('parameter_name',name)
    node.set_editor_property('default_value',value)
    return node


def save(mat):
    EDIT.recompile_material(mat)
    assert LIB.save_loaded_asset(mat), mat.get_path_name()
    return mat.get_path_name()


flame=material('M_Portrait_Flame',True)
uv=EDIT.create_material_expression(flame,unreal.MaterialExpressionTextureCoordinate,-650,-200)
clock=EDIT.create_material_expression(flame,unreal.MaterialExpressionTime,-650,0)
intensity=scalar(flame,'EmissionScale',1.)
custom=EDIT.create_material_expression(flame,unreal.MaterialExpressionCustom,-320,-100)
custom.set_editor_property('description','Four-second soft flame tongues: drifting edges, hot heart and translucent red boundary')
custom.set_editor_property('output_type',unreal.CustomMaterialOutputType.CMOT_FLOAT4)
inputs=[]
for name in ['UV','Clock','Intensity']:
    entry=unreal.CustomInput();entry.set_editor_property('input_name',name);inputs.append(entry)
custom.set_editor_property('inputs',inputs)
custom.set_editor_property('code',r'''
float y=saturate(1.0-UV.y);
float x=(UV.x-.5)*2.0;
float phase=Clock*1.57079632679;
float drift=(sin(y*9.0-phase*3.0)*.12+sin(y*19.0+phase*2.0)*.045)*y;
x+=drift;
float width=max(.015,(1.0-y)*.61);
float middle=1.0-abs(x)/width;
float left=(1.0-abs(x+.21+sin(phase*2.0+y*12.0)*.055)/max(.012,(.74-y)*.25));
float right=(1.0-abs(x-.24+sin(phase*3.0-y*14.0)*.045)/max(.012,(.87-y)*.23));
float flameShape=max(middle,max(left*(1.0-smoothstep(.69,.77,y)),right*(1.0-smoothstep(.8,.89,y))));
float edge=smoothstep(0.0,.33,flameShape);
float tip=1.0-smoothstep(.86,1.0,y);
float base=smoothstep(0.0,.055,y);
float heat=saturate(flameShape*.75+(1.0-y)*.25);
float3 ember=float3(1.55,.055,.003);
float3 core=float3(4.0,1.10,.035);
float3 color=lerp(ember,core,pow(heat,1.9))*Intensity;
float opacity=edge*tip*base*.88;
return float4(color,opacity);
''')
for source,name in [(uv,'UV'),(clock,'Clock'),(intensity,'Intensity')]:
    assert EDIT.connect_material_expressions(source,'',custom,name)
color=EDIT.create_material_expression(flame,unreal.MaterialExpressionComponentMask,-70,-140)
for key,value in {'r':True,'g':True,'b':True,'a':False}.items():color.set_editor_property(key,value)
alpha=EDIT.create_material_expression(flame,unreal.MaterialExpressionComponentMask,-70,70)
for key,value in {'r':False,'g':False,'b':False,'a':True}.items():alpha.set_editor_property(key,value)
assert EDIT.connect_material_expressions(custom,'',color,'')
assert EDIT.connect_material_expressions(custom,'',alpha,'')
assert EDIT.connect_material_property(color,'',unreal.MaterialProperty.MP_EMISSIVE_COLOR)
assert EDIT.connect_material_property(alpha,'',unreal.MaterialProperty.MP_OPACITY)
assets=[save(flame)]

# Existing camp lights are calibrated for the sunlit battlefield (400x radiance).
# Portraits have their own fixed lighting, so use these restrained equivalents.
for name,rgb in [('M_Portrait_Amber',(2.3,.55,.025)),('M_Portrait_Teal',(.08,1.3,1.45))]:
    mat=material(name)
    value=EDIT.create_material_expression(mat,unreal.MaterialExpressionConstant3Vector,-250,0)
    value.set_editor_property('constant',unreal.LinearColor(*rgb,1))
    assert EDIT.connect_material_property(value,'',unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    assets.append(save(mat))

ground=material('M_Portrait_Ground')
ground.set_editor_property('shading_model',unreal.MaterialShadingModel.MSM_DEFAULT_LIT)
ground_uv=EDIT.create_material_expression(ground,unreal.MaterialExpressionTextureCoordinate,-700,0)
ground_uv.set_editor_property('u_tiling',16.)
ground_uv.set_editor_property('v_tiling',16.)
for name,output,prop,y in [('T_dirt_diff_4k_Color','RGB',unreal.MaterialProperty.MP_BASE_COLOR,-200),
                           ('T_dirt_nor_dx_4k_Normal','RGB',unreal.MaterialProperty.MP_NORMAL,0),
                           ('T_dirt_arm_4k_Mask','G',unreal.MaterialProperty.MP_ROUGHNESS,200)]:
    tex=LIB.load_asset('/Game/Art/Camps/Textures/'+name)
    assert tex,name
    sample=EDIT.create_material_expression(ground,unreal.MaterialExpressionTextureSample,-400,y)
    sample.set_editor_property('texture',tex)
    if 'Normal' in name:sample.set_editor_property('sampler_type',unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL)
    elif 'Mask' in name:sample.set_editor_property('sampler_type',unreal.MaterialSamplerType.SAMPLERTYPE_MASKS)
    assert EDIT.connect_material_expressions(ground_uv,'',sample,'UVs')
    assert EDIT.connect_material_property(sample,output,prop)
assets.append(save(ground))

weapon_path=DEST+'/M_Portrait_Weapon'
weapon=LIB.load_asset(weapon_path) if LIB.does_asset_exist(weapon_path) else LIB.duplicate_asset('/Game/Art/Camps/Materials/M_Camp_DarkSteel',weapon_path)
assert weapon,weapon_path
EDIT.set_base_material_usage(weapon,unreal.MaterialUsage.MATUSAGE_NANITE,True)
assert EDIT.has_material_usage(weapon,unreal.MaterialUsage.MATUSAGE_NANITE)
assets.append(save(weapon))

report={'ok':True,'assets':assets,'animation_loop_seconds':4,'raster_assets':False,'map_modified':False}
path=ROOT/'game/tests/reports/portrait-material-authoring.json'
path.parent.mkdir(parents=True,exist_ok=True)
path.write_text(json.dumps(report,indent=2)+'\n')
unreal.log('OLDWEST_PORTRAIT_MATERIALS '+json.dumps(report))
