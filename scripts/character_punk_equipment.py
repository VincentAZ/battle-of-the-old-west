"""Surface-fitted respirator and shoulder protection on the preserved Punk rig."""
import math
import bpy
from mathutils import Vector
from author_vigilante_headgear_candidate import Geometry, bind_soft_expressions
from character_fitted_accessories import surface_info, atlas_patch


def cylinder(geo, center, axis, profile, uv, sides=48):
    axis=Vector(axis).normalized();center=Vector(center)
    u=axis.cross(Vector((0,0,1))).normalized();v=axis.cross(u).normalized()
    start=len(geo.vertices)
    for along,radius in profile:
        for i in range(sides):
            angle=i*math.tau/sides
            geo.vertex(center+axis*along+radius*(u*math.cos(angle)+v*math.sin(angle)))
    for row in range(len(profile)-1):
        for i in range(sides):
            a=start+row*sides+i;b=start+row*sides+(i+1)%sides
            geo.face((a,b,b+sides,a+sides),[uv]*4)
    geo.face(tuple(start+i for i in reversed(range(sides))),[uv]*sides)
    end=start+(len(profile)-1)*sides
    geo.face(tuple(end+i for i in range(sides)),[uv]*sides)
    return u,v,axis


def rounded_bar(geo,a,b,width,depth,normal,uv):
    # Closed rectangular slats with chamfered edges, oriented on the filter face.
    a,b,normal=Vector(a),Vector(b),Vector(normal).normalized()
    tangent=(b-a).normalized();side=tangent.cross(normal).normalized();bevel=min(width,depth)*.22
    contour=[(-width/2+bevel,-depth/2), (width/2-bevel,-depth/2), (width/2,-depth/2+bevel),
             (width/2,depth/2-bevel),(width/2-bevel,depth/2),(-width/2+bevel,depth/2),
             (-width/2,depth/2-bevel),(-width/2,-depth/2+bevel)]
    start=len(geo.vertices)
    for point in (a,b):
        for x,y in contour:geo.vertex(point+side*x+normal*y)
    for i in range(8):geo.face((start+i,start+(i+1)%8,start+(i+1)%8+8,start+i+8),[uv]*4)
    geo.face(tuple(start+i for i in reversed(range(8))),[uv]*8)
    geo.face(tuple(start+8+i for i in range(8)),[uv]*8)


def finish(geo,name,material,arm,uv,bone='mixamorig:Head'):
    obj=geo.object(name,material,arm);atlas_patch(obj,uv)
    if bone!='mixamorig:Head':
        obj.vertex_groups.clear();obj.vertex_groups.new(name=bone).add(list(range(len(obj.data.vertices))),1,'REPLACE')
    return obj


def front_hit(tree,x,z):
    p,n,_,_=tree.ray_cast(Vector((x,-.3,z)),Vector((0,1,0)),.4)
    assert p is not None,('Missing respirator support',x,z)
    return p,n


