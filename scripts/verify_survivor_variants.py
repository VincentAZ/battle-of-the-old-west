"""Read-only native reference-skeleton/material/bounds audit; run with NullRHI."""
import hashlib
import json
import math
import os
import sys
from pathlib import Path

import unreal

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from identity_material_checks import verify_hair_root_fade
OUT=Path(os.environ.get('OLDWEST_VARIANT_SOURCE',str(ROOT/'art/characters/survivor_variants'))).resolve()
LIB=unreal.EditorAssetLibrary
BASE='/Game/Art/Survivors/SurvivorA'
originals={str(p):hashlib.sha256(p.read_bytes()).hexdigest()
           for p in (ROOT/'game/OldWest/Content/Art/Survivors/SurvivorA').rglob('*.uasset')}
imported=json.loads((OUT/'unreal-import.json').read_text())
expected_originals=dict(imported['protected_sha256'])
# A separately reviewed rig revision need not rewrite an old import record.
# The caller must name its exact expected bytes; every other protected asset
# remains pinned to the import, and all assets are checked unchanged afterward.
expected_physics=os.environ.get('OLDWEST_EXPECTED_PHYSICS_SHA256')
if expected_physics:
    assert len(expected_physics)==64 and all(c in '0123456789abcdef' for c in expected_physics)
    physics_path=str(ROOT/'game/OldWest/Content/Art/Survivors/SurvivorA/PA_Survivor_Anatomical.uasset')
    assert physics_path in expected_originals
    expected_originals[physics_path]=expected_physics
assert originals==expected_originals,'Original assets differ from the import and explicitly expected physics revision'
report={'ok':False,'variants':[],'source_originals_sha256':originals,
        'explicitly_expected_physics_sha256':expected_physics,
        'import_protected_sha256':imported['protected_sha256']}
components=[]


def vector(v):return [float(v.x),float(v.y),float(v.z)]


def inspect(path):
    mesh=LIB.load_asset(path);assert isinstance(mesh,unreal.SkeletalMesh),path
    component=unreal.SkeletalMeshComponent()
    components.append(component);component.set_skinned_asset_and_update(mesh)
    bones=[]
    for index in range(component.get_num_bones()):
        name=component.get_bone_name(index);pose=component.get_ref_pose_transform(index)
        q=pose.rotation
        bones.append({'name':str(name),'parent':str(component.get_parent_bone(name)),
                      'translation':vector(pose.translation),'scale':vector(pose.scale3d),
                      'rotation':[float(q.x),float(q.y),float(q.z),float(q.w)]})
    bounds=mesh.get_imported_bounds()
    origin,extent=vector(bounds.origin),vector(bounds.box_extent)
    slots=mesh.get_editor_property('materials')
    return {'mesh':mesh.get_path_name(),'bone_count':len(bones),'bones':bones,
            'skeleton':mesh.get_editor_property('skeleton').get_path_name(),
            'physics_asset':mesh.get_editor_property('physics_asset').get_path_name(),
            'bounds':{'origin':origin,'extent':extent,'minimum':[a-b for a,b in zip(origin,extent)],
                      'maximum':[a+b for a,b in zip(origin,extent)]},
            'morph_targets':sorted(m.get_name() for m in mesh.get_editor_property('morph_targets')),
            'materials':[{'slot':str(s.get_editor_property('material_slot_name')),
                          'material':s.get_editor_property('material_interface').get_path_name()
                          if s.get_editor_property('material_interface') else None} for s in slots]}


