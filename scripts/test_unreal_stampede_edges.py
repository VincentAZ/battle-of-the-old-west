#!/usr/bin/env python3
"""Replay legal public-command journals for Stampede's uncommon lifecycles."""
import argparse,hashlib,json,time
from pathlib import Path
from test_unreal_stampede import StampedeScenario
from test_unreal_interactions import EDITOR,write_json
from native_launch import game_net_driver_ports,stop_owned_process_groups
from native_runtime_checks import assert_runtime_assets

class EdgeScenario(StampedeScenario):
    def vehicle(self,identity):
        return next((u for u in self.read().get('cinematic',{}).get('units',[]) if u['id']==identity),None)
    def run(self):
        plan=json.loads(self.args.manifest.read_text());identity=plan.get('identity');motions=[]
        try:
            self.launch('b',f'/Game/Maps/WaterDepotV2?listen?Match=1?game=/Script/OldWestGame.OldWestGameMode?Ruleset={self.args.ruleset}')
            log=self.folder/'b.log'
            self.wait('listen server',lambda:log.exists() and self.port in game_net_driver_ports(log.read_text(errors='replace')),120)
            self.launch('a','/Game/Maps/WaterDepotV2',rendered=True)
            self.wait('menu',lambda:self.snapshot().get('hosted') is False and self.hud(),120)
            self.command('a','join',address=f'127.0.0.1:{self.port}');self.wait('selection',self.agree,100)
            prior_position=None;prior_travel=None;resolutions=0
            for index,row in enumerate(plan['journal']):
                peer=next(n for n in ('a','b') if self.snapshot(n)['seat']==row['seat']);s=self.snapshot(peer)
                assert s['view']['revision']==row['revision']
                assert hashlib.sha256(json.dumps(s['actions'],sort_keys=True).encode()).hexdigest()==row['legal_actions_sha256']
                action=next(a for a in s['actions'] if a['command']==row['command'])
                previous=self.vehicle(identity) if identity else None
                if previous:prior_position=previous['location'];prior_travel=previous['stampede']['travel_cm']
                self.submit(peer,action)
                events=row['events']
                launch=next((e for e in events if e['type']=='raid_launch'),None)
                resolve=next((e for e in events if e['type']=='event_resolve' and e['detail']=='Stampede'),None)
                move=next((e for e in events if e['type']=='event_advance' and e['source']==identity),None)
                if launch:
                    identity=launch['target'];self.observe(identity,'launch');self.validate(identity)
                elif resolve:
                    identity=resolve['source'];resolutions+=1
                    self.wait('immediate approach completes',lambda:not self.read()['cinematic']['busy'],40)
                    self.validate(identity)
                    assert self.snapshot()['view']['choice'] and all(not c or c['id']!=identity for p in self.snapshot()['view']['players'] for c in p['queue'])
                    pos=self.vehicle(identity)['location'];time.sleep(.35);assert self.vehicle(identity)['location']==pos
                    self.capture(f'immediate-wait-{resolutions}')
                elif move:
                    self.observe(identity,'backward-delay');self.validate(identity);motions.append(move)
                    assert move['from_slot']<move['to_slot']
                    self.capture('backward-delay-complete')
                elif any(e['type'] in ('damage','destroy') and e['source']==identity for e in events):
                    if resolutions>1:
                        self.settle_presentation();self.checked('Reused immediate Stampede can be skipped and is cleaned up')
                    else:self.observe(identity,'authoritative-charge')
                    assert self.vehicle(identity) is None
                else:self.settle_presentation()
            if plan['kind']=='blocked':
                current=self.vehicle(identity);assert current and current['location']==prior_position
                assert current['stampede']['travel_cm']==prior_travel and not current['stampede']['running']
                self.capture('blocked-delay-remains-idle');self.checked('Blocked delay leaves the herd at its authoritative queue location')
            elif plan['kind']=='backward':
                assert motions;self.checked('Legal Pinkerton Agent delay moves the herd backward with reversed in-place running')
            else:
                assert resolutions==2;self.checked('Zeto/Gas Station immediate resolution, covered defender choice, removal and same-ID reuse')
            result=dict(ok=True,kind=plan['kind'],checks=self.checks,screenshots=self.captures,evidence=self.evidence,runtime_assets=assert_runtime_assets([self.folder/'a.log',self.folder/'b.log']))
            write_json(self.folder/'result.json',result);return result
        except Exception as e:
            write_json(self.folder/'result.json',dict(ok=False,error=str(e),last=self.read(),checks=self.checks));raise
        finally:
            stop_owned_process_groups(list(self.processes.values()))
            for stream in self.streams:stream.close()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--editor',type=Path,default=EDITOR);p.add_argument('--package-dir',type=Path);p.add_argument('--output',type=Path,required=True);p.add_argument('--plans',type=Path,required=True)
    p.add_argument('--port',type=int,default=20379);p.add_argument('--timeout',type=float,default=600);p.add_argument('--settle',type=float,default=.3)
    p.add_argument('--kinds',nargs='+',choices=['backward','blocked','immediate'],default=['backward','blocked','immediate'])
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True);results=[]
    for index,kind in enumerate(a.kinds):
        a.manifest=a.plans/f'{kind}-plan.json';plan=json.loads(a.manifest.read_text());a.seed=plan['seed'];a.ruleset=plan['ruleset'];out=a.output/kind;out.mkdir();results.append(EdgeScenario(a,out,(1280,720),index).run())
    write_json(a.output/'result.json',dict(ok=all(r['ok'] for r in results),results=results))
