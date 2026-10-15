"""Stage a project-authored Prospector sorting gesture; CPU Blender only.

Run Blender background with --python this_file -- --render. Outputs only a
new candidate directory. Existing character meshes, clips and Unreal assets
are protected. This studio fixture has three anonymous samples and a selected
middle sample; it is NOT connected to game state or evidence of native play.
"""
import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Quaternion, Vector

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'art/characters/survivor_variants/deformation-v3/scientist/Scientist.blend'
parser = argparse.ArgumentParser()
parser.add_argument('--output', type=Path, default=ROOT / 'art/characters/scientist_gesture/candidate-v11')
parser.add_argument('--render', action='store_true')
args = parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
OUT = args.output.resolve(); OUT.mkdir(parents=True, exist_ok=True)
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
protected = {str(SOURCE): sha(SOURCE)}
protected.update({str(p): sha(p) for p in (ROOT / 'game/OldWest/Content/Art/Survivors').rglob('*.uasset')})
bpy.ops.wm.open_mainfile(filepath=str(SOURCE), use_scripts=False)
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
assert arm.name == 'Survivor_Rig' and len(arm.data.bones) == 53
arm.animation_data_clear()
for action in list(bpy.data.actions): bpy.data.actions.remove(action)
for bone in arm.pose.bones: bone.matrix_basis.identity()
for obj in list(bpy.data.objects):
    if obj.type not in {'ARMATURE', 'MESH'}: bpy.data.objects.remove(obj, do_unlink=True)
for image in bpy.data.images:
    if image.filepath: image.filepath = bpy.path.abspath(image.filepath)
scene = bpy.context.scene
scene.unit_settings.system = 'METRIC'; scene.unit_settings.scale_length = 1
scene.render.fps = 30; scene.frame_start = 1; scene.frame_end = 271
scene.view_settings.view_transform = 'AgX'
reference = [{'name': b.name, 'parent': b.parent.name if b.parent else None,
              'matrix': [list(row) for row in b.matrix_local], 'deform': b.use_deform} for b in arm.data.bones]
parts, roots, material_specs = [], {}, {}


def activate(obj):
    bpy.ops.object.select_all(action='DESELECT'); obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def root(name, position=(0, 0, 0)):
    obj = bpy.data.objects.new(name, None); bpy.context.collection.objects.link(obj)
    obj.location = position; roots[name] = obj
    return obj


def material(name, color, roughness, metallic=0, emission=0):
    mat = bpy.data.materials.new(name); mat.use_nodes = True
    mat.diffuse_color = (*color, 1)
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    bsdf = nodes.get('Principled BSDF')
    bsdf.inputs['Base Color'].default_value = (*color, 1)
    bsdf.inputs['Roughness'].default_value = roughness
    bsdf.inputs['Metallic'].default_value = metallic
    tex = nodes.new('ShaderNodeTexNoise'); tex.inputs['Scale'].default_value = 190
    tex.inputs['Detail'].default_value = 3
    coord = nodes.new('ShaderNodeTexCoord'); links.new(coord.outputs['Object'], tex.inputs['Vector'])
    bump = nodes.new('ShaderNodeBump'); bump.inputs['Strength'].default_value = .16
    bump.inputs['Distance'].default_value = .00015
    links.new(tex.outputs['Fac'], bump.inputs['Height']); links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
    if emission:
        bsdf.inputs['Emission Color'].default_value = (*color, 1)
        bsdf.inputs['Emission Strength'].default_value = emission
    material_specs[name] = dict(base_color=color, roughness=roughness, metallic=metallic,
                                microrelief_meters=.00015, emission=emission)
    return mat


M = {key: material('M_ScientistAnalysis_' + key, color, rough, metal, emission) for key, color, rough, metal, emission in [
    ('TealPaint', (.035, .16, .145), .42, .25, 0), ('Steel', (.20, .24, .25), .38, .9, 0),
    ('Brass', (.38, .24, .072), .36, .85, 0), ('Rubber', (.015, .02, .021), .84, 0, 0),
    ('Foam', (.029, .039, .04), .97, 0, 0), ('Ceramic', (.49, .47, .35), .51, 0, 0),
    ('Amber', (.45, .13, .016), .23, .05, .35), ('Green', (.038, .35, .21), .2, .05, .55),
    ('Lens', (.025, .075, .11), .12, .4, 0), ('Dark', (.009, .016, .02), .65, .3, 0)]}


