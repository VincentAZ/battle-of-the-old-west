"""Legal Bounty Office rehearsal: covered targets, decline/accept and punk gate."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bridge', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    assert not args.output.exists()
    process = subprocess.Popen([str(args.bridge.resolve()), str(ROOT/'game/data/cards.json'), '11'],
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    journal, checkpoints = [], {}
    try:
        state = json.loads(process.stdout.readline())['public_snapshots']

        def apply(seat, predicate, purpose):
            nonlocal state
            action = next(a for a in state[seat]['actions'] if predicate(a))
            before = state
            last = max((e['sequence'] for e in before[seat]['view']['log']), default=-1)
            process.stdin.write(json.dumps(dict(seat=seat, command=action['command']))+'\n')
            process.stdin.flush()
            reply = json.loads(process.stdout.readline())
            assert reply['accepted']['ok']
            state = reply['public_snapshots']
            journal.append(dict(seat=seat, revision=before[seat]['view']['revision'],
                command=action['command'], public_label=action['label'], purpose=purpose,
                legal_actions_sha256=hashlib.sha256(json.dumps(before[seat]['actions'],sort_keys=True).encode()).hexdigest(),
                public_events=[e for e in state[seat]['view']['log'] if e['sequence'] > last]))

        def board(owner):
            return [c for col in state[0]['view']['players'][owner]['columns'] for c in col]

        def end(seat):
            apply(seat, lambda a:a['command']['type']=='end_turn', 'Ordinary turn handover')

        apply(0, lambda a:'bounty_office' in a['command'].get('camps', []), 'Select offered Bounty Office')
        apply(1, lambda a:a['command'].get('camps')==['railroad_depot','bare_knuckle_ring','army_surgeon_s_tent'], 'Select offered opposing holdings')
        opening = state
        holding = next(c['id'] for c in board(0) if c.get('card_id')=='bounty_office')
        victim = next(c['id'] for c in board(1) if c.get('card_id')=='army_surgeon_s_tent')
        activate = lambda a:a['command']==dict(type='activate', source=holding, ability=0)
        end(0)
        apply(1, lambda a:a.get('category')=='play_person' and 'Blacksmith' in a['label']
              and a['command'].get('column')==2, 'Deploy an ordinary person in front of the target holding')
        guard = next(c['id'] for c in board(1) if c.get('card_id')=='blacksmith')
        if any(a['label']=='Skip' for a in state[1]['actions']):
            apply(1,lambda a:a['label']=='Skip','Decline an optional entry effect')
        end(1)
        for index, choice in enumerate(('decline','accept')):
            assert any(activate(a) for a in state[0]['actions'])
            before = state
            checkpoints[choice+'_before'] = state
            apply(0, activate, 'Pay two for Bounty Office; opponent has no punks')
            assert state[0]['view']['players'][0]['water']==before[0]['view']['players'][0]['water']-2
            assert any(a.get('target')==victim for a in state[0]['actions']), 'Covered holding was not offered'
            checkpoints[choice+'_target_choice'] = state
            apply(0, lambda a:a.get('target')==victim, 'Choose the covered enemy holding')
            target = next(c for c in board(1) if c['id']==victim)
            assert target['damage']==index+1 and target['destroyed']==bool(index)
            assert next(c for c in board(1) if c['id']==guard)['damage']==0
            checkpoints[choice+'_recruit_choice'] = state
            if choice=='decline':
                apply(1, lambda a:a['label']=='Skip', 'Opponent declines the optional punk')
                assert not any(c.get('punk') or c.get('card_id')=='punk' for c in board(1))
            else:
                old_ids = {c['id'] for c in board(1)}
                apply(1, lambda a:a.get('placement',{}).get('punk') and a['placement']['column']==0,
                      'Opponent accepts the optional punk into an offered position')
                new = [c for c in board(1) if c['id'] not in old_ids]
                assert len(new)==1 and new[0].get('punk'), new
                punk = new[0]['id']
            checkpoints[choice+'_after'] = state
            end(0); end(1)
        assert not any(activate(a) for a in state[0]['actions']), 'Opponent punk failed to block next-turn activation'
        assert state[0]['view']['players'][0]['water']>=2, 'Insufficient resources would confound the punk gate'
        checkpoints['gated_next_turn'] = state
        assert all('hand' not in s['view']['players'][1-s['seat']] for s in state)
        process.stdin.close(); assert process.wait(timeout=5)==0
        files = [Path(__file__),ROOT/'scripts/oldwest_public_costume_bridge.cpp',ROOT/'game/data/cards.json',
                 ROOT/'game/OldWest/Source/OldWestGame/Private/Core/OldWestRules.cpp',
                 ROOT/'game/OldWest/Source/OldWestGame/Private/Core/OldWestRules.h']
        report = dict(ok=True,seed=11,ruleset='boomtown',journal=journal,queue_moves=[],
            opening=opening,own_opening_hands=[dict(seat=i,own_hand=opening[i]['view']['players'][i]['hand']) for i in (0,1)],
            holding=holding,victim=victim,guard=guard,punk=punk,checkpoints=checkpoints,
            provenance={str(p.relative_to(ROOT)):sha(p) for p in files},bridge_sha256=sha(args.bridge),
            scope='Public offered-command rehearsal only. Native visuals, History, privacy and terrain require separate review.')
        args.output.write_text(json.dumps(report,indent=2)+'\n')
        print('BOUNTY_OFFICE_LEGAL_PLAN_PASSED',len(journal),flush=True)
    finally:
        if process.poll() is None:
            process.terminate(); process.wait(timeout=5)


if __name__=='__main__':
    main()
