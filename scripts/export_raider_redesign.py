"""Bake the approved Blender Raider into the game's three moving static meshes.
Run Blender -b -t 8 --python scripts/export_raider_redesign.py.
Preserves the authoring blend; exports to redesign/game-export with PBR atlases.
"""
import bpy, math, json, hashlib, sys, os
from pathlib import Path
from mathutils import Matrix,Vector
ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'art/vehicles/raiders/redesign/Raider.blend'
OUT=SOURCE.parent/'game-export';OUT.mkdir(exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
s=bpy.context.scene;s.render.engine='CYCLES';s.cycles.device='CPU';s.cycles.samples=8
s.render.bake.margin=12;s.render.bake.use_clear=True
s.render.bake.normal_space='TANGENT'
s.render.image_settings.file_format='PNG'
groups={key:[] for key in ('Body','Driver','Turret','Gatling Gunner','Wheel','Glass')}
original=list(s.objects);deps=bpy.context.evaluated_depsgraph_get()
for ob in original:
    if ob.type not in {'MESH','CURVE','FONT'} or ob.hide_render:continue
    if any(c.name.startswith('09 STUDIO') for c in ob.users_collection):continue
    if ob.name=='Ground':continue
    if ob.name.startswith('Punk 1'):key='Gatling Gunner'
    elif ob.name.startswith('Punk 2'):key='Driver'
    elif any(c.name.startswith('07 TURRET') for c in ob.users_collection):key='Turret'
    elif any(c.name.startswith('04 WHEELS') for c in ob.users_collection) or ob.name.startswith('Tire dried clay splash'):
        centre=sum((ob.matrix_world@Vector(p) for p in ob.bound_box),Vector())/8
        # One full wheel, at the +X/front axle. Runtime instantiates it four times.
        if centre.x<.5 or centre.y>0:continue
        key='Wheel'
    elif ob.name.startswith(('Laminated windshield','Armored side window')):key='Glass'
    else:key='Body'
    evaluated=ob.evaluated_get(deps)
    mesh=bpy.data.meshes.new_from_object(evaluated,preserve_all_data_layers=True,depsgraph=deps)
    if not mesh or not len(mesh.polygons):continue
    mesh.transform(ob.matrix_world)
    if ob.matrix_world.determinant()<0:mesh.flip_normals()
    copy=bpy.data.objects.new('Export '+ob.name,mesh);s.collection.objects.link(copy);groups[key].append(copy)
for ob in original:bpy.data.objects.remove(ob,do_unlink=True)
meshes={};report={'source':str(SOURCE.relative_to(ROOT)),'source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),'bakes':{},'assets':[]}
# Material copies prevent modifying the source and allow temporary bake outputs.
for key,objects in groups.items():
    assert objects,key
    bpy.ops.object.select_all(action='DESELECT')
    for ob in objects:ob.select_set(True)
    bpy.context.view_layer.objects.active=objects[0];bpy.ops.object.join()
    ob=bpy.context.object;ob.name='Bake_'+key;meshes[key]=ob
    # Discard empty material slots and preserve existing photographic UV0.
    mats=[]
    for slot in ob.material_slots:
        if slot.material:
            slot.material=slot.material.copy();slot.material.name='Bake_'+key+'_'+slot.material.name
            mats.append(slot.material)
    ob.data.calc_loop_triangles()
    print('BAKE_GROUP',key,len(ob.data.vertices),len(ob.data.loop_triangles),len(mats),flush=True)
    if key=='Glass':continue
    # A separate UV channel allows the original skin/outfit maps to be sampled
    # while the final atlas is baked into new nonoverlapping islands.
    if ob.data.uv_layers.active:ob.data.uv_layers.active.active_render=True
    uv=ob.data.uv_layers.new(name='GameAtlas');ob.data.uv_layers.active=uv
    bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(66),island_margin=.003,area_weight=.1,scale_to_bounds=True)
    bpy.ops.object.mode_set(mode='OBJECT')
    size=4096 if key=='Body' else 2048
    outputs={}
    for channel in ('BaseColor','ORM','Normal'):
        image=bpy.data.images.new('T_Raider_'+key+'_'+channel,width=size,height=size,alpha=False)
        image.colorspace_settings.name='sRGB' if channel=='BaseColor' else 'Non-Color'
        resets=[]
        for mat in mats:
            nodes=mat.node_tree.nodes;links=mat.node_tree.links
            bsdf=next((n for n in nodes if n.type=='BSDF_PRINCIPLED'),None)
            output=next((n for n in nodes if n.type=='OUTPUT_MATERIAL' and n.is_active_output),None)
            if output is None:continue
            target=nodes.new('ShaderNodeTexImage');target.image=image;nodes.active=target
            for n in nodes:n.select=False
            target.select=True
            if channel!='Normal':
                old=output.inputs['Surface'].links[0].from_socket if output.inputs['Surface'].links else None
                emission=nodes.new('ShaderNodeEmission');emission.inputs['Strength'].default_value=1
                temp=[emission]
                def feed(socket,dest,default):
                    if socket and socket.links:links.new(socket.links[0].from_socket,dest)
                    else:dest.default_value=socket.default_value if socket else default
                if channel=='BaseColor':
                    feed(bsdf.inputs['Base Color'] if bsdf else None,emission.inputs['Color'],(.1,.1,.1,1))
                else:
                    combine=nodes.new('ShaderNodeCombineColor');combine.mode='RGB';combine.inputs['Red'].default_value=1
                    feed(bsdf.inputs['Roughness'] if bsdf else None,combine.inputs['Green'],.65)
                    feed(bsdf.inputs['Metallic'] if bsdf else None,combine.inputs['Blue'],0)
                    links.new(combine.outputs[0],emission.inputs['Color']);temp.append(combine)
                links.new(emission.outputs[0],output.inputs['Surface']);resets.append((mat,output,old,temp,target))
            else:resets.append((mat,output,None,[],target))
        bpy.ops.object.select_all(action='DESELECT');ob.select_set(True);bpy.context.view_layer.objects.active=ob
        print('BAKING',key,channel,size,flush=True)
        bpy.ops.object.bake(type='NORMAL' if channel=='Normal' else 'EMIT',uv_layer='GameAtlas')
        path=OUT/(image.name+'.png');image.filepath_raw=str(path);image.file_format='PNG';image.save()
        outputs[channel]={'file':path.name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
        for mat,output,old,temp,target in resets:
            if old:mat.node_tree.links.new(old,output.inputs['Surface'])
            for n in temp+[target]:mat.node_tree.nodes.remove(n)
        bpy.data.images.remove(image)
    # Bake complete. Keep only atlas UV as UV0 and collapse to one material.
    for old in list(ob.data.uv_layers):
        if old.name!='GameAtlas':ob.data.uv_layers.remove(old)
    ob.data.uv_layers.active=ob.data.uv_layers['GameAtlas'];ob.data.uv_layers.active.active_render=True
    mat=bpy.data.materials.new('M_Raider_'+key);mat.use_nodes=True
    nodes=mat.node_tree.nodes;links=mat.node_tree.links;b=nodes.get('Principled BSDF')
    for channel in outputs:
        im=bpy.data.images.load(str(OUT/outputs[channel]['file']));im.colorspace_settings.name='sRGB' if channel=='BaseColor' else 'Non-Color'
        tex=nodes.new('ShaderNodeTexImage');tex.image=im
        if channel=='BaseColor':links.new(tex.outputs['Color'],b.inputs['Base Color'])
        elif channel=='ORM':
            split=nodes.new('ShaderNodeSeparateColor');links.new(tex.outputs[0],split.inputs[0]);links.new(split.outputs['Green'],b.inputs['Roughness']);links.new(split.outputs['Blue'],b.inputs['Metallic'])
        else:
            normal=nodes.new('ShaderNodeNormalMap');links.new(tex.outputs['Color'],normal.inputs['Color']);links.new(normal.outputs[0],b.inputs['Normal'])
    ob.data.materials.clear();ob.data.materials.append(mat)
    for face in ob.data.polygons:face.material_index=0
    report['bakes'][key]={'size':size,'textures':outputs}
# Glass uses a dedicated physically transparent material in the game.
glass=meshes['Glass'];glass.data.materials.clear();glass.data.materials.append(bpy.data.materials.new('M_Raider_Glass'))
for f in glass.data.polygons:f.material_index=0
# Runtime pivots and handedness are identical to the established vehicle.
wheel=meshes['Wheel'];wheel.data.transform(Matrix.Rotation(-math.pi/2,4,'Y')@Matrix.Translation(Vector((-1.02,1.24,-.44))))
for name,keys,pivot in [('SM_Raiders_Chassis',['Body','Driver','Glass'],(0,0,0)),('SM_Raiders_Turret',['Turret','Gatling Gunner'],(0,.1,1.94)),('SM_Raiders_Wheel',['Wheel'],(0,0,0))]:
    bpy.ops.object.select_all(action='DESELECT')
    for key in keys:meshes[key].select_set(True)
    ob=meshes[keys[0]];bpy.context.view_layer.objects.active=ob;bpy.ops.object.join();ob.name=name
    ob.data.transform(Matrix.Translation(-Vector(pivot)))
    # Explicit triangles ensure the baked tangent-space map uses the same basis.
    mod=ob.modifiers.new('Stable triangle basis','TRIANGULATE');mod.keep_custom_normals=True;bpy.ops.object.modifier_apply(modifier=mod.name)
    ob.data.calc_loop_triangles()
    # Glass has no atlas UV, but joining supplies zero UVs for those surfaces;
    # it does not sample a normal texture and does not require custom tangents.
    path=OUT/(name+'.fbx')
    bpy.ops.export_scene.fbx(filepath=str(path),use_selection=True,object_types={'MESH'},apply_unit_scale=True,apply_scale_options='FBX_SCALE_UNITS',mesh_smooth_type='FACE',bake_anim=False,add_leaf_bones=False,use_tspace=True,axis_forward='-Y',axis_up='Z')
    lo=[min(v.co[i] for v in ob.data.vertices) for i in range(3)];hi=[max(v.co[i] for v in ob.data.vertices) for i in range(3)]
    report['assets'].append({'name':name,'file':path.name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'triangles':len(ob.data.loop_triangles),'bounds_min_m':lo,'bounds_max_m':hi,'materials':[slot.material.name for slot in ob.material_slots]})
    ob.hide_set(True);ob.hide_render=True
(OUT/'export.json').write_text(json.dumps(report,indent=2)+'\n')
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'Raider-Game.blend'))
print('RAIDER_GAME_EXPORT_COMPLETE',report['assets'],flush=True)
sys.stdout.flush();sys.stderr.flush();os._exit(0)
