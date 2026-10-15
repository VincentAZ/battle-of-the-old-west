#!/usr/bin/env python3
"""Verify a physical Looter-to-camp drag using legal setup and native input."""
import argparse
from pathlib import Path
from test_unreal_field_play import FieldPlayScenario
from test_unreal_direct_drags import DirectDragScenario
from test_unreal_interactions import EDITOR, resolution, write_json, field_cards, center
from native_launch import create_native_run_directory, stop_owned_process_groups
from native_runtime_checks import assert_runtime_assets


class DirectAttackScenario(FieldPlayScenario):
    def run(self):
        try:
            DirectDragScenario.boot(self)
            assert not self.hud()["battle_plan_open"]
            for panel_id in ('field_you','field_enemy'):
                panel=next(d for d in self.hud()['dock_panels'] if d['id']==panel_id)
                if not panel['collapsed']:
                    self.click(center(panel['collapse_button']))
                    self.wait('public panel collapsed',lambda:next(d for d in self.hud()['dock_panels'] if d['id']==panel_id)['collapsed'])
            action = self.seek(lambda a, s: a['command']['type']=='play'
                               and self.own_hand().get(a['command'].get('card'), {}).get('card_id')=='claim_jumper',
                               'Claim Jumper in hand', max_actions=self.args.max_setup_actions)
            looter = action['command']['card']
            self.submit('a', action)
            self.clear_choices()
            self.round()
            self.toggle_panel(False)
            current = self.snapshot()
            camps = {c['id'] for c in field_cards(current) if c['type']=='camp' and c['owner']!=current['seat']}
            ability = next(a for a in current['actions'] if a['command'].get('source')==looter)
            gesture = next(g for g in ability['gestures'] if g.get('target') in camps)
            camp = gesture['target']
            camp_point = self.world_point(camp)
            source_point = self.world_point(looter)
            self.start(looter, source_point)
            self.cancel('Cancelling a Claim Jumper attack spends no water and causes no damage')
            deployment = self.start(looter, source_point)
            target = self.drag_target(deployment, 'damage', target_card=camp)
            before, after = self.release(target, camp_point, '02-looter-dropped-on-camp')
            seat = before['seat']
            assert before['view']['players'][seat]['water']-after['view']['players'][seat]['water']==2
            assert len(after['view']['players'][seat]['hand'])==len(before['view']['players'][seat]['hand'])+1
            assert next(c for c in field_cards(after) if c['id']==camp)['damage']==1
            assert not after['view']['choice']
            assert not self.hud()['battle_plan_open']
            self.checked('Physical Looter-to-camp drop damages camp, pays 2 water once, and draws a card without Battle Plan or right-click')
            result = dict(ok=True, checks=self.checks, evidence=self.evidence, screenshots=self.captures,
                          runtime_assets=assert_runtime_assets([self.folder/'a.log', self.folder/'b.log']))
            write_json(self.folder/'result.json', result)
            return result
        except Exception as error:
            try:self.capture('failure')
            except Exception:pass
            write_json(self.folder/'result.json', dict(ok=False,error=str(error),checks=self.checks,evidence=self.evidence))
            raise
        finally:
            stop_owned_process_groups(list(self.processes.values()))
            for stream in self.streams:stream.close()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--editor',type=Path,default=EDITOR);p.add_argument('--package-dir',type=Path)
    p.add_argument('--resolutions',nargs='+',type=resolution,default=[(1920,1080)])
    p.add_argument('--ruleset',default='base_2024');p.add_argument('--seed',type=int,default=94)
    p.add_argument('--port',type=int,default=20761);p.add_argument('--timeout',type=float,default=900)
    p.add_argument('--settle',type=float,default=.3);p.add_argument('--max-setup-actions',type=int,default=240)
    p.add_argument('--output',type=Path)
    args=p.parse_args();out=args.output or create_native_run_directory('oldwest-direct-attacks-')
    out.mkdir(parents=True,exist_ok=True)
    for i,size in enumerate(args.resolutions):DirectAttackScenario(args,out,size,i).run()


if __name__=='__main__':main()
