"""Import regional assets into new paths without saving any existing level."""
import hashlib
import json
from pathlib import Path
import unreal

ROOT=Path(__file__).resolve().parents[1]
TREES=ROOT/'art/western/regions/review-v002'
TERRAIN=ROOT/'art/western/regions/terrain-v001'
BASE='/Game/Art/Western/Regions'
LIB=unreal.EditorAssetLibrary;EDIT=unreal.MaterialEditingLibrary;TOOLS=unreal.AssetToolsHelpers.get_asset_tools()
EVIDENCE=ROOT/'research/western-presentation/regional-battlefields.json'


def material(name,colour,two_sided=False,roughness=.85):
    path=BASE+'/Materials/'+name
    mat=LIB.load_asset(path) if LIB.does_asset_exist(path) else TOOLS.create_asset(name,BASE+'/Materials',unreal.Material,unreal.MaterialFactoryNew())
    EDIT.delete_all_material_expressions(mat);mat.set_editor_property('two_sided',two_sided)
    c=EDIT.create_material_expression(mat,unreal.MaterialExpressionConstant3Vector)
    c.set_editor_property('constant',unreal.LinearColor(*colour,1));EDIT.connect_material_property(c,'',unreal.MaterialProperty.MP_BASE_COLOR)
    r=EDIT.create_material_expression(mat,unreal.MaterialExpressionConstant);r.set_editor_property('r',roughness)
    EDIT.connect_material_property(r,'',unreal.MaterialProperty.MP_ROUGHNESS)
    return mat


def custom(mat,names,code):
    node=EDIT.create_material_expression(mat,unreal.MaterialExpressionCustom)
    node.set_editor_property('output_type',unreal.CustomMaterialOutputType.CMOT_FLOAT3)
    inputs=[]
    for name in names:
        i=unreal.CustomInput();i.set_editor_property('input_name',name);inputs.append(i)
    node.set_editor_property('inputs',inputs);node.set_editor_property('code',code)
    return node


def finish(mat):
    EDIT.set_base_material_usage(mat,unreal.MaterialUsage.MATUSAGE_INSTANCED_STATIC_MESHES,True)
    EDIT.set_base_material_usage(mat,unreal.MaterialUsage.MATUSAGE_NANITE,True)
    EDIT.recompile_material(mat);assert LIB.save_loaded_asset(mat,only_if_is_dirty=False)
    return mat


def ground(name,kind):
    mat=material(name,(.1,.2,.03));world=EDIT.create_material_expression(mat,unreal.MaterialExpressionWorldPosition)
    normal=EDIT.create_material_expression(mat,unreal.MaterialExpressionVertexNormalWS)
    texture=LIB.load_asset('/Game/Art/WaterDepotV2/Textures/T_dirt_aerial_03_diff_4k');assert texture
    scan=EDIT.create_material_expression(mat,unreal.MaterialExpressionTextureObject);scan.set_editor_property('texture',texture)
    common='''
struct RegionalNoise {
 float H(float2 p) { uint2 q=asuint(int2(p));
  uint h=q.x*1597334677u ^ q.y*3812015801u;h=(h^(h>>16))*2246822519u;
  h^=h>>13;return float(h&16777215u)/16777215.0; }
 float V(float2 p) { float2 i=floor(p),f=frac(p);f=f*f*(3-2*f);
  return lerp(lerp(H(i),H(i+float2(1,0)),f.x),lerp(H(i+float2(0,1)),H(i+1),f.x),f.y); }
};
RegionalNoise n;
float patch=.6*n.V(World.xy/1900)+.3*n.V(World.xy/710)+.1*n.V(World.xy/160);
float3 grain=Texture2DSample(Scan,ScanSampler,World.xy/1800.0).rgb;
float broad=Texture2DSample(Scan,ScanSampler,World.xy/14700.0+float2(.23,.67)).g;
float detail=Texture2DSample(Scan,ScanSampler,World.xy/270.0).r;
float variation=saturate(broad*1.7);
float3 earth=lerp(float3(.075,.042,.018),float3(.24,.13,.055),variation)*(0.70+detail);
'''
    code={
      'winter':'''float exposed=saturate((1-Normal.z)*3.7+smoothstep(.59,.72,patch));
float3 snow=lerp(float3(.49,.61,.76),float3(.83,.88,.94),saturate(detail*1.9));
return lerp(snow,earth,exposed);''',
      'pine':'''float bare=saturate((1-Normal.z)*4+smoothstep(.42,.63,patch)*.85);
float3 grass=lerp(float3(.022,.09,.01),float3(.12,.23,.03),patch)*(0.6+detail*1.5);
float rock=smoothstep(.18,.40,1-Normal.z);
return lerp(lerp(grass,earth,bare),float3(.32,.30,.26)*(0.6+detail),rock);''',
      'river':'''float y=-World.y/100;float channel=127+18*sin(y/130)+8*sin(y/57);
float d=abs(World.x/100-channel);float shore=1-smoothstep(23,44,d);
float3 grass=lerp(float3(.022,.10,.013),float3(.105,.245,.026),patch)*(0.6+detail*1.5);
grass=lerp(grass,earth,smoothstep(.61,.74,patch)*.5);
return lerp(grass,float3(.38,.27,.13)*(0.7+detail),shore);'''
    }[kind]
    out=custom(mat,['World','Normal','Scan'],common+code)
    for src,pin in [(world,'World'),(normal,'Normal'),(scan,'Scan')]:EDIT.connect_material_expressions(src,'',out,pin)
    EDIT.connect_material_property(out,'',unreal.MaterialProperty.MP_BASE_COLOR)
    detail_normal=EDIT.create_material_expression(mat,unreal.MaterialExpressionTextureSample)
    detail_normal.set_editor_property('texture',LIB.load_asset('/Game/Art/WaterDepotV2/Textures/T_dirt_nor_dx_4k'))
    detail_normal.set_editor_property('sampler_type',unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL)
    soften=custom(mat,['Grain'], 'return normalize(lerp(float3(0,0,1),Grain,.32));')
    EDIT.connect_material_expressions(detail_normal,'RGB',soften,'Grain')
    EDIT.connect_material_property(soften,'',unreal.MaterialProperty.MP_NORMAL)
    return finish(mat)


