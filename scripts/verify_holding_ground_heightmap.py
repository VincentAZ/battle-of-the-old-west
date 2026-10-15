"""Compare encoded terrain interpolation with independently raycast rim samples.

This tests the lookup data and displacement arithmetic, not GPU rendering.
"""
import hashlib
import json
from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'art/western/holdings/ground-fit-v001'
audit_path = ROOT/'art/western/holdings/expansion-game-v001/post-office/ground-clearance-v001.json'
audit = json.loads(audit_path.read_text())
image = (OUT/'T_ArenaGroundHeight.tga').read_bytes()
header = struct.unpack('<BBBHHBHHHHBB', image[:18])
assert header[2] == 2 and header[8:12] == (261, 261, 24, 32)


def pixel(x, y):
    blue, green, red = image[18+(y*261+x)*3:21+(y*261+x)*3]
    return (red*256+green-32768)/16, blue > 127


def surface(x, y):
    gx, gy = (x+6500)/50, (y+6500)/50
    i, j = int(gx), int(gy)
    fx, fy = gx-i, gy-j
    a, rising = pixel(i, j)
    b, _ = pixel(i+1, j)
    c, _ = pixel(i, j+1)
    d, _ = pixel(i+1, j+1)
    if rising:
        return a+(b-a)*fx+(d-b)*fy if fy <= fx else a+(d-c)*fx+(c-a)*fy
    return a+(b-a)*fx+(c-a)*fy if fx+fy <= 1 else d+(c-d)*(1-fx)+(b-d)*(1-fy)


samples = []
origin = audit['native_component']['location']
assert audit['native_component']['scale'] == [1, 1, 1]
assert audit['native_component']['quaternion_xyzw'] == [0, 0, 0, 1]
for s in audit['samples']:
    x, y, z = s['world_cm']
    outside = (max(abs(x-origin[0])-225, 0)**2+max(abs(y-origin[1])-133, 0)**2)**.5
    assert outside >= 60, 'A rim vertex would not fully conform'
    h = surface(x, y)
    error = h-s['terrain_z_cm']
    assert abs(error) <= .03126
    fitted_z = z+h-origin[2]+.5
    clearance = fitted_z-s['terrain_z_cm']
    assert .86 < clearance < .94
    samples.append(dict(vertex=s['vertex'], lookup_error_cm=error, fitted_clearance_cm=clearance))
report = dict(ok=True, scope=__doc__.strip(), samples=samples,
    minimum_fitted_clearance_cm=min(s['fitted_clearance_cm'] for s in samples),
    maximum_fitted_clearance_cm=max(s['fitted_clearance_cm'] for s in samples),
    maximum_lookup_error_cm=max(abs(s['lookup_error_cm']) for s in samples),
    reference_audit_sha256=hashlib.sha256(audit_path.read_bytes()).hexdigest(),
    height_texture_sha256=hashlib.sha256(image).hexdigest(), gpu_verification='requires native capture')
(OUT/'lookup-validation.json').write_text(json.dumps(report, indent=2)+'\n')
print('HOLDING_GROUND_LOOKUP_PASSED', report['minimum_fitted_clearance_cm'], report['maximum_fitted_clearance_cm'])
