#!/usr/bin/env python3
"""Real native Raider context menus and animated punk-yard recruitment.
Setup uses legal commands; interaction checks use actual mouse events.
"""
import argparse,copy,hashlib,json,time
from pathlib import Path
from test_unreal_field_play import FieldPlayScenario
from test_unreal_interactions import EDITOR,center,resolution,write_json,field_cards
from native_launch import create_native_run_directory,stop_owned_process_groups,game_net_driver_ports
from native_runtime_checks import assert_runtime_assets

class ShelterScenario(FieldPlayScenario):
    def boot(self):
        self.launch('b',f'/Game/Maps/WaterDepotV2?listen?Match=1?game=/Script/OldWestGame.OldWestGameMode?Ruleset={self.args.ruleset}')
        log=self.folder/'b.log'
        self.wait('listen server',lambda:log.exists() and self.port in game_net_driver_ports(log.read_text(errors='replace')),120)
        self.launch('a','/Game/Maps/WaterDepotV2',rendered=True)
        self.wait('menu',lambda:self.snapshot().get('hosted') is False and self.hud(),120)
        self.command('a','join',address=f'127.0.0.1:{self.port}');self.wait('two peers',self.agree,100)
        self.submit('a',next(a for a in self.snapshot()['actions'] if a['command']['camps']==['stockyards','wagon_fort','coal_yard']))
        self.submit('b',max(self.snapshot('b')['actions'],key=lambda a:sum(self.defs[c]['starting_cards'] for c in a['command']['camps'])))
        self.wait('match starts',lambda:self.snapshot()['view']['status']=='actions');self.own_turn()
        self.camps={c['card_id']:c['id'] for c in field_cards(self.snapshot()) if c['owner']==self.snapshot()['seat'] and c['type']=='camp'}
        self.hand(False)
        self.wait('punk yard appears',lambda:self.hud().get('punk_shelter'))

    def own_turn(self):
        self.clear_choices()
        if self.snapshot()['view']['active_player']!=self.snapshot()['seat']:
            action=self.wait('opponent turn actions replicated',lambda:next((a for a in self.snapshot('b')['actions'] if a['command']['type']=='end_turn'),None))
            self.submit('b',action)
        self.clear_choices();self.settle_presentation()

    def shelter(self):return self.hud()['punk_shelter']
    def ready(self,count):
        def check():
            state=self.shelter()
            for punk in state['crew']:
                if punk['phase'] in ('exiting_gate','exiting_pad','waiting'):
                    motion=punk['motion']
                    assert motion['travel_waypoint_count']==2, 'Recruit detoured through battlefield routing'
                    assert motion['travel_length_cm']<1100, 'Recruit took a long detour from the pen'
            return state['available']==count and len([p for p in state['crew'] if p['phase']=='waiting'])==count and state
        return self.wait(f'{count} punks await placement',check)
    def token_point(self,token):
        return self.wait('ready punk name label',lambda:next((x['screen'] for x in self.hud()['battlefield_labels'] if x['id']==token),None))
    def activate(self,key):
        source=self.camps[key]
        self.click(next(b['screen'] for b in self.hud()['battlefield_labels'] if b['id']==source))
        self.field_action(next(a for a in self.snapshot()['actions'] if a['command'].get('source')==source))
    def skip_punk(self):
        a=next(a for a in self.snapshot()['actions'] if a['command']['type']=='choose' and a['label'].lower()=='skip')
        self.field_action(a)
    def test_shelter(self):
        before=copy.deepcopy(self.snapshot()['view']);a=copy.deepcopy(self.shelter());time.sleep(2.5);b=self.shelter()
        assert len(b['crew'])==6 and b['available']==0 and all(not p['can_drag'] for p in b['crew'])
        assert any(x['world']!=y['world'] or x['trips']!=y['trips'] for x,y in zip(a['crew'],b['crew']))
        assert self.snapshot()['view']==before
        self.wait('resident practices on the punching bag',lambda:any(p.get('motion',{}).get('active_clip')=='MM_Attack_01' for p in self.shelter()['crew']))
        resident=self.shelter()['crew'][3]
        self.event('move',resident['screen']);self.event('down',resident['screen']);self.event('move',(resident['screen'][0]+18,resident['screen'][1]-12));self.event('up')
        assert self.hud()['deployment']['card']==-1 and self.snapshot()['view']==before
        assert all(c['id']>=0 for c in field_cards(self.snapshot()))
        self.capture('01-yard-crew-at-work')
        self.checked('Six animated yard residents are decorative until a legal punk placement exists')
        if self.snapshot()['view']['players'][self.snapshot()['seat']]['water']<3:self.round()
        self.activate('wagon_fort');state=self.ready(3)
        assert abs(state['gate_angle'])>80 and all(a.get('punk_remaining')==3 for a in self.snapshot()['actions'] if a.get('placement',{}).get('punk'))
        labels=[x for x in self.hud()['battlefield_labels'] if -1006<x['id']<=-1000]
        assert len(labels)==3
        for i,a in enumerate(labels):
            for b in labels[i+1:]:
                x,y=a['rect'],b['rect']
                assert x[2]<=y[0] or y[2]<=x[0] or x[3]<=y[1] or y[3]<=x[1], 'Recruit labels overlap'
        self.capture('02-three-punks-outside-gate')
        self.checked('Wagon Fort opens the gate and sends three punks out for its three placements')
        token=next(p['token'] for p in state['crew'] if p['can_drag']);before=copy.deepcopy(self.snapshot()['view'])
        self.start(token,self.token_point(token));self.cancel('Cancelling a recruited punk spends nothing and preserves the pending choice',escape=True)
        self.wait('cancelled punk returns through gate',lambda:self.shelter()['returns']>state['returns'])
        self.capture('03-cancelled-punk-returning')
        assert self.snapshot()['view']==before
        state=self.ready(3);token=next(p['token'] for p in state['crew'] if p['can_drag'])
        d=self.start(token,next(p['screen'] for p in state['crew'] if p['token']==token))
        target=next(t for t in d['targets'] if t['column']==0 and t['row']==1)
        self.event('move',target['screen']);self.wait('punk has a legal landing',lambda:self.hud()['deployment']['hovered']>=0)
        self.capture('04-drag-yard-punk-to-lane')
        carried=next(p for p in self.shelter()['crew'] if p['token']==token)
        assert all(abs(carried['world'][i]-target['world'][i])<2 for i in (0,1)), 'The 3D punk did not follow the chosen landing'

        old=copy.deepcopy(self.snapshot());self.event('up',target['screen'])
        self.wait('one authoritative punk placement',lambda:self.agree() and self.snapshot()['view']['revision']==old['view']['revision']+1)
        self.settle_presentation();state=self.ready(2)
        ids={c['id'] for c in field_cards(old)};added=[c for c in field_cards(self.snapshot()) if c['id'] not in ids]
        assert len(added)==1 and added[0]['punk'] and state['consumed']==1
        assert self.snapshot()['view']['players'][self.snapshot()['seat']]['water']==old['view']['players'][old['seat']]['water']
        self.capture('05-punk-placed-two-awaiting')
        self.checked('Dragging a waiting yard punk commits the chosen lane and row once, leaving two recruits')
        self.skip_punk();self.skip_punk()
        self.wait('unused recruits return and gate closes',lambda:self.shelter()['available']==0 and
                  all(p['phase']=='home' for p in self.shelter()['crew']) and abs(self.shelter()['gate_angle'])<1)
        self.capture('06-unused-punks-home-gate-closed')
        self.checked('Skipping remaining placements sends unused punks home and closes the gate')
        self.round();self.activate('stockyards');state=self.ready(1)
        token=next(p['token'] for p in state['crew'] if p['can_drag'])
        self.start(token,self.token_point(token));before=copy.deepcopy(self.snapshot()['view']);self.event('up',(10,10))
        self.wait('invalid drop cancels',lambda:self.hud()['deployment']['card']==-1)
        assert self.snapshot()['view']==before
        self.skip_punk()
        self.wait('single recruit returns',lambda:self.shelter()['available']==0 and all(p['phase']=='home' for p in self.shelter()['crew']))
        self.checked('A single-punk effect also recruits from the yard; invalid drops and Skip return it safely')

    def test_raid_junk_menu(self):
        self.own_turn()
        action=self.seek(lambda a,s:a['command']['type']=='junk' and self.junk_kind(self.own_hand().get(a['command'].get('card'),{}))=='raid','raid junk card',max_actions=70)
        card=action['command']['card']
        # Launch at position three to leave a real forward move available.
        self.round()
        for _ in range(4):
            if not any(c and c.get('card_id')=='stampede' for c in self.snapshot()['view']['players'][self.snapshot()['seat']]['queue']):break
            self.round()
        self.activate('coal_yard');self.clear_choices();self.settle_presentation()
        raider=next(c for c in self.snapshot()['view']['players'][self.snapshot()['seat']]['queue'] if c and c.get('card_id')=='stampede')
        self.hand(False)
        point=next(b['screen'] for b in self.hud()['battlefield_labels'] if b['id']==raider['id'])
        self.event('move',point);self.event('down',point,button='right');self.event('up',point,button='right')
        self.wait('Raider menu includes raid junk',lambda:any(a['command']==action['command'] for a in self.hud()['context_actions']))
        entry=self.wait('actual junk menu row',lambda:next((e for e in self.hud()['context_entries'] if e['id']==action['label'] and e['allocated_size'][0]>1 and e['allocated_size'][1]>1 and e['max'][0]>e['min'][0]),None))
        self.capture('07-raider-menu-with-free-junk')
        old=copy.deepcopy(self.snapshot());q=old['view']['players'][old['seat']]['queue'];slot=next(i for i,c in enumerate(q) if c and c['id']==raider['id'])
        self.click(center(entry))
        self.wait('menu junk applies exactly once',lambda:self.agree() and self.snapshot()['view']['revision']==old['view']['revision']+1)
        after=self.snapshot();assert card not in self.own_hand()
        assert after['view']['players'][after['seat']]['water']==old['view']['players'][old['seat']]['water']
        if slot>0:assert after['view']['players'][after['seat']]['queue'][slot-1]['id']==raider['id']
        self.settle_presentation();self.capture('08-raider-advanced-by-junk')
        self.checked('Right-clicking Stampede offers and executes the hand-card raid junk for zero water')

    def run(self):
        try:
            self.boot();self.test_shelter();self.test_raid_junk_menu()
            result=dict(ok=True,package_directory=str(self.runtime.package_root) if self.runtime.package_root else None,checks=self.checks,screenshots=self.captures,shelter=self.shelter(),runtime_assets=assert_runtime_assets([self.folder/'a.log',self.folder/'b.log']))
            if self.runtime.package_root:
                binary=self.runtime.package_root/'OldWest/Binaries/Linux/OldWestGame';result['build']={'executable':{'path':str(binary),'sha256':hashlib.sha256(binary.read_bytes()).hexdigest()}}
            write_json(self.folder/'result.json',result);return result
        except Exception as error:
            try:self.capture('failure')
            except Exception:pass
            write_json(self.folder/'result.json',dict(ok=False,error=str(error),checks=self.checks,last_reports=self.reports));raise
        finally:
            stop_owned_process_groups(list(self.processes.values()))
            for stream in self.streams:stream.close()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--editor',type=Path,default=EDITOR);p.add_argument('--package-dir',type=Path)
    p.add_argument('--resolutions',nargs='+',type=resolution,default=[(1280,720),(1920,1080)])
    p.add_argument('--ruleset',default='boomtown');p.add_argument('--seed',type=int,default=9)
    p.add_argument('--port',type=int,default=20561);p.add_argument('--timeout',type=float,default=600)
    p.add_argument('--settle',type=float,default=.3);p.add_argument('--max-setup-actions',type=int,default=240);p.add_argument('--output',type=Path)
    args=p.parse_args();out=args.output or create_native_run_directory('oldwest-punk-yard-');out.mkdir(parents=True,exist_ok=True);result=dict(ok=False,results=[])
    try:
        for i,size in enumerate(args.resolutions):result['results'].append(ShelterScenario(args,out,size,i).run())
        result['ok']=True
    finally:write_json(out/'result.json',result)
if __name__=='__main__':main()