def finish(obj, name, mat, parent, bevel=0):
    obj.name = name; obj.data.materials.append(mat)
    activate(obj); bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if bevel:
        modifier = obj.modifiers.new('Manufactured_edge_radius', 'BEVEL'); modifier.width = bevel; modifier.segments = 3
        bpy.ops.object.modifier_apply(modifier=modifier.name)
    for face in obj.data.polygons: face.use_smooth = True
    # Local prop geometry/pivots are intentional, independent of the 53 bones.
    obj.parent = parent
    parts.append(obj)
    return obj


def box(name, position, dimensions, mat, parent, bevel=.004):
    bpy.ops.mesh.primitive_cube_add(size=1, location=position)
    obj = bpy.context.object; obj.dimensions = dimensions
    return finish(obj, name, mat, parent, bevel)


def cylinder(name, position, radius, depth, mat, parent, axis=(0, 0, 1), vertices=32):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=depth, location=position)
    obj = bpy.context.object; obj.rotation_euler = Vector(axis).to_track_quat('Z', 'Y').to_euler()
    return finish(obj, name, mat, parent, min(.0015, radius * .1))


def rail(name, start, end, radius, mat, parent):
    a, b = Vector(start), Vector(end)
    return cylinder(name, (a+b)*.5, radius, (b-a).length, mat, parent, b-a)


case = root('AnalysisCase_Base', (0, -.34, .98))
box('Case_lower_moulded_shell', (0, 0, -.006), (.70, .32, .11), M['TealPaint'], case, .023)
box('Case_rubber_perimeter', (0, 0, .041), (.714, .332, .021), M['Rubber'], case, .019)
box('Case_work_surface', (0, 0, .055), (.661, .288, .018), M['Steel'], case, .009)
box('Case_foam_insert', (0, -.026, .067), (.475, .244, .012), M['Foam'], case, .01)
for x in (-.326, .326):
    for y in (-.126, .126):
        box('Corner_protection', (x, y, -.012), (.046, .055, .12), M['Rubber'], case, .009)
        cylinder('Shell_through_bolt', (x, y, .068), .006, .007, M['Steel'], case, vertices=16)
for x in (-.23, .23):
    box('Front_latch_bracket', (x, .167, .012), (.063, .014, .051), M['Steel'], case)
    rail('Front_latch_spring', (x-.019, .178, .015), (x+.019, .178, .015), .005, M['Brass'], case)
    rail('Folding_leg', (x, -.08, -.045), (x*1.34, -.13, -.965), .014, M['Steel'], case)
    rail('Folding_leg', (x, .08, -.045), (x*1.34, .16, -.965), .014, M['Steel'], case)
    rail('Leg_crossbar', (x*1.22, -.115, -.56), (x*1.22, .13, -.56), .009, M['Steel'], case)
    for y in (-.13, .16): box('Grounded_rubber_foot', (x*1.34, y, -.986), (.070, .055, .038), M['Rubber'], case, .009)
rail('Right_side_bracing_grip', (.470,.025,.152),(.470,.14,.152),.014,M['Rubber'],case)
for y in (.025,.14):rail('Right_bracing_handle_mount',(.345,y,.152),(.470,y,.152),.008,M['Steel'],case)
rail('Case_carry_handle', (-.09, .196, -.01), (.09, .196, -.01), .014, M['Rubber'], case)
for x in (-.095, .095): rail('Carry_handle_mount', (x, .161, -.01), (x, .196, -.01), .009, M['Steel'], case)

lid = root('AnalysisCase_Lid_Hinge', (-.356, -.34, 1.049))
box('Hollow_lid_ceiling', (.356, 0, .145), (.712, .326, .026), M['TealPaint'], lid, .012)
box('Lid_moulded_inner_foam', (.356, 0, .123), (.655, .273, .018), M['Foam'], lid, .012)
for x in (.010, .702):box('Lid_end_wall', (x,0,.071),(.020,.31,.142),M['TealPaint'],lid,.008)
for y in (-.152,.152):box('Lid_side_wall', (.356,y,.071),(.678,.017,.142),M['TealPaint'],lid,.008)
for y in (-.11,.11):cylinder('Side_lid_hinge_barrel',(0,y,0),.011,.070,M['Steel'],lid,(0,1,0))
for x in (.06,.65):
    for y in (-.12,.12):cylinder('Lid_fastener',(x,y,.163),.0055,.006,M['Steel'],lid,vertices=16)