def respirator(face,arm,material,rubber_uv,metal_uv):
    skin=surface_info(face);tree=skin['tree'];columns=96;rows=9
    outline=[]
    for i in range(columns):
        angle=i*math.tau/columns
        x=.051*math.cos(angle);z=1.571+.038*math.sin(angle)
        p,n=front_hit(tree,x,z);outline.append((p,n))
    # The rigid shell leaves room for facial motion; only the seal follows skin.
    center=Vector((0,-.120,1.574));shell=Geometry()
    for layer in range(2):
        shell.vertex(center+Vector((0,layer*.0025,0)))
        for row in range(1,rows):
            fraction=row/(rows-1)
            for hit,n in outline:
                edge=hit+Vector((0,-.009,0))
                point=center.lerp(edge,fraction)
                point.y-=.006*math.sin(math.pi*fraction)
                point.y+=layer*.0025
                shell.vertex(point)
    section=1+(rows-1)*columns
    for layer in range(2):
        base=layer*section
        for i in range(columns):shell.face((base,base+1+i,base+1+(i+1)%columns),[rubber_uv]*3)
        for row in range(rows-2):
            for i in range(columns):
                a=base+1+row*columns+i;b=base+1+row*columns+(i+1)%columns
                shell.face((a,b,b+columns,a+columns),[rubber_uv]*4)
    last=1+(rows-2)*columns
    for i in range(columns):
        a=last+i;b=last+(i+1)%columns;shell.face((a,b,b+section,a+section),[rubber_uv]*4)
    parts=[finish(shell,'Punk_Respirator_Shell',material,arm,rubber_uv)]
    seal=Geometry()
    for ring in range(4):
        for i,(hit,n) in enumerate(outline):
            angle=i*math.tau/columns
            radial=Vector((math.cos(angle),0,math.sin(angle)))
            # Rear inner/outer loops fit the cheeks. Front loops close against
            # the rigid shell, making a real flexible face seal.
            p=hit+n*.0025 if ring<2 else hit+Vector((0,-.009,0))
            p+=radial*(.0015 if ring in (1,2) else -.0015)
            seal.vertex(p)
    for ring in range(4):
        for i in range(columns):
            a=ring*columns+i;b=ring*columns+(i+1)%columns
            c=((ring+1)%4)*columns+(i+1)%columns;d=((ring+1)%4)*columns+i
            seal.face((a,b,c,d),[rubber_uv]*4)
    gasket=finish(seal,'Punk_Respirator_Face_Seal',material,arm,rubber_uv)
    seal_binding=bind_soft_expressions(gasket,face,range(columns*2));parts.append(gasket)
    housing,trim,grille=Geometry(),Geometry(),Geometry()
    for sign in (-1,1):
        center=Vector((sign*.039,-.099,1.557));axis=Vector((sign*.43,-.9,-.07)).normalized()
        u,v,n=cylinder(housing,center,axis,[(-.014,.012),(0,.014),(.003,.020),(.007,.022),(.023,.022),(.026,.0195)],rubber_uv)
        for t in (.006,.012,.020):
            cylinder(trim,center,axis,[(t-.0006,.0222),(t,.023),(t+.0006,.0222)],metal_uv)
        cylinder(trim,center,axis,[(.024,.021),(.0265,.021),(.028,.0185)],metal_uv)
        cylinder(housing,center,axis,[(.027,.0175),(.028,.0175)],rubber_uv)
        for row in range(-3,4):
            y=row*.0042;half=math.sqrt(.016**2-y*y)
            point=center+axis*.029+v*y
            rounded_bar(grille,point-u*half,point+u*half,.0018,.0015,axis,metal_uv)
    # Small central exhalation valve and its three protective grille ribs.
    center=Vector((0,-.1205,1.554));axis=Vector((0,-1,-.12)).normalized()
    cylinder(housing,center,axis,[(-.018,.008),(-.008,.010),(0,.011)],rubber_uv)
    u,v,n=cylinder(trim,center,axis,[(0,.011),(.003,.013),(.006,.011)],metal_uv)
    cylinder(housing,center,axis,[(.006,.0095),(.007,.0095)],rubber_uv)
    for row in (-1,0,1):
        p=center+axis*.008+v*(row*.005)
        rounded_bar(grille,p-u*.007,p+u*.007,.0016,.0012,axis,metal_uv)
    parts += [finish(housing,'Punk_Respirator_Filter_Housings',material,arm,rubber_uv),
              finish(trim,'Punk_Respirator_Filter_Rims',material,arm,metal_uv),
              finish(grille,'Punk_Respirator_Filter_Grilles',material,arm,metal_uv)]
    # One continuous retaining band passes under the ears and around the nape.
    path=[]
    start=outline[0][0]+Vector((0,-.010,0));end=outline[columns//2][0]+Vector((0,-.010,0))
    for i in range(97):
        angle=-.35+(math.pi+.70)*i/96
        direction=Vector((math.cos(angle),math.sin(angle),0));z=1.585-.030*abs(math.cos(angle))**3
        origin=Vector((0,.025,z));p,n,_,_=tree.ray_cast(origin+direction*.25,-direction,.30)
        assert p is not None
        path.append(p+n*.0035)
    path=[start.lerp(path[0],i/12) for i in range(12)]+path+[path[-1].lerp(end,i/12) for i in range(1,13)]
    band=Geometry();width=.007
    for layer in range(2):
        for p in path:
            for sign in (-1,1):
                q=p+Vector((0,0,sign*width/2))
                hit,normal,_,_=tree.find_nearest(q)
                band.vertex(hit+normal*(.0042+layer*.0012))
    section=len(path)*2
    for layer in range(2):
        base=layer*section
        for i in range(len(path)-1):
            a=base+i*2;band.face((a,a+1,a+3,a+2),[rubber_uv]*4)
    for edge in (0,1):
        for i in range(len(path)-1):
            a=i*2+edge;b=a+2;band.face((a,b,b+section,a+section),[rubber_uv]*4)
    for i in (0,len(path)-1):
        a=i*2;band.face((a,a+1,a+1+section,a+section),[rubber_uv]*4)
    strap=finish(band,'Punk_Respirator_Retaining_Band',material,arm,rubber_uv)
    strap_binding=bind_soft_expressions(strap,face,range(len(strap.data.vertices)));parts.append(strap)
    return parts,dict(method='Contoured rigid shell, flexible cheek seal, twin ribbed filter cartridges with physical grilles, and continuous nape band',seal=seal_binding,strap=strap_binding)


def pauldron(body,outfit,arm,material,metal_uv,rubber_uv):
    garments=outfit if isinstance(outfit,(list,tuple)) else [outfit]
    surfaces=[surface_info(o) for o in [body]+list(garments)]
    bone=arm.data.bones['mixamorig:LeftArm'];axis=(bone.tail_local-bone.head_local).normalized()
    outward=Vector((1,0,0));outward=(outward-axis*outward.dot(axis)).normalized()
    front=axis.cross(outward).normalized()
    if front.y>0:front=-front
    rows,columns=15,49;supports=[]
    for row in range(rows):
        fraction=row/(rows-1);along=-.036+fraction*.135
        half_angle=1.05+.35*math.sin(math.pi*fraction)
        origin=bone.head_local+axis*along
        for column in range(columns):
            # Keep the front edge outside the chest panel when the arm lowers.
            front_angle=.95-.15*fraction
            angle=-half_angle+(half_angle+front_angle)*column/(columns-1)
            direction=outward*math.cos(angle)+front*math.sin(angle)
            hits=[]
            for surface in surfaces:
                p,n,_,_=surface['tree'].ray_cast(origin+direction*.23,-direction,.26)
                if p is not None:hits.append(((p-origin).dot(direction),p,n))
            assert hits,('Missing shoulder support',row,column)
            _,p,n=max(hits,key=lambda x:x[0]);supports.append((p,direction))
    plate=Geometry()
    for layer in range(2):
        for i,(p,direction) in enumerate(supports):
            row,column=divmod(i,columns)
            lift=.006+(.003 if layer==0 else 0)+.002*math.sin(math.pi*row/(rows-1))*math.cos((-1+2*column/(columns-1))*math.pi/2)
            plate.vertex(p+direction*lift)
    section=rows*columns
    for layer in range(2):
        for row in range(rows-1):
            for column in range(columns-1):
                a=layer*section+row*columns+column;plate.face((a,a+1,a+1+columns,a+columns),[metal_uv]*4)
    boundary=list(range(columns))+[r*columns+columns-1 for r in range(1,rows)]+[(rows-1)*columns+c for c in range(columns-2,-1,-1)]+[r*columns for r in range(rows-2,0,-1)]
    for i,a in enumerate(boundary):
        b=boundary[(i+1)%len(boundary)];plate.face((a,b,b+section,a+section),[metal_uv]*4)
    main=finish(plate,'Punk_Contoured_Pauldron',material,arm,metal_uv,bone.name)
    trim,fasteners=Geometry(),Geometry()
    trim.ring_tube([plate.vertices[i] for i in boundary],.0015,rubber_uv,sides=6)
    for row in (2,rows-3):
        for col in (5,columns//2,columns-6):
            i=row*columns+col;p,direction=supports[i]
            cylinder(fasteners,plate.vertices[i]-direction*.001,direction,[(0,.0035),(.002,.0035),(.003,.0027)],metal_uv,sides=12)
    parts=[main,finish(trim,'Punk_Pauldron_Edge_Binding',material,arm,rubber_uv,bone.name),finish(fasteners,'Punk_Pauldron_Fasteners',material,arm,metal_uv,bone.name)]
    return parts,dict(method='Thin closed plate fitted over the sleeve, with edge binding and six physical fasteners',bone=bone.name,vertices=len(main.data.vertices),triangles=sum(len(p.vertices)-2 for p in main.data.polygons))
