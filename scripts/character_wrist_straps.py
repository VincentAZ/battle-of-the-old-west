"""Closed wrist straps and seated studs fitted to the existing skin surface."""
import math
import bpy
from mathutils import Vector
from author_vigilante_headgear_candidate import Geometry
from character_fitted_accessories import surface_info, binding, atlas_patch


def fitted_wrist_straps(body, arm, strap_material, stud_material, strap_uv, stud_uvs, name):
    skin = surface_info(body)
    parts, reports = [], []

    def finish(geo, part_name, material, uv, supports):
        obj = geo.object(part_name, material, arm)
        obj.vertex_groups.clear()
        for index, (point, triangle) in enumerate(supports):
            ids, bary = binding(skin, point, triangle)
            values = {}
            for i, fraction in zip(ids, bary):
                for group in body.data.vertices[i].groups:
                    bone_name = body.vertex_groups[group.group].name
                    values[bone_name] = values.get(bone_name, 0.) + max(0., fraction)*group.weight
            total = sum(values.values())
            assert total > .99
            for bone_name, value in values.items():
                if value > 1e-8:
                    group = obj.vertex_groups.get(bone_name) or obj.vertex_groups.new(name=bone_name)
                    group.add([index], value/total, 'REPLACE')
        atlas_patch(obj, uv)
        obj['wrist_strap_surface_binding'] = True
        return obj

    for side in ('Left', 'Right'):
        bone = arm.data.bones['mixamorig:'+side+'ForeArm']
        head, tail = arm.matrix_world@bone.head_local, arm.matrix_world@bone.tail_local
        axis = (tail-head).normalized()
        front = Vector((0, -1, 0))
        front = (front-axis*front.dot(axis)).normalized()
        across = axis.cross(front).normalized()
        rows, columns = 7, 96
        width = .024
        center = head.lerp(tail, .8)
        rings = []
        for row in range(rows):
            origin = center+axis*((row/(rows-1)-.5)*width)
            ring = []
            for col in range(columns):
                angle = math.tau*col/columns
                direction = front*math.cos(angle)+across*math.sin(angle)
                hit, normal, triangle, distance = skin['tree'].ray_cast(origin, direction, .09)
                assert hit is not None and .012 < distance < .065, (name, side, row, col)
                ring.append((hit, direction, triangle))
            rings.append(ring)
        geo, supports = Geometry(), []
        for offset in (.0027, .0015):
            for ring in rings:
                for hit, direction, triangle in ring:
                    geo.vertex(hit+direction*offset)
                    supports.append((hit, triangle))
        section = rows*columns
        for layer in range(2):
            for row in range(rows-1):
                for col in range(columns):
                    a = layer*section+row*columns+col
                    b = layer*section+row*columns+(col+1)%columns
                    geo.face((a, b, b+columns, a+columns))
        for row in (0, rows-1):
            for col in range(columns):
                a, b = row*columns+col, row*columns+(col+1)%columns
                geo.face((a, b, b+section, a+section))
        strap = finish(geo, name+'_Wrist_Strap_'+side, strap_material, strap_uv, supports)

        # The stud's bottom is seated within the strap's thickness. Its curved
        # base follows the same skin support, keeping the metal attached as the
        # small hand/forearm weight transition moves beneath it.
        stud, stud_supports = Geometry(), []
        def stud_vertex(along, lateral, offset):
            origin = center+axis*along+across*lateral+front*.09
            hit, normal, triangle, distance = skin['tree'].ray_cast(origin, -front, .1)
            assert hit is not None, (name, side, along, lateral)
            stud.vertex(hit+front*offset)
            stud_supports.append((hit, triangle))
        sides = 48
        profile = [(.0045,.0020), (.0050,.0025), (.0050,.0036), (.0040,.0044)]
        for radius, offset in profile:
            for col in range(sides):
                angle = math.tau*col/sides
                stud_vertex(radius*math.cos(angle), radius*math.sin(angle), offset)
        for row in range(len(profile)-1):
            for col in range(sides):
                a, b = row*sides+col, row*sides+(col+1)%sides
                stud.face((a, b, b+sides, a+sides))
        bottom = len(stud.vertices);stud_vertex(0, 0, .0020)
        top = len(stud.vertices);stud_vertex(0, 0, .0046)
        for col in range(sides):
            stud.face((bottom, (col+1)%sides, col))
            a, b = (len(profile)-1)*sides+col, (len(profile)-1)*sides+(col+1)%sides
            stud.face((top, a, b))
        fastener = finish(stud, name+'_Wrist_Stud_'+side, stud_material, stud_uvs[side], stud_supports)
        parts.extend((strap, fastener))
        reports.append(dict(side=side,forearm_fraction=.8,width_mm=width*1000,strap_inner_offset_mm=1.5,strap_outer_offset_mm=2.7,
                            stud_seated_offset_mm=2.0,stud_top_offset_mm=4.6,strap_vertices=len(geo.vertices),stud_vertices=len(stud.vertices),
                            strap=strap.name,stud=fastener.name,bones=sorted({g.name for obj in (strap,fastener) for g in obj.vertex_groups}),
                            body_supports=[dict(vertex=i,point_m=list(p),triangle=t) for i,(p,t) in enumerate(supports)]))
    return parts, dict(method='Closed contoured straps and curved seated studs, using barycentric skin weights',wrists=reports)
