"""Stage/generate/verify survivor LODs in a coordinated Unreal commandlet.

Default: read-only plan. -ApplySurvivorLODs: generate and save only after exact
hero-LOD fidelity and skin/morph structure checks. -VerifySurvivorLODs: fresh
reload checks. -ReviseSurvivorLODs backs up an existing generated mesh before
rebuilding its lower detail levels against the original hero fingerprint.
Applying requires the staged DescribeSurvivorLods C++ readout
to have been integrated and built first. Missing readout aborts before edits.
Use a unique temporary -GameUserSettingsINI for every commandlet.
"""
import hashlib
import json
import shutil
import shlex
import time
from pathlib import Path
import unreal

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'art/characters/oldwest_survivor/lods'
OUT.mkdir(exist_ok=True)
BASE='/Game/Art/Survivors/SurvivorA'
MESH_PATH=BASE+'/SKM_Survivor_A_Cm'
SETTINGS_PATH=BASE+'/LOD_Survivor_CinematicTactical'
CONTENT=ROOT/'game/OldWest/Content/Art/Survivors/SurvivorA'
SOURCE=CONTENT/'SKM_Survivor_A_Cm.uasset'
PLAN=[{'lod':0,'triangle_fraction':1.0,'screen_size':1.0,'hysteresis':0.0},
      {'lod':1,'triangle_fraction':.45,'screen_size':.50,'hysteresis':.02},
      {'lod':2,'triangle_fraction':.25,'screen_size':.22,'hysteresis':.02},
      {'lod':3,'triangle_fraction':.20,'screen_size':.10,'hysteresis':.02}]
command=unreal.SystemLibrary.get_command_line()
write_gate=next((Path(arg.split('=',1)[1]) for arg in shlex.split(command)
                 if arg.startswith('-SurvivorLODWriteGate=')),None)
first_apply='-ApplySurvivorLODs' in command
revise='-ReviseSurvivorLODs' in command
apply=first_apply or revise
verify='-VerifySurvivorLODs' in command
assert sum((first_apply,revise,verify))<=1
mesh=unreal.load_asset(MESH_PATH)
assert mesh
edit=(unreal.get_editor_subsystem(unreal.SkeletalMeshEditorSubsystem)
      or unreal.get_default_object(unreal.SkeletalMeshEditorSubsystem))
assert edit
proposal={'mesh':MESH_PATH,'levels':PLAN,'reduction_source_lod':0,
          'remap_morph_targets':True,'remove_bones':False,'preserve_normals':True,
          'screen_size_metric':'Unreal projected bounding-sphere diameter',
          'hero_lod0_geometry_weights_and_morph_hash_gate':True,
          'preserve_eye_and_hair_sections':True,
          'revision_reason':'Visible scalp holes in the previous LOD3 hair reduction',
          'deformation_render_validation_required':True,'executed':False}
(OUT/'proposal.json').write_text(json.dumps(proposal,indent=2)+'\n')

if not apply and not verify:
    unreal.log('SURVIVOR_LOD_PLAN_ONLY '+json.dumps(proposal))
