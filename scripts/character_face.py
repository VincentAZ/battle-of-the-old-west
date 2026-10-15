"""Distinct facial sculpts on the preserved Survivor topology and expressions.

All facial surfaces, including the eye shells and mouth interior, use the same
continuous spatial deformation. The neck seam, scalp and rest rig stay fixed.
Dimensions are meters on the existing source mesh, not guessed rig landmarks.
"""
import json
import math

import bpy
from mathutils import Vector


PROFILES = {
    'quanah_parker': dict(jaw=.007, chin_width=.002, chin_height=.0015, chin_forward=.002,
                        cheek_width=-.001, cheek_forward=-.001, cheek_height=0,
                        nose_width=-.0014, nose_forward=-.0018, nose_height=0,
                        brow_forward=.0025, brow_height=-.001,
                        mouth_width=-.0015, lip_forward=-.0003),
    'bartender': dict(jaw=-.006, chin_width=-.003, chin_height=.003, chin_forward=-.001,
                 cheek_width=.0045, cheek_forward=.0035, cheek_height=0,
                 nose_width=-.0008, nose_forward=-.003, nose_height=.0015,
                 brow_forward=-.0008, brow_height=.002,
                 mouth_width=.0025, lip_forward=.001),
    'charles_goodnight': dict(jaw=.004, chin_width=.003, chin_height=-.007, chin_forward=.0035,
                      cheek_width=.003, cheek_forward=.001, cheek_height=.003,
                      nose_width=.002, nose_forward=.005, nose_height=-.001,
                      brow_forward=.002, brow_height=-.0008,
                      mouth_width=.0005, lip_forward=-.0007),
}


def sculpt_point(point, profile):
    x, y, z = point
    if z <= 1.505 or z >= 1.697:
        return point.copy()

    def smooth(value):
        value = max(0., min(1., value))
        return value * value * (3 - 2 * value)

    def region(center, radius):
        return math.exp(-2 * sum(((a - b) / r) ** 2 for a, b, r in zip(point, center, radius)))

    sign = math.tanh(x / .016)
    jaw = region((.052 if x >= 0 else -.052, -.028, 1.55), (.05, .075, .041))
    chin = region((0, -.055, 1.536), (.040, .065, .032))
    cheek = region((.055 if x >= 0 else -.055, -.038, 1.608), (.031, .067, .030))
    nose = region((0, -.083, 1.602), (.018, .035, .030))
    nostril = region((0, -.083, 1.593), (.027, .033, .013))
    brow = region((.030 if x >= 0 else -.030, -.052, 1.650), (.034, .041, .015))
    mouth = region((0, -.070, 1.566), (.035, .041, .018))
    dx = sign * (profile['jaw'] * jaw + profile['chin_width'] * chin
                 + profile['cheek_width'] * cheek + profile['mouth_width'] * mouth)
    dx += math.tanh(x / .008) * profile['nose_width'] * nostril
    dy = -(profile['chin_forward'] * chin + profile['cheek_forward'] * cheek
           + profile['nose_forward'] * nose + profile['brow_forward'] * brow
           + profile['lip_forward'] * mouth)
    dz = (profile['chin_height'] * chin + profile['cheek_height'] * cheek
          + profile['nose_height'] * nose + profile['brow_height'] * brow)
    influence = smooth((z - 1.505) / .020) * smooth((1.697 - z) / .020)
    return point + Vector((dx, dy, dz)) * influence


def author_face(card):
    if card not in PROFILES:
        return None
    profile = PROFILES[card]
    names = ['Survivor_Face_27Shapes', 'Eye_L_eyeball', 'Eye_R_eyeball',
             'Lacrimal_Caruncle', 'Tearline']
    report = {'card_id': card, 'profile_m': profile, 'components': [],
              'neck_and_scalp_fixed': True, 'weights_preserved': True,
              'expression_visual_review_required': True}
    for name in names:
        obj = bpy.data.objects[name]
        assert not obj.get('identity_face_profile'), 'Refusing to apply a facial sculpt twice'
        inverse = obj.matrix_world.inverted()
        original = [obj.matrix_world @ vertex.co for vertex in obj.data.vertices]
        weights = [tuple((g.group, g.weight) for g in v.groups) for v in obj.data.vertices]
        key_names = []
        if obj.data.shape_keys:
            key_names = [key.name for key in obj.data.shape_keys.key_blocks]
            for key in obj.data.shape_keys.key_blocks:
                for point in key.data:
                    point.co = inverse @ sculpt_point(obj.matrix_world @ point.co, profile)
        for vertex, before in zip(obj.data.vertices, original):
            vertex.co = inverse @ sculpt_point(before, profile)
        obj.data.update()
        assert weights == [tuple((g.group, g.weight) for g in v.groups) for v in obj.data.vertices]
        if obj.data.shape_keys:
            assert key_names == [key.name for key in obj.data.shape_keys.key_blocks]
        distances = [(obj.matrix_world @ v.co - p).length for v, p in zip(obj.data.vertices, original)]
        assert max(distances) < .020, (card, name, 'Sculpt exceeds 2 cm deformation budget')
        assert all(distance < 1e-6 for p, distance in zip(original, distances) if p.z <= 1.505 or p.z >= 1.697)
        report['components'].append({'name': name, 'vertices': len(original),
                                      'shape_keys': key_names, 'max_displacement_m': max(distances)})
        obj['identity_face_profile'] = card
    bpy.data.objects[names[0]]['identity_face_report'] = json.dumps(report)
    return report