rail('Lid_grip',(.146,.02,.220),(.276,.02,.220),.012,M['Rubber'],lid)
for x in (.146,.276):rail('Lid_grip_mount',(x,.02,.158),(x,.02,.220),.007,M['Steel'],lid)

trays = []
for index, x in enumerate((-.155, 0, .155)):
    tray = root(f'SampleTray_{index+1}', (x, -.368, 1.053))
    box('Recessed_ceramic_tray', (0, 0, .013), (.133, .176, .026), M['Ceramic'], tray, .012)
    box('Dark_sample_recess', (0, 0, .028), (.105, .145, .009), M['Dark'], tray, .009)
    for side in (-1, 1):
        box('Raised_side_rim', (side*.061, 0, .034), (.010, .161, .030), M['Steel'], tray, .004)
        box('Raised_end_rim', (0, side*.079, .034), (.119, .009, .030), M['Steel'], tray, .004)
    for mark in range(index+1): box('Anonymous_sample_index_mark', ((mark-index*.5)*.012, .08, .052), (.006, .013, .004), M['Brass'], tray, .001)
    trays.append(tray)
output = root('SelectedSample_OutputModule', (.271, -.33, 1.054))
box('Output_module_body', (0, 0, .012), (.13, .18, .034), M['TealPaint'], output, .012)
box('Actual_sample_slot', (0, 0, .032), (.071, .112, .015), M['Dark'], output, .007)
for y in (-.061, .061): rail('Output_slot_guide', (-.046, y, .042), (.046, y, .042), .005, M['Steel'], output)
cylinder('Output_indicator', (.048, .05, .039), .008, .009, M['Amber'], output)
cylinder('Sample_receiver_stud', (0,0,.053), .012, .046, M['Steel'], output)

scanner = root('HandScanner_GripAnchor', (-.258, -.205, 1.148))
cylinder('Scanner_grip', (0,-.070,-.028), .017, .110, M['Rubber'], scanner, (1,0,0))
box('Scanner_neck', (0,-.116,-.004),(.025,.080,.018),M['Steel'],scanner,.007)
box('Scanner_curved_housing', (0, -.180, -.023), (.080, .105, .060), M['TealPaint'], scanner, .021)
box('Scanner_display_bezel', (0, -.180, .009), (.060, .068, .012), M['Steel'], scanner, .009)
box('Scanner_display_glass', (0, -.180, .016), (.046, .049, .005), M['Lens'], scanner, .004)
for index in range(4): box('Scanner_live_gauge_segment', (-.015+index*.01, -.180, .02), (.005, .008+index*.006, .003), M['Green'], scanner, .001)
cylinder('Downward_scanner_sensor', (0, -.199, -.060), .023, .018, M['Steel'], scanner)
cylinder('Optical_lens', (0, -.199, -.071), .017, .004, M['Lens'], scanner)
cylinder('Side_scan_trigger', (.055, -.070, -.026), .009, .010, M['Brass'], scanner, (1, 0, 0))
for x in (-.027, .027):
    for y in (-.157, -.207): cylinder('Scanner_screw', (x, y, .010), .003, .005, M['Steel'], scanner, vertices=12)
for x in (-.035,.035):
    box('Scanner_dock_support',(-.258+x,-.005,.096),(.010,.060,.038),M['Rubber'],case,.004)

samples = []
for index, x in enumerate((-.155, 0, .155)):
    sample = root(f'AnonymousSalvageSample_{index+1}', (x, -.368, 1.1))
    cylinder('Salvage_capsule', (0, 0, 0), .020, .028, M['Steel'], sample)
    cylinder('Sample_retaining_band', (0, 0, .004), .024, .009, M['Brass'], sample)
    for angle in range(0, 360, 60):
        a = math.radians(angle)
        cylinder('Sample_bolt', (.016*math.cos(a), .016*math.sin(a), .017), .0027, .004, M['Dark'], sample, vertices=12)
    samples.append(sample)


def smooth(value):
    value = min(1., max(0., value)); return value*value*(3-2*value)


def blend(a, b, frame, start, end):
    return Vector(a).lerp(Vector(b), smooth((frame-start)/(end-start)))


def key(obj, frame):
    obj.rotation_mode = 'QUATERNION'
    obj.keyframe_insert('location', frame=frame); obj.keyframe_insert('rotation_quaternion', frame=frame)


