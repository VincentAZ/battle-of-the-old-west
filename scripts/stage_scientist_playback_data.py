"""Stage compact runtime prop clocks; no live Content or Unreal mutation."""
import json
from pathlib import Path
from scientist_import_contract import BASE, CONTRACT, DEST, load_bundle, sha, require

OUT = BASE/'playback-stage/Data/scientist-presentation.json'
require(not OUT.exists(),'Preserve staged data; choose an explicit new iteration before regenerating')
bundle = load_bundle()


def packed(t):
    return t['translation_cm']+t['rotation_xyzw']+t['scale']


tracks = {}
for item in bundle['clips']:
    short = Path(item['source_fbx']).stem.removeprefix('A_Scientist_').removesuffix('_Cm')
    if short not in ('Full','SortLeft','SortRight','SkipRecover','WorkHold','Holster','Unholster'):
        continue
    tracks[short] = {'asset':item['asset'],'seconds':item['seconds'],'frames':[]}
    for frame,row in item['published'].items():
        tracks[short]['frames'].append({'time':(frame-item['frames'][0])/30,
            'props':{name:packed(t) for name,t in row.get('props',{}).items()},
            'rifle':packed(row['rifle_body_relative']) if 'rifle_body_relative' in row else None})
props = []
for item in bundle['props']:
    row = bundle['dense']['props'][item['asset']]
    name = row['pivot']
    props.append({'name':name,'asset':item['asset'],'initial':packed(row['body_relative_transform']),
                  'sample_index':int(name.rsplit('_',1)[1])-1 if name.startswith('AnonymousSalvageSample_') else -1})
data = {'schema':'oldwest.scientist.presentation.v1','complete_contract_sha256':sha(CONTRACT),
        'fps':30,'authoring_bones':53,'native_bones':54,'tracks':tracks,'props':props,
        'rifle_asset':bundle['holster']['rifle_asset'],'rifle_parked':tracks['Holster']['frames'][-1]['rifle'],
        'selected_sample_recovery':'Freeze every sample transform at the actual selected branch endpoint; recover only body/scanner/lid.'}
require(len(props) == 11 and len(tracks) == 7,'Incomplete runtime bundle')
OUT.parent.mkdir(parents=True,exist_ok=True)
OUT.write_text(json.dumps(data,separators=(',',':'))+'\n')
print(json.dumps({'staged':str(OUT),'sha256':sha(OUT),'tracks':7,'props':11,'frames':sum(len(t['frames']) for t in tracks.values()),'live_content_changed':False}))
