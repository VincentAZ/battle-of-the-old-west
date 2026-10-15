"""Provider-name-independent anatomical mapping for the inspected Mixar biped topology."""
import math

FINGERS = ('Thumb', 'Index', 'Middle', 'Ring', 'Pinky')


def canonical_parents():
    parents = dict(Hips='root', Spine='Hips', Spine1='Spine', Spine2='Spine1', Neck='Spine2', Head='Neck')
    for side in ('Left', 'Right'):
        for part, parent in [('Shoulder', 'Spine2'), ('Arm', side+'Shoulder'), ('ForeArm', side+'Arm'), ('Hand', side+'ForeArm'), ('UpLeg', 'Hips'), ('Leg', side+'UpLeg'), ('Foot', side+'Leg'), ('ToeBase', side+'Foot')]:
            parents[side+part] = parent
        for finger in FINGERS:
            for digit in range(1, 4):
                parents[side+'Hand'+finger+str(digit)] = side+'Hand'+finger+str(digit-1) if digit > 1 else side+'Hand'
    return parents


def infer_mapping(bones):
    """Infer anatomy from topology and rest positions; refuse unfamiliar/ambiguous guides.

    Coordinates must be world-space, Z-up, character facing -Y. Finger bases are
    ordered geometrically from the thumb; provider bone names/order are unused.
    """
    nodes = {b['name']: b for b in bones}
    assert len(nodes) == len(bones), 'Duplicate guide bones'
    children = {n: [b['name'] for b in bones if b['parent'] == n] for n in nodes}
    roots = [n for n in nodes if nodes[n]['parent'] is None]
    assert len(roots) == 1, 'Expected one guide root'
    root = roots[0]
    mapping = {root: 'Hips'}

    def chain(n, strict=True):
        result = [n]
        while children[result[-1]]:
            if len(children[result[-1]]) != 1:
                if not strict: return []
                raise AssertionError('Expected linear anatomical chain')
            result.append(children[result[-1]][0])
        return result

    def dist(a, b):
        return math.dist(nodes[a]['head'], nodes[b]['head'])

    hands = [n for n in nodes if len(children[n]) == 5 and all(len(chain(c, False)) == 3 for c in children[n])]
    assert len(hands) == 2, 'Expected two hands with five three-joint fingers'
    shoulders = []
    for hand in hands:
        n = hand
        for _ in range(3): n = nodes[n]['parent']
        shoulders.append(n)
    shoulder_center_x = sum(nodes[n]['head'][0] for n in shoulders)/2
    shoulders = []
    sides = set()
    for hand in hands:
        arm_chain = [hand]
        for _ in range(3):
            arm_chain.append(nodes[arm_chain[-1]]['parent'])
        shoulder = arm_chain[-1]
        shoulders.append(shoulder)
        side = 'Left' if nodes[shoulder]['head'][0] > shoulder_center_x else 'Right'
        assert side not in sides, 'Both shoulders on same side: explicit mapping required'
        sides.add(side)
        for n, part in zip(reversed(arm_chain), ('Shoulder', 'Arm', 'ForeArm', 'Hand')):
            mapping[n] = side+part
        bases = sorted(children[hand], key=lambda n: dist(n, hand))
        thumb = bases[0]
        assert dist(thumb, hand) < .85*dist(bases[1], hand), 'Ambiguous thumb: explicit mapping required'
        bases = [thumb] + sorted(bases[1:], key=lambda n: dist(n, chain(thumb)[-1]))
        for base, finger in zip(bases, FINGERS):
            for i, n in enumerate(chain(base), 1):
                mapping[n] = side+'Hand'+finger+str(i)
    necks = {nodes[s]['parent'] for s in shoulders}
    assert len(necks) == 1, 'Shoulders do not share neck branch'
    branch = necks.pop()
    head_children = [n for n in children[branch] if n not in shoulders]
    assert len(head_children) == 1, 'Ambiguous head chain'
    head_chain = chain(head_children[0])
    # Providers attach clavicles either to the top spine or the neck.
    height = max(b['head'][2] for b in bones)-min(b['head'][2] for b in bones)
    branch_is_spine = len(head_chain) >= 2 and nodes[head_chain[0]]['head'][2]-nodes[branch]['head'][2] > .075*height
    neck = head_chain.pop(0) if branch_is_spine else branch
    mapping[neck] = 'Neck'
    for n in head_chain:
        mapping[n] = 'Head'
    torso = []
    n = nodes[neck]['parent']
    while n != root:
        assert n is not None, 'Torso disconnected from root'
        torso.append(n)
        n = nodes[n]['parent']
    torso.reverse()
    assert len(torso) in (2, 3), 'Expected two or three spine joints'
    for n, name in zip(torso, ('Spine', 'Spine1', 'Spine2')):
        mapping[n] = name
    hips_branch = torso[0]
    leg_roots = [n for parent in (root, hips_branch) for n in children[parent] if n not in mapping and len(chain(n, False)) in (4, 5)]
    assert len(leg_roots) == 2, 'Expected two leg branches'
    leg_center_x = sum(nodes[n]['head'][0] for n in leg_roots)/2
    leg_sides = set()
    for leg in leg_roots:
        side = 'Left' if nodes[leg]['head'][0] > leg_center_x else 'Right'
        assert side not in leg_sides, 'Ambiguous leg sides'
        leg_sides.add(side)
        parts = chain(leg)
        assert len(parts) in (4, 5), 'Expected four-joint leg plus optional toe end'
        assert nodes[parts[2]]['head'][2] < nodes[leg]['head'][2], 'Leg must descend toward foot'
        for i, n in enumerate(parts):
            mapping[n] = side+('UpLeg', 'Leg', 'Foot', 'ToeBase')[min(i, 3)]
    for n in set(nodes)-set(mapping):
        # The inspected Lozen provider output has a weight-bearing hip helper.
        parent = nodes[n]['parent']
        assert parent in (root, hips_branch) and not children[n], 'Unclassified guide bone: '+n
        assert abs(nodes[n]['head'][2]-nodes[hips_branch]['head'][2]) < .08*height, 'Helper is not near hips'
        mapping[n] = mapping[parent]
    assert set(mapping) == set(nodes)
    return mapping