def hand_rotation(side, forward=(0, -1, 0), normal=(0, 0, -1)):
    hand = arm.data.bones['mixamorig:'+side+'Hand']
    index = arm.data.bones['mixamorig:'+side+'HandIndex1'].head_local
    pinky = arm.data.bones['mixamorig:'+side+'HandPinky1'].head_local
    rest_f = ((index+pinky)*.5-hand.head_local).normalized()
    rest_n = rest_f.cross(index-pinky).normalized() * (1 if side == 'Left' else -1)
    rest_x = rest_f.cross(rest_n).normalized()
    desired_f, desired_n = Vector(forward).normalized(), Vector(normal).normalized()
    desired_x = desired_f.cross(desired_n).normalized()
    original = Matrix((rest_x, rest_f, rest_n)).transposed()
    desired = Matrix((desired_x, desired_f, desired_n)).transposed()
    return (desired @ original.inverted()).to_quaternion()


def pose_arm(side, contact, curl=0, rotation=None):
    """Analytical two-link solve, with a fixed outside elbow pole and no stretch."""
    upper = arm.pose.bones['mixamorig:'+side+'Arm']
    lower = arm.pose.bones['mixamorig:'+side+'ForeArm']
    hand = arm.pose.bones['mixamorig:'+side+'Hand']
    quat = rotation or hand_rotation(side)
    index = arm.data.bones['mixamorig:'+side+'HandIndex1'].head_local
    pinky = arm.data.bones['mixamorig:'+side+'HandPinky1'].head_local
    palm_rest = (hand.bone.head_local + (index+pinky)*.5)*.5
    offset = quat @ (palm_rest-hand.bone.head_local)
    wrist = Vector(contact)-offset
    shoulder = upper.head.copy(); delta = wrist-shoulder
    a, b = upper.bone.length, lower.bone.length
    distance = delta.length
    assert abs(a-b)+.0001 < distance < a+b-.0001, f'{side} unreachable contact: {contact}; wrist distance {distance}, reach {a+b}'
    direction = delta.normalized()
    pole = Vector((1 if side == 'Left' else -1, .28, -.18))
    pole = (pole-direction*pole.dot(direction)).normalized()
    along = (a*a-b*b+distance*distance)/(2*distance)
    elbow = shoulder + direction*along + pole*math.sqrt(max(0., a*a-along*along))
    def aim(bone, toward):
        rest = bone.bone.matrix_local
        q = (bone.bone.tail_local-bone.bone.head_local).rotation_difference(Vector(toward).normalized())
        bone.matrix = Matrix.Translation(bone.head) @ q.to_matrix().to_4x4() @ rest.to_3x3().to_4x4()
        bpy.context.view_layer.update()
    aim(upper, elbow-shoulder)
    # Carry pronation through the forearm instead of placing the whole roll
    # at the wrist. Preserve the solved elbow/wrist and original bone lengths.
    hand_world = quat @ hand.bone.matrix_local.to_quaternion()
    hand_relative = lower.bone.matrix_local.to_quaternion().inverted() @ hand.bone.matrix_local.to_quaternion()
    lower_rotation = hand_world @ hand_relative.inverted()
    lower_rotation = (lower_rotation @ Vector((0,1,0))).rotation_difference((wrist-lower.head).normalized()) @ lower_rotation
    aim(lower, wrist-lower.head)
    lower_rotation = lower.matrix.to_quaternion().slerp(lower_rotation, .25)
    lower.matrix = Matrix.Translation(lower.head) @ lower_rotation.to_matrix().to_4x4()
    bpy.context.view_layer.update()
    hand.matrix = Matrix.Translation(hand.head) @ quat.to_matrix().to_4x4() @ hand.bone.matrix_local.to_3x3().to_4x4()
    bpy.context.view_layer.update()
    # Curl against the scanned device/sample rather than leaving a flat hand.
    forward, normal = quat @ ((index+pinky)*.5-hand.bone.head_local).normalized(), quat @ (
        ((index+pinky)*.5-hand.bone.head_local).normalized().cross(index-pinky).normalized() * (1 if side == 'Left' else -1))
    for finger in ('Index', 'Middle', 'Ring', 'Pinky'):
        for joint, amount in enumerate((.32, .70, 1.03), 1):
            bone = arm.pose.bones[f'mixamorig:{side}Hand{finger}{joint}']
            wanted = forward*math.cos(curl*amount) + normal*math.sin(curl*amount)
            current_axis = bone.tail-bone.head
            q = current_axis.rotation_difference(wanted.normalized())
            bone.matrix = Matrix.Translation(bone.head) @ q.to_matrix().to_4x4() @ bone.matrix.to_3x3().to_4x4()
            bpy.context.view_layer.update()
    if curl > .2:
        across = forward.cross(normal).normalized()
        thumb = [arm.pose.bones[f'mixamorig:{side}HandThumb{i}'] for i in (1,2,3)]
        target = Vector(contact) + (across*.059 + forward*.070 + normal*.024 if side == 'Right'
                                    else -across*.018 + forward*.055 + normal*.023)
        target = thumb[-1].tail.lerp(target, smooth((curl-.2)/.8))
        for _ in range(8):
            for bone in reversed(thumb):
                direction, desired = thumb[-1].tail-bone.head, target-bone.head
                if direction.length > 1e-6 and desired.length > 1e-6:
                    q = direction.rotation_difference(desired)
                    bone.matrix = Matrix.Translation(bone.head) @ q.to_matrix().to_4x4() @ bone.matrix.to_3x3().to_4x4()
                    bpy.context.view_layer.update()
    actual = hand.matrix @ hand.bone.matrix_local.inverted() @ palm_rest
    gap = (actual-Vector(contact)).length
    assert gap < .0002, f'{side} contact solve drift {gap}'
    return dict(palm_world_m=list(actual), desired_contact_m=list(contact), solver_gap_cm=gap*100,
                wrist_world_m=list(hand.head), elbow_world_m=list(lower.head), rotation_xyzw=[quat.x,quat.y,quat.z,quat.w])


