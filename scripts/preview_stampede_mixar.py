"""Render real single-longhorn poses and animation frames in Mixar."""
import argparse,json,sys
from pathlib import Path
import bpy
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'art/western/stampede/animation-v001'
p=argparse.ArgumentParser();p.add_argument('--sequence',choices=['Idle','Run']);p.add_argument('--camera',default='side');p.add_argument('--samples',type=int,default=16)
a=p.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
bpy.ops.wm.open_mainfile(filepath=str(OUT/'Longhorn-Animated.blend'))
s=bpy.context.scene;arm=next(o for o in s.objects if o.type=='ARMATURE')
s.cycles.samples=a.samples;s.render.resolution_x=960;s.render.resolution_y=720
s.render.image_settings.file_format='PNG'
def pose(clip,frame,camera,path):
    arm.animation_data.action=bpy.data.actions['Longhorn_'+clip]
    s.camera=next(o for o in s.objects if o.type=='CAMERA' and o.name=='Review_'+camera)
    s.frame_set(frame);bpy.context.view_layer.update()
    s.render.filepath=str(path);bpy.ops.render.render(write_still=True)
    print('STAMPEDE_RENDER',clip,frame,camera,flush=True)
if a.sequence:
    dest=OUT/'previews'/('frames-'+a.sequence.lower()+'-'+a.camera);dest.mkdir(parents=True,exist_ok=True)
    for frame in range(120 if a.sequence=='Idle' else 24):
        pose(a.sequence,frame,a.camera,dest/f'{frame:04d}.png')
else:
    dest=OUT/'previews';dest.mkdir(exist_ok=True)
    for clip,frame,camera in [('Idle',0,'three-quarter'),('Run',0,'side'),('Run',6,'side'),('Run',12,'side'),('Run',18,'side'),('Run',6,'three-quarter'),('Run',6,'game-camera')]:
        pose(clip,frame,camera,dest/f'{clip.lower()}-{frame:03d}-{camera}.png')
