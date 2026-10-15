"""Replay the verified public setup, then decline the destroyed person's ability."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bridge', type=Path, required=True)
    parser.add_argument('--source', type=Path, default=ROOT/'art/western/holdings/expansion-game-v001/gallows/gameplay-plan-v001.json')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    assert not args.output.exists()
    plan = json.loads(args.source.read_text())
    for path, digest in plan['provenance'].items():
        assert sha(ROOT/path) == digest, path
    assert sha(args.bridge) == plan['bridge_sha256']
    process = subprocess.Popen([str(args.bridge.resolve()), str(ROOT/'game/data/cards.json'), str(plan['seed'])],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    try:
        state = json.loads(process.stdout.readline())['public_snapshots']
        journal = []
        for row in plan['journal']:
            if row['revision'] >= plan['destroyed'][0]['view']['revision']:
                break
            seat = row['seat']
            assert state[seat]['view']['revision'] == row['revision']
            assert hashlib.sha256(json.dumps(state[seat]['actions'], sort_keys=True).encode()).hexdigest() == row['legal_actions_sha256']
            assert any(a['command'] == row['command'] for a in state[seat]['actions'])
            process.stdin.write(json.dumps(dict(seat=seat, command=row['command']))+'\n'); process.stdin.flush()
            reply = json.loads(process.stdout.readline()); assert reply['accepted']['ok']
            state = reply['public_snapshots']; journal.append(copy.deepcopy(row))
        assert state == plan['destroyed']
        seat = state[0]['view']['choice']['player']
        skip = next(a for a in state[seat]['actions'] if a['label'] == 'Skip')
        row = dict(seat=seat, revision=state[seat]['view']['revision'], command=skip['command'],
            purpose='Controller declines the optional free response', public_label=skip['label'],
            legal_actions_sha256=hashlib.sha256(json.dumps(state[seat]['actions'], sort_keys=True).encode()).hexdigest())
        process.stdin.write(json.dumps(dict(seat=seat, command=skip['command']))+'\n'); process.stdin.flush()
        reply = json.loads(process.stdout.readline()); assert reply['accepted']['ok']
        after = reply['public_snapshots']
        last = max(e['sequence'] for e in state[seat]['view']['log'])
        row['public_events'] = [e for e in after[seat]['view']['log'] if e['sequence'] > last]
        assert not row['public_events'], 'Declining unexpectedly emitted a response effect'
        def board_state(value):
            # Ending a choice intentionally recomputes legal-action hints.
            # Preserve every card/resource field while excluding only these
            # two derived availability descriptions from the board comparison.
            if isinstance(value, dict):
                return {k: board_state(v) for k, v in value.items()
                        if k not in ('ability_availability', 'play_availability')}
            if isinstance(value, list):
                return [board_state(v) for v in value]
            return value
        for viewer in (0, 1):
            assert after[viewer]['view']['choice'] is None
            assert board_state(after[viewer]['view']['players']) == board_state(state[viewer]['view']['players'])
            assert 'hand' not in after[viewer]['view']['players'][1-viewer]
        journal.append(row)
        plan.update(journal=journal, after=after, response_events=[], response_variant='decline',
            scope='Legal CPU decline branch: same exposed-target destruction, optional response declined, no response event/payment or board changes, both hands private.')
        plan['provenance'].update({str(Path(__file__).relative_to(ROOT)): sha(Path(__file__)),
                                   str(args.source.resolve().relative_to(ROOT)): sha(args.source)})
        args.output.write_text(json.dumps(plan, indent=2)+'\n')
        print('GALLOWS_DECLINE_REHEARSED', len(journal), flush=True)
    finally:
        process.stdin.close(); process.wait(timeout=5)


if __name__ == '__main__':
    main()