else:
    describe=getattr(unreal.OldWestAssetAuthoring,'describe_survivor_lods',None)
    assert describe,'Build the staged Engine-only LOD validation method before changing the mesh'
    def inspect():
        report=json.loads(describe())
        assert report.get('lods'),'No imported geometry to validate'
        return report
    before=inspect() if first_apply else json.loads((OUT/'before-generation.json').read_text())
    baseline=before['lods'][0]
    protected_files=[p for p in CONTENT.rglob('*.uasset') if p not in
                     (SOURCE,CONTENT/'LOD_Survivor_CinematicTactical.uasset')]
    protected={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in protected_files}
    if apply:
        assert len(before['lods'])==1,'The preserved baseline must contain only the imported hero LOD'
        assert baseline['invalid_weight_vertices']==0 and baseline['invalid_bone_influences']==0
        if revise:
            current=inspect()
            assert len(current['lods'])==len(PLAN),'Revision expects the existing generated detail levels'
            assert current['lods'][0]==baseline,'Existing hero differs from the original baseline'
            revision_backup=OUT/('before-hair-revision-'+time.strftime('%Y%m%dT%H%M%SZ',time.gmtime()))
            revision_backup.mkdir()
            for path in (SOURCE,CONTENT/'LOD_Survivor_CinematicTactical.uasset',
                         OUT/'authoring-report.json',OUT/'fresh-validation.json'):
                shutil.copy2(path,revision_backup/path.name)
            for path in list(OUT.glob('*-lod-comparison.png'))+list(OUT.glob('deformation-captures*.json')):
                shutil.copy2(path,revision_backup/path.name)
            (revision_backup/'input-readout.json').write_text(json.dumps(current,indent=2)+'\n')
        else:
            (OUT/'before-generation.json').write_text(json.dumps(before,indent=2)+'\n')
        backup=OUT/'SKM_Survivor_A_Cm-before-lods.uasset'
        if not backup.exists():shutil.copy2(SOURCE,backup)
        factory=unreal.DataAssetFactory()
        factory.set_editor_property('data_asset_class',unreal.SkeletalMeshLODSettings)
        settings=unreal.load_asset(SETTINGS_PATH) if unreal.EditorAssetLibrary.does_asset_exist(SETTINGS_PATH) else \
            unreal.AssetToolsHelpers.get_asset_tools().create_asset(
                'LOD_Survivor_CinematicTactical',BASE,unreal.SkeletalMeshLODSettings,factory)
        assert settings
        eye_slots={i for i,material in enumerate(before['materials']) if material['slot'] in {
            'M_Survivor_Sclera','M_Survivor_Iris','M_Survivor_EyeBack',
            'M_Survivor_Cornea','M_Survivor_Tearline'}}
        assert len(eye_slots)==5
        hair_slots={i for i,material in enumerate(before['materials']) if material['slot']=='M_Survivor_Hair'}
        assert len(hair_slots)==1
        priority_sections=[i for i,section in enumerate(baseline['sections'])
                           if section['material'] in eye_slots|hair_slots]
        def configure_groups(seed=False):
            groups=[]
            for level in PLAN:
                reduction=unreal.SkeletalMeshOptimizationSettings()
                values={'termination_criterion':unreal.SkeletalMeshTerminationCriterion.SMTC_NUM_OF_TRIANGLES,
                        'num_of_triangles_percentage':1.0 if seed else level['triangle_fraction'],
                        'base_lod':0,'remap_morph_targets':True,'recalc_normals':False,
                        'max_bones_per_vertex':max(8,baseline['max_influences']),
                        'enforce_bone_boundaries':True,'merge_coincident_vert_bones':True,
                        'volume_importance':1.0,'lock_edges':False,
                        'silhouette_importance':unreal.SkeletalMeshOptimizationImportance.SMOI_HIGH,
                        'skinning_importance':unreal.SkeletalMeshOptimizationImportance.SMOI_HIGH,
                        'texture_importance':unreal.SkeletalMeshOptimizationImportance.SMOI_HIGH,
                        'shading_importance':unreal.SkeletalMeshOptimizationImportance.SMOI_HIGH}
                for key,value in values.items():reduction.set_editor_property(key,value)
                group=unreal.SkeletalMeshLODGroupSettings()
                group.set_editor_property('reduction_settings',reduction)
                group.set_editor_property('screen_size',unreal.PerPlatformFloat(default=level['screen_size']))
                group.set_editor_property('lod_hysteresis',level['hysteresis'])
                group.set_editor_property('bone_list',[])
                # Keep the eyes and complete hairstyle. Global reduction alone
                # preserved a nonempty hair section but left visible scalp holes.
                group.set_editor_property('bones_to_prioritize',[])
                group.set_editor_property('sections_to_prioritize',priority_sections)
                group.set_editor_property('weight_of_prioritization',1000.0)
                groups.append(group)
            settings.set_editor_property('lod_groups',groups)
        settings.set_editor_property('min_lod',unreal.PerPlatformInt(default=0))
        settings.set_editor_property('disable_below_min_lod_stripping',unreal.PerPlatformBool(default=True))
        settings.set_editor_property('override_lod_streaming_settings',False)
        # UE validates priority indices against the DESTINATION LOD's current
        # sections. On first creation that LOD is empty, so valid eye priorities
        # are discarded. Populate full-detail section sets first, then reapply
        # the intended settings to the existing lower LODs before reduction.
        if not revise:
            configure_groups(seed=True)
            mesh.lod_settings=settings
            assert edit.regenerate_lod(mesh,4,False,False),'Full-section LOD seeding failed'
            seeded=inspect()
            material_ids={s['material'] for s in baseline['sections'] if s['triangles']>0}
            # AddSourceModel also halves the previous generated LOD's ratio. If a
            # seed loses a section, restore full detail now all LODInfos exist.
            if any({s['material'] for s in lod['sections'] if s['triangles']>0}!=material_ids
                   for lod in seeded['lods']):
                mesh.lod_settings=settings
                assert edit.regenerate_lod(mesh,4,True,False),'Full-detail section restore failed'
                seeded=inspect()
            (OUT/'section-seeding.json').write_text(json.dumps(seeded,indent=2)+'\n')
            assert len(seeded['lods'])==4
            assert seeded['lods'][0]['geometry_weights_sha1']==baseline['geometry_weights_sha1']
            for lod in seeded['lods']:
                assert {s['material'] for s in lod['sections'] if s['triangles']>0}==material_ids, \
                    f"Full-detail section seed dropped material at LOD {lod['lod']}"
            unreal.log('SURVIVOR_LOD_FULL_SECTIONS_SEEDED')
        configure_groups(seed=False)
        # Reflected property assignment calls the BlueprintSetter, transferring
        # reduction/priority settings to all existing LODInfos.
        mesh.lod_settings=settings
        assert edit.regenerate_lod(mesh,4,True,False),'Skeletal mesh reduction failed'

    after=inspect()
    (OUT/'latest-generation-attempt.json').write_text(json.dumps(after,indent=2)+'\n')
    assert len(after['lods'])==4
    settings=mesh.get_editor_property('lod_settings')
    assert settings and settings.get_path_name()==SETTINGS_PATH+'.LOD_Survivor_CinematicTactical'
    groups=list(settings.get_editor_property('lod_groups'))
    assert len(groups)==len(PLAN)
    for group,level in zip(groups,PLAN):
        reduction=group.get_editor_property('reduction_settings')
        assert abs(group.get_editor_property('screen_size').get_editor_property('default')-level['screen_size'])<1e-6
        assert abs(group.get_editor_property('lod_hysteresis')-level['hysteresis'])<1e-6
        assert abs(reduction.get_editor_property('num_of_triangles_percentage')-level['triangle_fraction'])<1e-6
        assert reduction.get_editor_property('base_lod')==0
        assert reduction.get_editor_property('remap_morph_targets')
        assert not group.get_editor_property('bone_list')
    assert after['reference_skeleton_sha1']==before['reference_skeleton_sha1']
    assert after['materials']==before['materials']
    hero=after['lods'][0]
    # Counts alone do not establish fidelity. Exact semantic data fingerprints
    # must match before saving: positions, tangent basis, UVs, color, indices,
    # material/bone maps, skin weights and every hero morph vertex delta.
    for key in ['geometry_weights_sha1','morphs','vertices','triangles','sections']:
        assert hero[key]==baseline[key],f'Hero LOD0 changed: {key}; do not save'
    required_morphs={name for name,value in baseline['morphs'].items() if value['deltas']>0}
    material_ids={s['material'] for s in baseline['sections'] if s['triangles']>0}
    upper_ratios=[1.0,.50,.28,.23]
    for lod in after['lods']:
        assert lod['invalid_weight_vertices']==0 and lod['invalid_bone_influences']==0
        assert lod['non_finite_vertices']==0
        assert {s['material'] for s in lod['sections'] if s['triangles']>0}==material_ids, \
            f"Material section loss at LOD {lod['lod']}"
        preserve_slots={i for i,material in enumerate(before['materials']) if material['slot'] in {
            'M_Survivor_Sclera','M_Survivor_Iris','M_Survivor_EyeBack',
            'M_Survivor_Cornea','M_Survivor_Tearline','M_Survivor_Hair'}}
        for slot in preserve_slots:
            original=sum(s['triangles'] for s in baseline['sections'] if s['material']==slot)
            actual=sum(s['triangles'] for s in lod['sections'] if s['material']==slot)
            assert actual==original,f"Priority surface lost triangles: LOD {lod['lod']}, material {slot}"
        assert required_morphs<={name for name,value in lod['morphs'].items() if value['deltas']>0}
        assert lod['triangles']<=baseline['triangles']*upper_ratios[lod['lod']]
        if lod['lod']:
            assert lod['triangles']<after['lods'][lod['lod']-1]['triangles']
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==digest for p,digest in protected.items())
    if apply:
        if write_gate:
            # Resource coordination, not an asset-quality bypass: other agents
            # may render the unchanged source while reductions run in memory.
            # The gate is released only after those runtimes have exited.
            (OUT/'ready-to-save.json').write_text(json.dumps(after,indent=2)+'\n')
            unreal.log('SURVIVOR_LOD_VALIDATED_WAITING_TO_SAVE '+str(write_gate))
            deadline=time.monotonic()+900
            while not write_gate.exists():
                assert time.monotonic()<deadline,'Timed out waiting for runtime processes to release the mesh'
                time.sleep(2)
            assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==digest for p,digest in protected.items())
        assert unreal.EditorAssetLibrary.save_loaded_asset(settings,only_if_is_dirty=False)
        assert unreal.EditorAssetLibrary.save_loaded_asset(mesh,only_if_is_dirty=False)
    after.update({'levels':PLAN,'fresh_reload':verify,'hero_lod0_exact_data_preserved':True,
                  'protected_asset_sha256':protected,'deformation_render_validation_required':True,
                  'morph_delta_presence_is_not_visual_deformation_qa':True})
    (OUT/('fresh-validation.json' if verify else 'authoring-report.json')).write_text(json.dumps(after,indent=2)+'\n')
    unreal.log('SURVIVOR_LOD_VALIDATED '+json.dumps({'fresh_reload':verify,
        'triangles':[lod['triangles'] for lod in after['lods']],'hero_lod0_exact_data_preserved':True}))