frames = []
work_offset = Vector((0,-.075,0))
ready_r, ready_l = (-.22, .04, .90), (.22, .04, .90)
above_lid_r = (-.22,.03,1.33)
lid_handle = Vector((.211, .090, .244))
dock = Vector((-.258, -.205, 1.148))
handoff_outer = Vector((-.58, .05, 1.37))
handoff_inner = Vector((-.32, .02, 1.10))
for frame in range(1, 272):
    scene.frame_set(frame)
    for bone in arm.pose.bones: bone.matrix_basis.identity()
    # Enter and leave the work lean. Remaining pitched forward after closing
    # puts the carried instrument pocket through the case's rear lid edge.
    work_lean = smooth((frame-1)/29) * (1-smooth((frame-250)/21))
    for name, angle in (('Spine', 8), ('Spine1', 4), ('Spine2', 4), ('Neck', 0), ('Head', 8)):
        bone = arm.pose.bones['mixamorig:'+name]; bone.rotation_mode='QUATERNION'
        bone.rotation_quaternion = Quaternion((1, 0, 0), math.radians(angle)*work_lean)
    bpy.context.view_layer.update()
    angle = math.radians(70) * smooth((frame-30)/30)
    if frame > 225: angle *= 1-smooth((frame-225)/25)
    lid.rotation_mode='QUATERNION'; lid.rotation_quaternion=Quaternion((0,1,0),-angle)
    bpy.context.view_layer.update()
    handle = lid.matrix_world @ lid_handle
    right, left = Vector(ready_r), Vector(ready_l)
    rq, lq = hand_rotation('Right'), hand_rotation('Left')
    rcurl, lcurl = .12, .12
    phase = 'entry'
    if frame <= 30:
        right=blend(ready_r,above_lid_r,frame,1,15) if frame <= 15 else blend(above_lid_r,handle,frame,15,30)
        left=blend(ready_l,(.48,.04,1.19),frame,1,15) if frame <= 15 else blend((.48,.04,1.19),(.470,-.205,1.18),frame,15,30)
        rq=hand_rotation('Right',(0,0,-1),(1,0,0)).slerp(rq,smooth((frame-1)/14))
        lq=hand_rotation('Left',(0,0,-1),(-1,0,0)).slerp(lq,smooth((frame-1)/14))
    elif frame <= 60:
        phase='reach-open'; right=handle; left=Vector((.470,-.205,1.18))
        rq=Quaternion((0,1,0),-angle) @ hand_rotation('Right'); rcurl=1.4
    elif frame <= 80:
        phase='reach-scanner'
        # Move behind the open lid's rear edge before crossing its plane.
        # Preserve palm orientation while letting go, then rotate in clear air.
        if frame <= 67:
            right=blend(handle,handoff_outer,frame,60,67)
            rq=Quaternion((0,1,0),-angle) @ hand_rotation('Right')
        elif frame <= 73:
            right=blend(handoff_outer,handoff_inner,frame,67,73)
            rq=(Quaternion((0,1,0),-angle) @ hand_rotation('Right')).slerp(rq,smooth((frame-67)/6))
        else:right=blend(handoff_inner,dock,frame,73,80)
        left=Vector((.470,-.205,1.18))
        rcurl=1.4*(1-smooth((frame-60)/4)) if frame < 64 else 1.35*smooth((frame-76)/4)
    elif frame <= 135:
        phase='scan'
        if frame <= 93: right=blend(dock,(-.155,-.169,1.25),frame,80,93)
        elif frame <= 110: right=blend((-.155,-.169,1.25),(0,-.169,1.25),frame,93,110)
        elif frame <= 127: right=blend((0,-.169,1.25),(.155,-.169,1.25),frame,110,127)
        else:right=blend((.155,-.169,1.25),(-.14,-.15,1.25),frame,127,135)
        left=Vector((.470,-.205,1.18)); rcurl=1.35
    elif frame <= 185:
        phase='sort'
        right=Vector((-.14,-.15,1.25)); rcurl=1.35
        if frame <= 145:left=blend((.470,-.205,1.18),(0,-.313,1.135),frame,135,145)
        elif frame <= 156:left=blend((0,-.313,1.135),(.10,-.31,1.23),frame,145,156)
        elif frame <= 176:left=blend((.10,-.31,1.23),(.271,-.275,1.179),frame,156,176)
        else:left=Vector((.271,-.275,1.179))
        lcurl=1.3*smooth((frame-140)/5)*(1-smooth((frame-176)/9))
    else:
        phase='recover'
        left=blend((.271,-.275,1.179),(.32,-.15,1.29),frame,185,198) if frame <= 198 else blend((.32,-.15,1.29),ready_l,frame,198,220)
        if frame >198:lq=lq.slerp(hand_rotation('Left',(0,0,-1),(-1,0,0)),smooth((frame-198)/22))
        if frame <= 205:right=blend((-.14,-.15,1.25),dock,frame,185,205);rcurl=1.35
        elif frame <= 212:
            right=blend(dock,handoff_inner,frame,205,212)
            rcurl=1.35*(1-smooth((frame-205)/4))
        elif frame <= 218:
            right=blend(handoff_inner,handoff_outer,frame,212,218)
            rq=rq.slerp(Quaternion((0,1,0),-angle) @ hand_rotation('Right'),smooth((frame-212)/6))
        elif frame <= 225:
            right=blend(handoff_outer,handle,frame,218,225)
            rq=Quaternion((0,1,0),-angle) @ hand_rotation('Right')
            rcurl=1.4*smooth((frame-221)/4)
        elif frame <= 250:right=handle;rq=Quaternion((0,1,0),-angle) @ hand_rotation('Right');rcurl=1.4
        elif frame <= 258:
            right=blend(handle,above_lid_r,frame,250,258)
            rcurl=1.4*(1-smooth((frame-250)/4))
        else:
            right=blend(above_lid_r,ready_r,frame,258,271)
            rq=rq.slerp(hand_rotation('Right',(0,0,-1),(1,0,0)),smooth((frame-258)/13))
    contacts = {'right':pose_arm('Right',right+work_offset,rcurl,rq), 'left':pose_arm('Left',left+work_offset,lcurl,lq)}
    if 80 < frame <= 205:
        scanner.location=right; scanner.rotation_quaternion=Quaternion((1,0,0),0)
    else:scanner.location=dock;scanner.rotation_quaternion=Quaternion((1,0,0),0)
    scanner.rotation_mode='QUATERNION'
    for index, sample in enumerate(samples):sample.location=(index*.155-.155,-.368,1.1)
    if 145 < frame <= 176:samples[1].location=left+Vector((0,-.055,-.035))
    elif frame > 176:samples[1].location=(.271,-.33,1.144)
    for bone in arm.pose.bones:
        bone.rotation_mode='QUATERNION'
        bone.keyframe_insert('location',frame=frame)
        bone.keyframe_insert('rotation_quaternion',frame=frame)
        bone.keyframe_insert('scale',frame=frame)
    frames.append(dict(frame=frame,seconds=(frame-1)/30,phase=phase,contacts=contacts,
        bones={b.name:dict(location=list(b.location),rotation_xyzw=[b.rotation_quaternion.x,b.rotation_quaternion.y,b.rotation_quaternion.z,b.rotation_quaternion.w],scale=list(b.scale)) for b in arm.pose.bones},
        props={name:dict(location_m=list(obj.location+work_offset),rotation_xyzw=[obj.rotation_quaternion.x,obj.rotation_quaternion.y,obj.rotation_quaternion.z,obj.rotation_quaternion.w]) for name,obj in roots.items()}))