def water():
    mat=material('M_Region_RiverWater',(.07,.13,.085),roughness=.16)
    world=EDIT.create_material_expression(mat,unreal.MaterialExpressionWorldPosition)
    time=EDIT.create_material_expression(mat,unreal.MaterialExpressionTime)
    ripple=custom(mat,['World','Time'],'''float x=World.x,y=World.y;
return normalize(float3(.08*sin(x/43+y/140+Time*1.1),.06*cos(y/67-x/310+Time*.7),1));''')
    EDIT.connect_material_expressions(world,'',ripple,'World');EDIT.connect_material_expressions(time,'',ripple,'Time')
    EDIT.connect_material_property(ripple,'',unreal.MaterialProperty.MP_NORMAL)
    return finish(mat)


def import_mesh(directory,record,materials):
    file=directory/record['fbx'];assert hashlib.sha256(file.read_bytes()).hexdigest()==record['sha256']
    opts=unreal.FbxImportUI()
    for k,v in dict(import_mesh=True,import_as_skeletal=False,import_materials=False,import_textures=False,
                    import_animations=False,automated_import_should_detect_type=False,
                    mesh_type_to_import=unreal.FBXImportType.FBXIT_STATIC_MESH).items():opts.set_editor_property(k,v)
    for k,v in dict(combine_meshes=True,auto_generate_collision=False,generate_lightmap_u_vs=False,
                    convert_scene=True,convert_scene_unit=True,force_front_x_axis=False,build_nanite=False,
                    normal_import_method=unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS).items():opts.static_mesh_import_data.set_editor_property(k,v)
    task=unreal.AssetImportTask()
    for k,v in dict(filename=str(file),destination_path=BASE+'/Meshes',destination_name=record['name'],
                    automated=True,replace_existing=True,save=False,options=opts,factory=unreal.FbxFactory()).items():task.set_editor_property(k,v)
    TOOLS.import_asset_tasks([task]);mesh=next(x for x in task.get_objects() if isinstance(x,unreal.StaticMesh))
    if record.get('materials'):
        for index,slot in enumerate(mesh.get_editor_property('static_materials')):
            name=str(slot.get_editor_property('imported_material_slot_name'))
            assert name in materials,(record['name'],name)
            mesh.set_material(index,materials[name])
    else:mesh.set_material(0,materials['M_Region_RiverWater' if 'Water' in record['name'] else 'M_Region_RiverGround'])
    assert LIB.save_loaded_asset(mesh,only_if_is_dirty=False)
    return dict(asset=mesh.get_path_name(),triangles=mesh.get_num_triangles(0))


def main():
    manifests=[json.loads((p/'manifest.json').read_text()) for p in (TREES,TERRAIN)]
    evidence_hash=hashlib.sha256(EVIDENCE.read_bytes()).hexdigest()
    assert all(m['evidence_sha256']==evidence_hash for m in manifests)
    protected={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'game/OldWest/Content/Maps').glob('*.umap')}
    world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    unreal.SystemLibrary.execute_console_command(world,'Interchange.FeatureFlags.Import.FBX 0')
    materials={name:finish(material(name,rgb,two_sided=True)) for name,rgb in manifests[0]['material_linear_rgb'].items()}
    for name,kind in [('M_Region_WinterGround','winter'),('M_Region_PineGround','pine'),('M_Region_RiverGround','river')]:materials[name]=ground(name,kind)
    materials['M_Region_RiverWater']=water();imports=[]
    if '-RegionMaterialsOnly' in unreal.SystemLibrary.get_command_line():
        assert all(hashlib.sha256(p.read_bytes()).hexdigest()==h for p,h in protected.items())
        unreal.log('REGIONAL_MATERIALS_UPDATED');return
    for directory,manifest in zip((TREES,TERRAIN),manifests):
        for record in manifest['assets']:imports.append(import_mesh(directory,record,materials))
    assert all(hashlib.sha256(p.read_bytes()).hexdigest()==h for p,h in protected.items())
    (TREES/'unreal-import.json').write_text(json.dumps(dict(ok=True,evidence_sha256=evidence_hash,assets=imports,
        levels_unchanged=True,visual_review='pending'),indent=2)+'\n')
    unreal.log('REGIONAL_SCENERY_IMPORTED '+str(len(imports)))


if __name__=='__main__':main()
