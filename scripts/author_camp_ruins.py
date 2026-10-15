"""Author camp ruin ash and smoke materials; preserve healthy/damaged materials."""
import unreal

E = unreal.MaterialEditingLibrary
L = unreal.EditorAssetLibrary
T = unreal.AssetToolsHelpers.get_asset_tools()
DEST = '/Game/Art/Camps/Ruins'

def node(m, kind, **props):
    n = E.create_material_expression(m, getattr(unreal, kind))
    for k, v in props.items():
        n.set_editor_property(k, v)
    return n

def wire(a, b, pin=''):
    assert E.connect_material_expressions(a, '', b, pin)

def prop(n, p):
    assert E.connect_material_property(n, '', getattr(unreal.MaterialProperty, 'MP_' + p))

def duplicate(source, name):
    path = DEST + '/' + name
    if L.does_asset_exist(path):
        L.delete_asset(path)
    return L.duplicate_asset(source, path)

m = L.load_asset(DEST + '/M_Ruin_Ash') if L.does_asset_exist(DEST + '/M_Ruin_Ash') else T.create_asset('M_Ruin_Ash', DEST, unreal.Material, unreal.MaterialFactoryNew())
E.delete_all_material_expressions(m)
m.set_editor_property('blend_mode', unreal.BlendMode.BLEND_MASKED)
m.set_editor_property('two_sided', True)
m.set_editor_property('opacity_mask_clip_value', .35)
uv = node(m, 'MaterialExpressionTextureCoordinate')
code = r'''
struct AshNoise {
 float hash(float2 p) { return frac(sin(dot(p,float2(127.1,311.7)))*43758.5453); }
 float noise(float2 p) {
  float2 i=floor(p),f=frac(p); f=f*f*(3.-2.*f);
  return lerp(lerp(hash(i),hash(i+float2(1,0)),f.x),lerp(hash(i+float2(0,1)),hash(i+1),f.x),f.y);
 }
 float fbm(float2 p) { return noise(p)*.55+noise(p*2.03)*.28+noise(p*4.11)*.17; }
};
AshNoise n;
float dust=n.fbm(UV*float2(95.,19.));
float grain=n.fbm(UV*float2(420.,95.));
// The mesh supplies the irregular streak silhouette; no radial mask.
float fringe=smoothstep(0.,.16,UV.y)*(1.-smoothstep(.82,1.,UV.y));
fringe*=smoothstep(0.,.06,UV.x)*(1.-smoothstep(.94,1.,UV.x));
float mask=fringe-.55*n.noise(UV*float2(700.,120.));
float ash=smoothstep(.28,.78,dust)*(.45+.55*grain);
float3 soot=float3(.012,.011,.010);
float3 powder=float3(.075,.070,.062);
float3 color=lerp(soot,powder,ash);
color*=.66+.65*grain;
return float4(color,mask);
'''
n = node(m,'MaterialExpressionCustom',code=code,output_type=unreal.CustomMaterialOutputType.CMOT_FLOAT4)
i=unreal.CustomInput();i.set_editor_property('input_name','UV');n.set_editor_property('inputs',[i]);wire(uv,n,'UV')
rgb=node(m,'MaterialExpressionComponentMask',r=True,g=True,b=True,a=False);wire(n,rgb);prop(rgb,'BASE_COLOR')
a=node(m,'MaterialExpressionComponentMask',r=False,g=False,b=False,a=True);wire(n,a);prop(a,'OPACITY_MASK')
rough=node(m,'MaterialExpressionConstant',r=.98);prop(rough,'ROUGHNESS')
E.recompile_material(m);L.save_loaded_asset(m)

# Darker burn-through for ruins while retaining each substrate's original normals.
for path in L.list_assets('/Game/Art/Camps/Conditions', recursive=False):
    if '/M_Soot_' not in path:
        continue
    source=L.load_asset(path)
    target=duplicate(path,source.get_name().replace('M_Soot_','M_Ruin_'))
    original=E.get_material_property_input_node(target,unreal.MaterialProperty.MP_BASE_COLOR)
    tint=node(target,'MaterialExpressionConstant3Vector',constant=unreal.LinearColor(.23,.235,.24,1))
    mult=node(target,'MaterialExpressionMultiply');wire(original,mult,'A');wire(tint,mult,'B');prop(mult,'BASE_COLOR')
    prop(node(target,'MaterialExpressionConstant',r=.96),'ROUGHNESS')
    prop(node(target,'MaterialExpressionConstant',r=0),'METALLIC')
    E.recompile_material(target);L.save_loaded_asset(target)

m=duplicate('/Game/Art/Effects/Materials/M_Smoke_Flipbook','M_Ruin_Smoke')
# The surface Custom node feeds the emissive component mask.
rgb=E.get_material_property_input_node(m,unreal.MaterialProperty.MP_EMISSIVE_COLOR)
# Find custom expressions through the material subobject list.
for expression in E.get_inputs_for_material_expression(m, rgb):
    if isinstance(expression,unreal.MaterialExpressionCustom):
        code=expression.get_editor_property('code')
        if 'float3 color = lerp' in code:
            code=code.replace('float3(.026,.024,.022),float3(.09,.083,.073)', 'float3(.075,.072,.068),float3(.24,.23,.215)')
            expression.set_editor_property('code',code)
# Travel and growth are now driven by individual particles in C++, not
# a small whole-sheet shader displacement that appears stationary in play.
wpo=E.get_material_property_input_node(m,unreal.MaterialProperty.MP_WORLD_POSITION_OFFSET)
assert isinstance(wpo,unreal.MaterialExpressionCustom)
code=wpo.get_editor_property('code')
code=code.replace('desired += float3(0,0,height*.45*age);','')
wpo.set_editor_property('code',code)
E.recompile_material(m);L.save_loaded_asset(m)
unreal.log('OLDWEST_RUIN_MATERIALS_AUTHORED')