# Move the complete workspace and every contact by the same amount, keeping
# forearms in front of the coat rather than entering its open lapels.
for values in frames:
    for name, data in values['props'].items():
        obj=roots[name];obj.location=data['location_m']
        x,y,z,w=data['rotation_xyzw'];obj.rotation_quaternion=Quaternion((w,x,y,z))
        key(obj,values['frame'])

assert reference == [{'name': b.name, 'parent': b.parent.name if b.parent else None,
    'matrix': [list(row) for row in b.matrix_local], 'deform': b.use_deform} for b in arm.data.bones]
arm.animation_data.action.name='Scientist_Open_Scan_Sort_Recover_Candidate'
scene.frame_set(110)
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'Scientist_Analysis_Candidate.blend'))
report = dict(status='authored_CPU_candidate_native_integration_pending',source=str(SOURCE),source_sha256=protected[str(SOURCE)],
    rig_bones=53,expected_native_bones=54,rig_reference_unchanged=True,frames=271,fps=30,duration_seconds=9,
    phase_ranges={'entry':[1,30],'reach_open':[31,60],'reach_scanner':[61,80],'scan':[81,135],'sort':[136,185],'recover':[186,271]},
    coordinate_contract='Blender meters: feet origin, front -Y, up +Z. Exports use identical -Y/Z axes and physical centimeters. No rig bones added.',
    case_surface_height_cm=105.3,workspace_translation_m=list(work_offset),materials=material_specs,solver_max_gap_cm=max(c['solver_gap_cm'] for f in frames for c in f['contacts'].values()),
    contact_semantics='Analytical wrist/palm anchor agreement, not a mesh-surface intersection or native finger-contact pass.',
    output_selected_sample_index=1,anonymous_studio_sample_count=3,
    limitations=['CPU animation candidate; no native play or performance proof.',
        'Three anonymous studio samples and selected middle sample are a review fixture; runtime must use actual revealed count and choice, including Skip/depletion.',
        'Firearm holstering, carried-case deployment, unused sample rejection and junk output target reactions remain separate scene work.',
        'The nine-second studio routine is modular source animation, not a request to alter game or cinematic timing.',
        'Surface-contact and garment clearance require actual studio and later native review.'])
