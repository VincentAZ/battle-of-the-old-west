"""Read-only CPU studio evaluation of an isolated candidate at dense bad frames."""
import argparse,hashlib,json,os,sys,traceback
from pathlib import Path
import bpy
from mathutils import Vector

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--frames',nargs='+',type=float,default=[10.,11.,12.,12.5,13.,14.,25.,65.,91.])
    parser.add_argument('--view',choices=['front-right','front-left'],default='front-right')
    parser.add_argument('--report',default='render-preflight.json')
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:]);source=args.source.resolve()
    path=source/'Scientist_Holster_Candidate.blend';before=hashlib.sha256(path.read_bytes()).hexdigest()
    bpy.ops.wm.open_mainfile(filepath=str(path),use_scripts=False);scene=bpy.context.scene
    for obj in list(bpy.data.objects):
        if obj.type in {'CAMERA','LIGHT'}:bpy.data.objects.remove(obj,do_unlink=True)
    scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=32;scene.cycles.use_denoising=True
    scene.render.threads_mode='FIXED';scene.render.threads=4
    scene.render.resolution_x=1000;scene.render.resolution_y=1000;scene.render.resolution_percentage=100
    if scene.world is None:scene.world=bpy.data.worlds.new('CPU_Review_World')
    scene.world.color=(.15,.15,.15)
    scene.view_settings.view_transform='AgX'
    for name,where,power,size in [('Key',(2,-3,4),900,4),('Fill',(-3,-1,2.8),500,3)]:
        data=bpy.data.lights.new(name,'AREA');data.energy=power;data.shape='DISK';data.size=size
        light=bpy.data.objects.new(name,data);scene.collection.objects.link(light);light.location=where
        light.rotation_euler=(Vector((0,0,1.0))-light.location).to_track_quat('-Z','Y').to_euler()
    camera=bpy.data.objects.new('Native_side_review',bpy.data.cameras.new('Native_side_review'));scene.collection.objects.link(camera)
    scene.camera=camera;camera.location=(2.8 if args.view=='front-right' else -2.8,-2.8,2.5);camera.data.lens=75
    camera.rotation_euler=(Vector((0,0,1.20))-camera.location).to_track_quat('-Z','Y').to_euler()
    files=[]
    for frame in args.frames:
        assert 1<=frame<=91
        out=source/f'{frame:05.1f}-{args.view}.png';assert not out.exists(),'Preserve existing render'
        scene.frame_set(int(frame),subframe=frame-int(frame));bpy.context.view_layer.update()
        scene.render.filepath=str(out);bpy.ops.render.render(write_still=True);files.append(str(out))
    assert hashlib.sha256(path.read_bytes()).hexdigest()==before
    report=source/args.report;assert not report.exists()
    report.write_text(json.dumps({'status':'CPU stills; manual review pending','source':str(path),
        'source_sha256':before,'source_unchanged':True,'images':files,'render_device':'CPU','threads':4},indent=2)+'\n')
try:
    main();code=0
except BaseException:
    traceback.print_exc();code=1
sys.stdout.flush();sys.stderr.flush();os._exit(code)
