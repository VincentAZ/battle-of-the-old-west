#!/usr/bin/env python3
"""Inspect a destroyed camp in a real match reached through legal actions."""
import argparse
from pathlib import Path
import time
from test_unreal_immersive_staging import StagingScenario
from test_unreal_interactions import EDITOR, field_cards, write_json
from native_launch import stop_owned_process_groups
from native_runtime_checks import assert_runtime_assets


def run(args):
    args.output.mkdir(parents=True, exist_ok=True)
    s = StagingScenario(args, args.output, (1920, 1080), 0)
    try:
        s.boot()
        play = s.seek(lambda a, _: a['command']['type'] == 'play' and
                      s.own_hand().get(a['command'].get('card'), {}).get('card_id') == 'barn_burner',
                      'Barn Burner', max_actions=120)
        pyro = play['command']['card']
        s.submit('a', play)
        s.clear_choices()
        s.round()
        target = None
        for hit in range(2):
            attack = next(a for a in s.snapshot()['actions'] if a['command'].get('source') == pyro)
            s.submit('a', attack)
            choices = s.snapshot()['actions']
            choice = next((a for a in choices if a.get('target') == target), choices[0])
            target = choice['target']
            s.submit('a', choice)
            s.clear_choices()
            s.settle_presentation()
            if hit == 0:
                s.close_view(target, '02-damaged-camp', 1400)
                s.round()
        card = next(c for c in field_cards(s.snapshot()) if c['id'] == target)
        assert card['destroyed']
        unit = next(u for u in s.read()['cinematic']['units'] if u['id'] == target)
        assert unit['visible_damage_fire_parts'] == 0
        assert unit['visible_ruin_smoke_parts'] == 18
        # Keep the actual gameplay camera fixed while recording motion.
        reset_camera = s.reset_camera
        s.reset_camera = lambda: None
        s.close_view(target, '03-ruined-camp', 1250)
        samples = []
        frames = []
        frame_times = []
        for frame in range(12):
            time.sleep(.35)
            current = next(u for u in s.read()['cinematic']['units'] if u['id'] == target)
            samples.append(current['ruin_smoke_sample'])
            label = f'smoke-motion-{frame:02d}'
            s.capture(label)
            frame_times.append(time.monotonic())
            frames.append(s.folder/(label+'.png'))
        rising = [(a,b) for a,b in zip(samples,samples[1:]) if b[0] > a[0]]
        assert len(rising) >= 8, samples
        assert all(b[1] > a[1] and b[2] > a[2] for a,b in rising), samples
        # Retain an animation for human review, not just a pixel-change score.
        from PIL import Image
        sequence = [Image.open(path).convert('RGB').crop((480,190,1480,870)) for path in frames]
        animation = s.folder/'rising-smoke.gif'
        durations = [round((b-a)*1000) for a,b in zip(frame_times,frame_times[1:])]
        durations.append(durations[-1])
        sequence[0].save(animation,save_all=True,append_images=sequence[1:],duration=durations,loop=0)
        s.reset_camera = reset_camera
        result = dict(ok=True, camp=card['card_id'], unit=unit,
                      smoke_samples_age_height_width=samples, rising_intervals=len(rising),
                      animation=str(animation), screenshots=s.captures,
                      runtime_assets=assert_runtime_assets([s.folder/'a.log', s.folder/'b.log']))
        write_json(s.folder/'result.json', result)
        print('Battlefield ruin passed:', card['card_id'], flush=True)
    except Exception as error:
        write_json(s.folder/'result.json', dict(ok=False, error=str(error)))
        raise
    finally:
        stop_owned_process_groups(list(s.processes.values()))
        for stream in s.streams:
            stream.close()


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--editor', type=Path, default=EDITOR)
    p.add_argument('--package-dir', type=Path)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--seed', type=int, default=94)
    p.add_argument('--port', type=int, default=20921)
    p.add_argument('--timeout', type=float, default=600)
    p.add_argument('--settle', type=float, default=.3)
    p.set_defaults(ruleset='base_2024', both_views=False)
    run(p.parse_args())