(OUT/'pose-and-prop-samples.json').write_text(json.dumps(frames,indent=2)+'\n')

# Animation-only centimeter FBX on the exact original rig. Rebuild the same
# basis keys at centimeter translation; do not multiply rig object scale.
arm.animation_data_clear(); arm.data.transform(Matrix.Scale(100,4))
scene.unit_settings.scale_length=.01
for f in frames:
    for name,values in f['bones'].items():
        bone=arm.pose.bones[name];bone.location=Vector(values['location'])*100
        x,y,z,w=values['rotation_xyzw'];bone.rotation_quaternion=Quaternion((w,x,y,z));bone.scale=values['scale']
        for channel in ('location','rotation_quaternion','scale'):bone.keyframe_insert(channel,frame=f['frame'])
arm.animation_data.action.name='Scientist_Analysis_Candidate_Cm'
activate(arm)
exports=[]
for name,first,last in [('Full',1,271),('Entry',1,30),('ReachOpen',31,60),('ReachScanner',61,80),('Scan',81,135),('Sort',136,185),('Recover',186,271)]:
    scene.frame_start=first;scene.frame_end=last
    path=OUT/f'A_Scientist_{name}_Cm.fbx'
    bpy.ops.export_scene.fbx(filepath=str(path),use_selection=True,object_types={'ARMATURE'},add_leaf_bones=False,
        use_armature_deform_only=True,bake_anim=True,bake_anim_use_all_actions=False,bake_anim_use_nla_strips=False,
        bake_anim_force_startend_keying=True,bake_anim_simplify_factor=0.,apply_unit_scale=True,
        apply_scale_options='FBX_SCALE_UNITS',axis_forward='-Y',axis_up='Z')
    exports.append(dict(path=str(path),sha256=sha(path),frames=[first,last]))
report['animation_exports']=exports

