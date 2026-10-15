#!/usr/bin/env python3
"""Full four-turn history and native camp/person/water action parity, including Mining Camp."""
import argparse, copy, json, time
from pathlib import Path
from test_unreal_immersive_staging import StagingScenario
from test_unreal_interactions import EDITOR, center, field_cards, resolution, write_json
from native_launch import game_net_driver_ports, stop_owned_process_groups
from native_runtime_checks import assert_runtime_assets

class HistoryActionsScenario(StagingScenario):
    def boot(self):
        self.launch('b',f'/Game/Maps/WaterDepotV2?listen?Match=1?game=/Script/OldWestGame.OldWestGameMode?Ruleset={self.args.ruleset}')
        log=self.folder/'b.log'
        self.wait('listen server',lambda:log.exists() and self.port in game_net_driver_ports(log.read_text(errors='replace')),120)
        self.launch('a','/Game/Maps/WaterDepotV2',rendered=True)
        self.wait('native menu',lambda:self.snapshot().get('hosted') is False and self.hud(),120)
        self.command('a','join',address=f'127.0.0.1:{self.port}')
        self.wait('connected peers',self.agree,100)
        chosen=['boarding_house','riverboat','gunsmith']
        self.submit('a',next(a for a in self.snapshot()['actions'] if a['command']['camps']==chosen))
        self.submit('b',self.snapshot('b')['actions'][0])
        self.wait('match starts',lambda:self.snapshot()['view']['status']=='actions')
        self.own_turn()
        seat=self.snapshot()['seat']
        self.camps={c['card_id']:c['id'] for c in field_cards(self.snapshot()) if c['owner']==seat and c['type']=='camp'}
        water=next(b for b in self.hud()['status_buttons'] if b['id']=='water_drag')
        drag=self.start(-3002,center(water))
        paid=[a for a in self.snapshot()['actions'] if a.get('cost',0)>0]
        assert all(any(t['command']==a['command'] for t in drag['targets']) for a in paid)
        self.cancel('Water readout drags to every available paid action without spending on pickup',escape=True)
        # Fold information temporarily to leave every world source accessible.
        for key in ('field_you','field_enemy'):
            p=next(p for p in self.hud()['dock_panels'] if p['id']==key)
            if not p['collapsed']:self.click(center(p['collapse_button']));time.sleep(.4)
    def ability(self,source,index=0):
        return next(a for a in self.snapshot()['actions'] if a['command'].get('source')==source and a['command'].get('ability')==index)
    def parity(self,source):
        before=copy.deepcopy(self.snapshot()['view'])
        point=self.point(source)
        self.event('down',point,button='right');self.event('up',point,button='right');time.sleep(.4)
        advertised=copy.deepcopy(self.hud()['context_actions'])
        self.key('Escape');time.sleep(.3)
        if advertised:
            d=self.start(source,point)
            commands={json.dumps(t['command'],sort_keys=True) for t in d['targets']}
            assert all(json.dumps(a['command'],sort_keys=True) in commands for a in advertised),(source,advertised,d)
            self.cancel('All right-click commands are also available by drag for '+str(source),escape=True)
        assert self.snapshot()['view']==before
    def histories(self):
        before=copy.deepcopy(self.snapshot()['view'])
        for visible in (False,True):
            toggle=next(b for b in self.hud()['camera_buttons'] if b['id']=='battlefield_text')
            self.click(center(toggle))
            self.wait('battlefield text toggles',lambda:self.hud()['battlefield_text_visible']==visible)
            if not visible:assert not self.hud()['battlefield_labels']
            else:assert self.hud()['battlefield_labels']
            self.capture('battlefield-text-on' if visible else 'battlefield-text-off')
        assert self.snapshot()['view']==before
        self.checked('Battlefield text toggles off and back on without changing the match')
        entries=before['history'];turn=before['turn']
        assert {e['turn'] for e in entries}==set(range(turn-3,turn+1))
        # Expand the history panel and verify both complete sort orders.
        p=next(p for p in self.hud()['dock_panels'] if p['id']=='field_enemy')
        if p['collapsed']:self.click(center(p['collapse_button']));time.sleep(.4)
        def click_control(key):
            button=next(b for b in self.hud()['status_buttons'] if b['id']==key)
            self.click(center(button));time.sleep(.3)
        for ascending in (True,False):
            click_control('history_ascending' if ascending else 'history_descending')
            seen=[]
            for selected in range(turn,turn-4,-1):
                expected=sorted([e['sequence'] for e in entries if e['turn']==selected],reverse=not ascending)
                self.wait('selected turn has every entry in order',lambda:self.hud()['history_rendered_sequences']==expected)
                seen.extend(expected)
                if selected>turn-3:click_control('history_older')
            assert sorted(seen)==sorted(e['sequence'] for e in entries)
            click_control('history_newer')
            expected=sorted([e['sequence'] for e in entries if e['turn']==turn-2],reverse=not ascending)
            self.wait('newer turn navigation',lambda:self.hud()['history_rendered_sequences']==expected)
            click_control('history_latest')
            expected=sorted([e['sequence'] for e in entries if e['turn']==turn],reverse=not ascending)
            self.wait('return to latest turn',lambda:self.hud()['history_rendered_sequences']==expected)
            self.capture('history-ascending' if ascending else 'history-descending')
        assert self.snapshot()['view']==before
        self.checked('Older/Newer/Latest preserve every retained entry in both sort orders without changing the match')
    def run(self):
        try:
            self.boot()
            if self.args.history_only:
                self.round();self.round();self.histories()
                panel=next(p for p in self.hud()['dock_panels'] if p['id']=='field_enemy')
                if not panel['collapsed']:self.click(center(panel['collapse_button']));time.sleep(.4)
                seat=self.snapshot()['seat']
                water=self.snapshot()['view']['players'][seat]['water']
                draw=next(a for a in self.snapshot()['actions'] if a['command']['type']=='draw')
                self.perform_drag(-4002,draw,'Two-water bundle pays for a draw')
                assert self.snapshot()['view']['players'][seat]['water']==water-2
                silo=next(a for a in self.snapshot()['actions'] if a['command']['type']=='silo')
                self.perform_drag(-4001,silo,'One water can stores in the silo barrel')
                assert self.snapshot()['view']['players'][seat]['water']==water-3
                assert self.snapshot()['view']['players'][seat]['silo_in_hand']
                result=dict(ok=True,package_directory=str(self.runtime.package_root) if self.runtime.package_root else None,checks=self.checks,screenshots=self.captures,runtime_assets=assert_runtime_assets([self.folder/'a.log',self.folder/'b.log']))
                write_json(self.folder/'result.json',result);return result
            for source in [*self.camps.values(),-3002]:self.parity(source)
            # Water tank initiates Gunsmith, then the camp supplies its spatial choice.
            self.perform_drag(-3002,self.ability(self.camps['gunsmith']),'Water drag activates Gunsmith')
            placement=next(a for a in self.snapshot()['actions'] if a.get('placement',{}).get('punk'))
            self.perform_drag(self.camps['gunsmith'],placement,'Camp drag completes punk placement')
            punk=next(c['id'] for c in field_cards(self.snapshot()) if c.get('punk') and c['owner']==self.snapshot()['seat'])
            for cycle in range(3):
                if cycle:self.round()
                self.perform_drag(self.camps['riverboat'],self.ability(self.camps['riverboat']),f'Camp drag advances Riverboat {cycle+1}')
                self.clear_choices();self.settle_presentation()
            ruin=next(c['id'] for c in field_cards(self.snapshot()) if c['owner']!=self.snapshot()['seat'] and c['type']=='camp' and c.get('destroyed'))
            mining=self.camps['boarding_house']
            self.perform_drag(mining,self.ability(mining),'Boarding House drag starts ruin removal')
            self.perform_drag(mining,next(a for a in self.snapshot()['actions'] if a.get('target')==ruin),'Boarding House drag removes enemy ruin')
            assert ruin not in {c['id'] for c in field_cards(self.snapshot())}
            assert self.snapshot()['view']['choice']['prompt']=='Choose a damage target'
            self.parity(mining)
            damage=next(a for a in self.snapshot()['actions'] if a.get('target'))
            victim=damage['target'];previous=next(c for c in field_cards(self.snapshot()) if c['id']==victim)
            self.capture('mining-damage-choice')
            self.perform_drag(mining,damage,'Boarding House drag applies damage after enemy ruin removal')
            current=next((c for c in field_cards(self.snapshot()) if c['id']==victim),None)
            assert current is None or current.get('damage',0)>previous.get('damage',0) or current.get('destroyed')
            self.checked('Boarding House removes an enemy ruin, offers legal damage choices, and applies the chosen damage')
            self.round();self.parity(punk)
            self.perform_drag(punk,next(a for a in self.snapshot()['actions'] if a['command'].get('source')==punk and a['command']['type']=='activate'),'Person drag initiates granted damage ability')
            self.perform_drag(punk,next(a for a in self.snapshot()['actions'] if a.get('target')),'Person drag completes damage choice')
            self.histories()
            result=dict(ok=True,checks=self.checks,evidence=self.evidence,screenshots=self.captures,runtime_assets=assert_runtime_assets([self.folder/'a.log',self.folder/'b.log']))
            write_json(self.folder/'result.json',result);return result
        except Exception as error:
            write_json(self.folder/'result.json',dict(ok=False,error=str(error),checks=self.checks,last_reports=self.reports));raise
        finally:
            stop_owned_process_groups(list(self.processes.values()))
            for stream in self.streams:stream.close()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--editor',type=Path,default=EDITOR);p.add_argument('--package-dir',type=Path)
    p.add_argument('--resolutions',nargs='+',type=resolution,default=[(1280,720),(1920,1080)])
    p.add_argument('--ruleset',default='boomtown');p.add_argument('--seed',type=int,default=24)
    p.add_argument('--port',type=int,default=21041);p.add_argument('--timeout',type=float,default=600)
    p.add_argument('--settle',type=float,default=.3);p.add_argument('--max-setup-actions',type=int,default=240)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--both-views',action='store_true')
    p.add_argument('--history-only',action='store_true')
    args=p.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    results=[]
    for i,size in enumerate(args.resolutions):results.append(HistoryActionsScenario(args,args.output,size,i).run())
    write_json(args.output/'result.json',dict(ok=True,results=results))
if __name__=='__main__':main()