try:
    base=inspect(BASE+'/SKM_Survivor_A_Cm');report['reference']=base
    assert base['bone_count']==54
    assert imported['variants'], 'No imported variants to verify'
    for record in imported['variants']:
        card=record['card_id']
        result=inspect(record['mesh'])
        result['card_id']=card;report['variants'].append(result)
        assert result['bone_count']==54 and result['skeleton']==base['skeleton']
        # The preserved source mesh still has its initial auto-generated default
        # physics asset. Unit.Configure overrides that with this reviewed rig.
        assert result['physics_asset']==BASE+'/PA_Survivor_Anatomical.PA_Survivor_Anatomical'
        maximum={'translation_cm':0.,'scale':0.,'angle_degrees':0.}
        for actual,expected in zip(result['bones'],base['bones']):
            assert (actual['name'],actual['parent'])==(expected['name'],expected['parent'])
            translation=math.dist(actual['translation'],expected['translation'])
            scale=max(abs(a-b) for a,b in zip(actual['scale'],expected['scale']))
            a,b=actual['rotation'],expected['rotation']
            dot=abs(sum(x*y for x,y in zip(a,b)))/math.sqrt(sum(x*x for x in a)*sum(x*x for x in b))
            angle=math.degrees(2*math.acos(min(1.,max(0.,dot))))
            assert translation<.001 and scale<.000001 and angle<.001,(card,actual['name'],translation,scale,angle)
            for key,value in [('translation_cm',translation),('scale',scale),('angle_degrees',angle)]:maximum[key]=max(maximum[key],value)
        result['maximum_ref_pose_delta']=maximum
        assert all(math.isfinite(v) and v>0 for v in result['bounds']['extent'])
        assert .92<result['bounds']['extent'][2]/base['bounds']['extent'][2]<1.20
        spec=json.loads((OUT/card/'manifest.json').read_text())
        if spec.get('facial_identity'):
            expected_shapes={key for component in spec['facial_identity']['components']
                             for key in component['shape_keys'] if key!='Basis'}
            assert len(expected_shapes)==26, (card,'Unexpected source expression inventory')
            assert len(result['morph_targets'])==len(expected_shapes), (card,result['morph_targets'])
            for shape in expected_shapes:
                assert sum(name.endswith(shape) for name in result['morph_targets'])==1, (card,shape)
            result['source_expressions_preserved']=True
        assert {m['slot'] for m in result['materials']}==set(spec['material_names'])
        assert all(m['material'] for m in result['materials'])
        expected_materials={m['slot']:m['material'] for row in imported['variants'] if row['card_id']==card for m in row['materials']}
        assert {m['slot']:m['material'] for m in result['materials']}==expected_materials,(card,'persisted material mapping differs from import')
        result['hair_materials']=[]
        result['detail_materials']=[]
        for name,details in spec.get('materials',{}).items():
            if details.get('kind')=='solid_detail':
                material=LIB.load_asset(expected_materials[name])
                assert material.get_editor_property('blend_mode')==unreal.BlendMode.BLEND_OPAQUE
                assert material.get_editor_property('two_sided')==details['two_sided']
                for usage in [unreal.MaterialUsage.MATUSAGE_SKELETAL_MESH,unreal.MaterialUsage.MATUSAGE_MORPH_TARGETS]:
                    assert unreal.MaterialEditingLibrary.has_material_usage(material,usage)
                result['detail_materials'].append({'material':material.get_path_name(),'opaque':True,
                                                  'morph_usage':True,'skeletal_usage':True})
            if details.get('kind')!='masked_hair':continue
            material=LIB.load_asset(expected_materials[name])
            assert material.get_editor_property('blend_mode')==unreal.BlendMode.BLEND_MASKED
            assert material.get_editor_property('two_sided') is True
            assert abs(material.get_editor_property('opacity_mask_clip_value')-details['opacity_clip'])<1e-6
            assert unreal.MaterialEditingLibrary.has_material_usage(material,unreal.MaterialUsage.MATUSAGE_SKELETAL_MESH)
            result['hair_materials'].append({'material':material.get_path_name(),'masked':True,'two_sided':True,
                                            'skeletal_usage':True,
                                            'root_fade':verify_hair_root_fade(material,details['root_fade_start'])})
    assert originals=={p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in originals}
    report['original_assets_unchanged']=True
    report['ok']=True
except Exception as error:
    report['error']=str(error)
    raise
finally:
    (OUT/'native-reference-audit.json').write_text(json.dumps(report,indent=2)+'\n')
    unreal.log('VARIANT_REFERENCE_AUDIT '+json.dumps({'ok':report['ok'],'variants':len(report['variants']),'error':report.get('error')}))
