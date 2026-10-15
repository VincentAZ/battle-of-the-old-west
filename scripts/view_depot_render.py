"""Show the actual 4K render in Blender without changing the saved 3D layout."""
import bpy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
path=ROOT/'art/water_depot_v2/WaterDepot_4K.png'
im=bpy.data.images.load(str(path),check_existing=True)
def show():
    window=bpy.context.window
    if not window:return .5
    area=max(window.screen.areas,key=lambda a:a.width*a.height)
    area.type='IMAGE_EDITOR';area.spaces.active.image=im
    region=next(r for r in area.regions if r.type=='WINDOW')
    with bpy.context.temp_override(window=window,area=area,region=region):
        bpy.ops.image.view_all(fit_view=True)
    return None
bpy.app.timers.register(show,first_interval=1)
