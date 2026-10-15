"""Move the driver to the opposite side and reduce the engine to 80% size."""
import bpy
from mathutils import Matrix, Vector


def apply_layout_revision():
    s=bpy.context.scene
    if s.get('Driver side and engine scale revision'):return
    reflect=Matrix.Diagonal((-1,1,1,1))
    driver_objects=[o for o in s.objects if o.name.startswith('Punk 2 — driver')]
    assert driver_objects,'Punk driver must be staged first'
    for o in driver_objects:
        if o.parent not in driver_objects:o.matrix_world=reflect@o.matrix_world
    wheel=bpy.data.objects.get('Steering wheel');assert wheel
    wheel.matrix_world=reflect@wheel.matrix_world
    for o in s.objects:
        if o.name.startswith('Armored side window') and o.type=='MESH':
            x=sum((o.matrix_world@v.co).x for v in o.data.vertices)/len(o.data.vertices)
            o.hide_render=x>0;o.hide_set(x>0)
            o['state']='Window rolled fully down for driver' if x>0 else 'Window closed'
        if o.name.startswith(('Wing mirror housing','Reflective mirror')):
            o.location.y+=.36 if o.location.x<0 else -.36
        if o.name.startswith('Mirror arm') and o.type=='CURVE':
            for spline in o.data.splines:
                spline.points[-1].co.y+=.36 if spline.points[0].co.x<0 else -.36
    for name,target in [
        ('01 HERO front three-quarter',(0,0,1.48)),
        ('02 REAR mechanical detail',(0,.2,1.35)),
        ('03 FRONT low angle',(0,-.1,1.53)),
        ('04 CREW driver and gunner',(.25,0,2.03)),
    ]:
        cam=bpy.data.objects.get(name)
        if cam:
            cam.location.x=-cam.location.x
            cam.rotation_euler=(Vector(target)-cam.location).to_track_quat('-Z','Y').to_euler()
    # Scale the complete mechanical assembly about its block mounting centre.
    # Aperture trim belongs to the existing hood and stays fitted to its edges.
    col=bpy.data.collections['11 EXPOSED TURBO ENGINE']
    engine=[o for o in col.objects if not o.name.startswith('Raw hood aperture')]
    pivot=Vector((0,-1.23,1.15))
    transform=Matrix.Translation(pivot)@Matrix.Scale(.8,4)@Matrix.Translation(-pivot)
    original={o.name:o.matrix_world.copy() for o in engine}
    for o in engine:o.matrix_world=transform@original[o.name]
    bpy.context.view_layer.update()
    for o in engine:
        ratio=o.matrix_world.to_scale().x/original[o.name].to_scale().x
        assert abs(ratio-.8)<1e-5,(o.name,ratio)
    driver=next(o for o in driver_objects if o.type=='ARMATURE')
    head=driver.matrix_world@driver.pose.bones['mixamorig:Head'].head
    assert head.x>.9
    assert wheel.location.x>0
    s['Crew staging']='Punk 1 seated on roof at gun; Punk 2 on +X seat, +X window down, head out and looking forward.'
    s['Driver side and engine scale revision']='Driver and steering wheel moved from -X to +X; complete engine and turbo scaled uniformly to 80% about the block mount.'
    s['Engine assembly scale']=.8
    print('LAYOUT_REVISION',len(engine),'engine parts at 80%; driver head',list(head),flush=True)
