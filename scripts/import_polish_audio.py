"""Import/reimport the authored polish cues in Unreal; -AudioVerifyOnly reads.

Run in an Unreal Python commandlet. Existing base sounds are not modified.
"""
import hashlib
import json
from pathlib import Path

import unreal

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / 'art/audio'
SPEC = json.loads((ART / 'audio-manifest.json').read_text())
VERIFY = '-AudioVerifyOnly' in unreal.SystemLibrary.get_command_line()
LIB = unreal.EditorAssetLibrary
report = {'fresh_reload': VERIFY, 'assets': {}, 'listening_reviewed': False}
selected = {name: spec for name, spec in SPEC['assets'].items()
            if spec.get('generator') == 'scripts/generate_polish_audio.py'}
assert selected, 'Generate the polish sounds first'
for name, spec in selected.items():
    source = ROOT / spec['file']
    assert hashlib.sha256(source.read_bytes()).hexdigest() == spec['sha256']
    if not VERIFY:
        task = unreal.AssetImportTask()
        for key, value in dict(filename=str(source), destination_path='/Game/Audio',
                               destination_name=name, automated=True, save=True,
                               replace_existing=True, factory=unreal.SoundFactory()).items():
            task.set_editor_property(key, value)
        unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
        assert task.get_objects(), f'Import failed: {name}'
    sound = LIB.load_asset(spec['unreal_path'])
    assert isinstance(sound, unreal.SoundWave), name
    if not VERIFY:
        sound.set_editor_property('looping', False)
        sound.set_editor_property('volume', 1.)
        sound.set_editor_property('compression_quality', 100)
        sound.set_editor_property('sound_group', unreal.SoundGroup.SOUNDGROUP_EFFECTS)
        assert LIB.save_loaded_asset(sound, only_if_is_dirty=False)
    duration = float(sound.get_editor_property('duration'))
    assert abs(duration - spec['duration_seconds']) < .002
    assert int(sound.get_editor_property('num_channels')) == 1
    assert int(sound.get_editor_property('imported_sample_rate')) == 48000
    assert not sound.get_editor_property('looping')
    assert abs(float(sound.get_editor_property('volume')) - 1.) < .0001
    report['assets'][name] = dict(path=sound.get_path_name(), duration_seconds=duration,
                                source_sha256=spec['sha256'])
report['ok'] = True
(ART / ('polish-unreal-validation.json' if VERIFY else 'polish-unreal-import.json')).write_text(
    json.dumps(report, indent=2) + '\n')
unreal.log(f'POLISH_AUDIO_VERIFIED {len(selected)} fresh_reload={VERIFY}')
