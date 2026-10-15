"""Read saved map rock bounds and imported Trouble bounds without saving assets."""
import hashlib
import json
from pathlib import Path
import unreal

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'art/western/trouble/route-clearance-v001'
OUT.mkdir(exist_ok=True)
MAP = ROOT / 'game/OldWest/Content/Maps/WaterDepotV2.umap'
before = hashlib.sha256(MAP.read_bytes()).hexdigest()
assert unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).load_level('/Game/Maps/WaterDepotV2')


def vector(v):
    return [v.x, v.y, v.z]


rocks = []
for actor in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
    if not isinstance(actor, unreal.StaticMeshActor):
        continue
    part = actor.static_mesh_component
    mesh = part.static_mesh
    if not mesh or mesh.get_name() not in ('SM_rock_07', 'SM_coast_rocks_05'):
        continue
    center, extent = actor.get_actor_bounds(False)
    rocks.append(dict(actor=actor.get_path_name(), label=actor.get_actor_label(),
                      mesh=mesh.get_path_name(), center=vector(center), extent=vector(extent),
                      location=vector(actor.get_actor_location()),
                      collision=str(part.get_collision_enabled()), actor_collision=actor.get_actor_enable_collision(),
                      visible=part.is_visible()))
props = []
for path in unreal.EditorAssetLibrary.list_assets('/Game/Art/Western/Trouble', recursive=True):
    if '/Meshes/SM_Trouble_' not in path:
        continue
    mesh = unreal.load_asset(path)
    if not isinstance(mesh, unreal.StaticMesh):
        continue
    box = mesh.get_bounds()
    props.append(dict(mesh=path, center=vector(box.origin), extent=vector(box.box_extent)))
assert hashlib.sha256(MAP.read_bytes()).hexdigest() == before
(OUT / 'saved-map-inventory.json').write_text(json.dumps(dict(
    map_sha256=before, map_unchanged=True, rocks=rocks, trouble_meshes=props), indent=2) + '\n')
print('TROUBLE_ROUTE_INVENTORY', len(rocks), len(props))