# Reload saved meter source for separate local-pivot static props and studios.
bpy.ops.wm.open_mainfile(filepath=str(OUT/'Scientist_Analysis_Candidate.blend'),use_scripts=False)
scene=bpy.context.scene;scene.frame_set(1)
prop_exports=[]
for name in roots:
    parent=bpy.data.objects[name]
    children=[o for o in bpy.data.objects if o.type=='MESH' and o.parent==parent]
    copies=[]
    for obj in children:
        duplicate=obj.copy();duplicate.data=obj.data.copy();bpy.context.collection.objects.link(duplicate)
        duplicate.parent=None
        local=parent.matrix_world.inverted() @ obj.matrix_world
        duplicate.data.transform(Matrix.Scale(100,4) @ local)
        duplicate.matrix_world=Matrix.Identity(4);copies.append(duplicate)
    activate(copies[0])
    for obj in copies:obj.select_set(True)
    bpy.ops.object.join();joined=bpy.context.object;joined.name='SM_'+name
    scene.unit_settings.scale_length=.01
    path=OUT/(joined.name+'_Cm.fbx')
    bpy.ops.export_scene.fbx(filepath=str(path),use_selection=True,object_types={'MESH'},bake_anim=False,
        apply_unit_scale=True,apply_scale_options='FBX_SCALE_UNITS',axis_forward='-Y',axis_up='Z',mesh_smooth_type='FACE')
    prop_exports.append(dict(path=str(path),sha256=sha(path),pivot=name,material_slots=[m.name for m in joined.data.materials]))
    bpy.data.objects.remove(joined,do_unlink=True)
report['prop_exports']=prop_exports

if args.render:
    scene.unit_settings.scale_length=1;scene.render.engine='CYCLES';scene.cycles.device='CPU'
    scene.cycles.samples=32;scene.cycles.use_denoising=True
    if hasattr(scene.cycles,'denoising_use_gpu'):scene.cycles.denoising_use_gpu=False
    scene.render.resolution_x=1280;scene.render.resolution_y=1080;scene.render.resolution_percentage=100
    world=bpy.data.worlds.new('Scientist_CPU_Studio');world.use_nodes=True
    world.node_tree.nodes['Background'].inputs[0].default_value=(.1,.13,.15,1)
    world.node_tree.nodes['Background'].inputs[1].default_value=.3;scene.world=world
    bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,-.025))
    floor=bpy.context.object;floor.data.materials.append(bpy.data.materials['M_ScientistAnalysis_Dark'])
    for name,pos,power,size,color in [('Key',(-3,-4,5),700,3.5,(1,.88,.72)),('Fill',(3,-2,3),450,3,(.65,.8,1)),('Rim',(0,3,4),850,3,(.8,.93,1))]:
        data=bpy.data.lights.new(name,'AREA');data.energy=power;data.shape='DISK';data.size=size;data.color=color
        obj=bpy.data.objects.new(name,data);bpy.context.collection.objects.link(obj);obj.location=pos
        obj.rotation_euler=(Vector((0,-.15,1))-obj.location).to_track_quat('-Z','Y').to_euler()
    data=bpy.data.cameras.new('Scientist_CPU_Review');camera=bpy.data.objects.new('Scientist_CPU_Review',data)
    bpy.context.collection.objects.link(camera);scene.camera=camera;data.lens=64
    images=[]
    for name,frame in [('entry',25),('open',55),('scan-left',94),('scan-right',125),('sort-lift',157),('sort-contact',176),('recover',265)]:
        scene.frame_set(frame)
        for view,pos,target in [('three-quarter',(2.8,-2.4,2.25),(0,-.19,1.04)),('contact',(1.3,-1.8,2.4),(0,-.28,1.15))]:
            if name == 'open' and view == 'contact':pos=(-1.9,-1.4,2.1);target=(-.3,-.32,1.27)
            if name == 'recover' and view == 'contact':pos=(1.3,-1.4,2.85);target=(0,-.1,1.1)
            camera.location=pos;camera.rotation_euler=(Vector(target)-camera.location).to_track_quat('-Z','Y').to_euler()
            path=OUT/(name+'-'+view+'.png');scene.render.filepath=str(path);bpy.ops.render.render(write_still=True)
            images.append(dict(phase=name,frame=frame,view=view,path=str(path),sha256=sha(path)))
            report['renders']=images;(OUT/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
assert all(sha(p)==digest for p,digest in protected.items()),'Protected source or native asset changed'
report.update(protected_source_and_native_assets_unchanged=True,protected_sha256=protected,
              blend_sha256=sha(OUT/'Scientist_Analysis_Candidate.blend'),manual_visual_review='pending')
(OUT/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
print('SCIENTIST_GESTURE_CANDIDATE_COMPLETE',str(OUT),flush=True)
