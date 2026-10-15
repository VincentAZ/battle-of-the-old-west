#!/usr/bin/env python3
"""Real Linux Slate tests for damage, two-turn history and persisted accordions."""
import argparse
import copy
import time
from pathlib import Path
from test_unreal_master_panel import MasterScenario
from test_unreal_interactions import EDITOR, center, resolution, write_json, field_cards
from native_launch import create_native_run_directory, stop_owned_process_groups, game_net_driver_ports
from native_runtime_checks import assert_runtime_assets

class JournalScenario(MasterScenario):
    def boot(self):
        self.launch('b',f'/Game/Maps/WaterDepotV2?listen?Match=1?game=/Script/OldWestGame.OldWestGameMode?Ruleset={self.args.ruleset}')
        log=self.folder/'b.log'
        self.wait('listen server',lambda:log.exists() and self.port in game_net_driver_ports(log.read_text(errors='replace')),120)
        self.launch('a','/Game/Maps/WaterDepotV2',rendered=True)
        self.wait('rendered menu',lambda:self.snapshot().get('hosted') is False and self.hud(),120)
        self.command('a','join',address=f'127.0.0.1:{self.port}')
        self.wait('both peers',self.agree,100)
        for name in ('a','b'):
            action=max(self.snapshot(name)['actions'],key=lambda a:sum(self.defs[c]['starting_cards'] for c in a['command']['camps'])+(100 if name=='a' and 'army_fort' in a['command']['camps'] else 0))
            self.submit(name,action)
        self.wait('match begins',lambda:self.snapshot()['view']['status']=='actions')
        self.settle_presentation()

    def tab(self,side):
        entry=self.wait('tab arranged',lambda:next((e for e in self.hud()['master_tabs'] if e['id']==side and e['allocated_size'][0]>1),None))
        self.click(center(entry))
        seat=self.snapshot()['seat'];expected=seat if side=='your' else 1-seat
        prefix=side+'.water'
        self.wait('tab sections arranged',lambda:self.hud()['inspector_side']==expected and not self.hud()['history_open'] and self.section(prefix))
        time.sleep(.3)

    def section(self,key):
        return next((s for s in self.hud().get('battle_sections',[]) if s['id']==key and s['allocated_size'][0]>0),None)

    def fold(self,key,closed):
        # Resizable nested sections own their wheel input. Navigate the outer
        # scrollbar explicitly when locating a section header.
        if self.hud().get('battle_scroll'):
            for _ in range(30):
                entry=self.section(key);outer=self.hud()['battle_scroll'][0]
                if entry and self.inside(entry) and (key=='your.actions' or self.inside(entry,outer)):break
                self.event('wheel',(outer['max'][0]-4,center(outer)[1]),wheel=3 if entry and entry['min'][1]<outer['min'][1] else -3)
                time.sleep(.15)
            assert entry and self.inside(entry),f'{key} not reachable'
            if entry['collapsed']!=closed:
                self.click(center(entry));self.wait('section '+key,lambda:self.section(key) and self.section(key)['collapsed']==closed)
            time.sleep(.2)
            return
        def reachable():
            s=self.section(key)
            return s if s and self.inside(s) else None
        entry=reachable()
        if not entry:
            area=self.panel()['content'];point=center(area)
            for _ in range(25):
                self.event('wheel',point,wheel=-2);time.sleep(.08)
                entry=reachable()
                if entry:break
        assert entry, f'{key} not reachable'
        if entry['collapsed']!=closed:
            generation=self.hud()['layout_generation']
            self.click(center(entry))
            self.wait('section '+key,lambda:self.hud()['layout_generation']>generation and self.section(key) and self.section(key)['collapsed']==closed)
        time.sleep(.2)

    def history_tab(self):
        entry=self.wait('history tab arranged',lambda:next((x for x in self.hud()['master_tabs'] if x['id']=='history' and x['allocated_size'][0]>1),None))
        self.click(center(entry))
        self.wait('history shown',lambda:self.hud()['history_open'] and self.section('history.current'))
        time.sleep(.3)

    def test_preferences(self):
        self.tab('your');before=copy.deepcopy(self.snapshot()['view'])
        for key in ('your.water','your.hand','your.column1','your.column2','your.column3','your.events','your.actions'):
            self.fold(key,True);self.fold(key,False)
        self.fold('your.formation',True);self.fold('your.formation',False)
        self.fold('your.hand',True);self.fold('your.column2',True)
        self.tab('enemy');self.fold('enemy.water',True)
        self.tab('your')
        assert self.section('your.hand')['collapsed'] and not self.section('your.water')['collapsed']
        assert self.snapshot()['view']==before
        self.capture('02-custom-accordions')
        expected_ini=(self.folder/'a.settings.ini').read_text()
        assert 'your.hand=True' in expected_ini and 'enemy.water=True' in expected_ini
        # Fresh process, same isolated profile/settings, ordinary reconnect.
        old=self.processes.pop('a');stop_owned_process_groups([old])
        self.wait('host sees disconnect',lambda:self.snapshot('b').get('connected')==1,30)
        self.reports.pop('a',None)
        for suffix in ('json','control.json'):(self.folder/f'a.{suffix}').unlink(missing_ok=True)
        self.launch('a','/Game/Maps/WaterDepotV2',rendered=True)
        self.wait('fresh menu',lambda:self.snapshot().get('hosted') is False and self.hud(),120)
        self.command('a','join',address=f'127.0.0.1:{self.port}')
        self.wait('fresh reconnect',self.agree,100);self.settle_presentation();self.tab('your')
        assert self.section('your.hand')['collapsed'] and self.section('your.column2')['collapsed']
        assert self.snapshot()['view']==before
        self.tab('enemy');assert self.section('enemy.water')['collapsed']
        self.tab('your');self.fold('your.hand',False);self.fold('your.column2',False)
        self.capture('03-prefs-after-process-restart')
        self.checked('Eight accordion controls change layout only; independent YOUR/ENEMY preferences survive a fresh process and reconnect')

    def clear_choices(self):
        for _ in range(30):
            if self.snapshot()['view']['choice'] is None:return
            actor=next(n for n in ('a','b') if self.snapshot(n).get('actions'))
            options=self.snapshot(actor)['actions']
            self.submit(actor,next((a for a in options if a['label']=='Skip'),options[0]))
        raise AssertionError('Choices did not settle')

    def test_damage(self):
        own=self.snapshot()['seat']
        cannon=next(c for c in field_cards(self.snapshot()) if c.get('card_id')=='army_fort' and c['owner']==own)
        assert cannon['damage']==1
        soldier=self.seek(lambda a,s:a['command']['type']=='play' and self.own_hand().get(a['command'].get('card'),{}).get('card_id')=='civil_war_veteran','Civil War Veteran',max_actions=100)
        person=soldier['command']['card'];self.submit('a',soldier);self.clear_choices();self.settle_presentation();self.tab('your')
        self.wait('damage markers',lambda:{cannon['id'],person}.issubset({m['id'] for m in self.hud()['damage_markers']}))
        damaged=[c for c in field_cards(self.snapshot()) if c['damage']==1 and not c['destroyed']]
        self.evidence['damaged_cards']=damaged;self.capture('04-damaged-camp-and-person')
        self.click(center(self.panel()['collapse_button']));self.wait('panel collapsed',lambda:self.panel()['collapsed']);self.capture('05-world-damage-markers')
        self.click(center(self.panel()['collapse_button']));self.wait('panel expanded',lambda:not self.panel()['collapsed'])
        for target in (cannon['id'],person):
            junk=self.seek(lambda a,s:a['command']['type']=='junk' and self.junk_kind(self.own_hand().get(a['command'].get('card'),{}))=='restore','restoration junk',max_actions=100)
            self.submit('a',junk)
            entry=next(a for a in self.snapshot()['actions'] if any(c['id']==target and c['name'] in a['label'] for c in field_cards(self.snapshot())))
            self.submit('a',entry);self.settle_presentation()
            assert next(c for c in field_cards(self.snapshot()) if c['id']==target)['damage']==0
            self.wait('restored marker removed',lambda:target not in {m['id'] for m in self.hud()['damage_markers']})
            if target==person:assert not next(c for c in field_cards(self.snapshot()) if c['id']==person)['ready']
        self.capture('06-restored-markers-cleared')
        self.checked('Damaged camp and person both have world markers; restoration clears each marker and leaves an ordinarily restored person unready')

    def test_long_turn(self):
        for _ in range(5):
            options=self.snapshot()['actions']
            if any(a['command']['type']=='silo' for a in options):break
            if options:
                silo=next((a for a in options if a['command']['type']=='junk' and self.own_hand().get(a['command'].get('card'),{}).get('card_id')=='hip_flask'),None)
                if silo:self.submit('a',silo);continue
            actor=next(n for n in ('a','b') if self.snapshot(n).get('actions'))
            self.submit(actor,next(a for a in self.snapshot(actor)['actions'] if a['command']['type']=='end_turn'))
        turn=self.snapshot()['view']['turn']
        first=copy.deepcopy(self.snapshot()['view']['history'])
        for i in range(40):
            if i==20:
                self.command('b','packet_loss',percent=5)
                self.wait('packet loss active',lambda:any(p.get('simulated_outgoing_loss')==5 and p.get('simulated_incoming_loss')==5 for p in self.read('b').get('network',{}).get('peers',[])))
                self.evidence['transport_packet_loss_percent']=5
            self.submit('a',next(a for a in self.snapshot()['actions'] if a['command']['type']=='silo'))
            self.submit('a',next(a for a in self.snapshot()['actions'] if a['command']['type']=='junk' and self.own_hand().get(a['command'].get('card'),{}).get('card_id')=='hip_flask'))
            if i%10==9:self.settle_presentation()
        self.command('b','packet_loss',percent=0)
        h=self.snapshot()['view']['history']
        assert len(h)>240 and h==self.snapshot('b')['view']['history']
        assert self.snapshot()['view']['turn']==turn
        assert all(e in h for e in first)
        self.evidence['long_turn_entries']=len(h)
        self.evidence['long_snapshot_bytes']=len(__import__('json').dumps(self.snapshot()).encode())
        self.checked('A 40-pair legal Silo stress turn keeps over 240 history entries synchronized across the real network connection, including 5% simulated packet loss')

    def test_history(self):
        self.clear_choices();self.settle_presentation()
        self.history_tab();before=copy.deepcopy(self.snapshot()['view'])
        self.fold('history.current',True)
        if self.section('history.last'):self.fold('history.last',False)
        self.capture('07-last-turn-history')
        self.fold('history.current',False)
        assert self.snapshot()['view']==before
        self.capture('08-current-turn-history')
        actor=next(n for n in ('a','b') if self.snapshot(n).get('actions'))
        self.submit(actor,next(a for a in self.snapshot(actor)['actions'] if a['command']['type']=='end_turn'))
        self.clear_choices();self.settle_presentation()
        v=self.snapshot()['view'];h=v['history'];turn=v['turn']
        assert h==self.snapshot('b')['view']['history']
        assert {e['turn'] for e in h}=={turn,turn-1}
        assert [e['sequence'] for e in h]==sorted(set(e['sequence'] for e in h))
        for e in before['history']:
            if e['turn']==turn-1:assert e in h
        self.evidence['rolling_history']=h
        self.checked('Both peers receive the same ordered current/last-turn history; turning the page preserves the previous turn without older turns')
        # Required choice must remain reachable from History with saved Actions closed.
        action=self.seek_punk('a');self.tab('your');self.fold('your.actions',True);self.history_tab()
        self.submit('a',action);self.settle_presentation()
        self.wait('required response over history',lambda:self.section('your.actions') and self.section('your.actions')['forced_open'])
        assert self.section('your.actions')['collapsed'], 'Required response overwrote the saved preference'
        assert self.hud()['master_actions_visible'] and self.hud()['placement_drag_buttons']
        self.capture('09-required-response-over-history')
        self.clear_choices();self.settle_presentation()
        assert not self.section('your.actions')['forced_open'] and self.section('your.actions')['collapsed']
        self.fold('your.actions',False)
        self.checked('A mandatory response opens over History despite collapsed Actions, then restores the saved collapsed preference')

    def test_result_history(self):
        for i in range(150):
            if self.snapshot()['view']['status'] in ('won','draw'):break
            self.clear_choices()
            actor=next(n for n in ('a','b') if self.snapshot(n).get('actions'))
            self.submit(actor,next(a for a in self.snapshot(actor)['actions'] if a['command']['type']=='end_turn'))
            if i%10==9:self.command('a','skip_cinematics')
        assert self.snapshot()['view']['status'] in ('won','draw')
        self.command('a','skip_cinematics')
        self.wait('result history arranged',lambda:self.hud().get('end_panel',{}).get('visible') and self.section('history.current'))
        assert self.snapshot()['view']['history']==self.snapshot('b')['view']['history']
        assert self.snapshot()['view']['history'][-1]['type'] in ('victory','draw_game')
        self.capture('10-final-result-history')
        self.checked('The final turn journal remains available on the result screen after an actual completed match')

    def run(self):
        try:
            self.boot();self.test_preferences();self.test_damage();self.test_long_turn();self.test_history();self.test_result_history()
            assets=assert_runtime_assets([self.folder/'a.log',self.folder/'b.log'])
            r=dict(ok=True,checks=self.checks,evidence=self.evidence,screenshots=self.captures,runtime_assets=assets)
            write_json(self.folder/'result.json',r);return r
        except Exception as e:
            write_json(self.folder/'result.json',dict(ok=False,failure=str(e),checks=self.checks,evidence=self.evidence,last_reports=self.reports));raise
        finally:
            stop_owned_process_groups(list(self.processes.values()))
            for stream in self.streams:stream.close()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--editor',type=Path,default=EDITOR);p.add_argument('--package-dir',type=Path)
    p.add_argument('--resolutions',nargs='+',type=resolution,default=[(1280,720),(1920,1080)])
    p.add_argument('--ruleset',default='boomtown');p.add_argument('--seed',type=int,default=1)
    p.add_argument('--port',type=int,default=19889);p.add_argument('--timeout',type=float,default=1500)
    p.add_argument('--settle',type=float,default=.4);p.add_argument('--max-setup-actions',type=int,default=240)
    p.add_argument('--output',type=Path)
    args=p.parse_args();out=args.output or create_native_run_directory('oldwest-battle-journal-');out.mkdir(parents=True,exist_ok=True)
    r=dict(ok=False,results=[])
    try:
        for i,size in enumerate(args.resolutions):r['results'].append(JournalScenario(args,out,size,i).run())
        r['ok']=True
    finally:write_json(out/'result.json',r)
if __name__=='__main__':main()
