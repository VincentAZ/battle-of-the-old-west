#!/usr/bin/env python3
"""Compare matching legal launch/advance scenes in two packaged builds."""
import argparse,json,time,statistics
from pathlib import Path
from test_unreal_raiders_vehicle import VehicleScenario
from test_unreal_interactions import EDITOR,write_json
from native_launch import stop_owned_process_groups

class PerformanceScenario(VehicleScenario):
    def launch(self,*a,**kw):
        if '-OldWestPresentationProfile' not in self.runtime.argv:self.runtime.argv.append('-OldWestPresentationProfile')
        return super().launch(*a,**kw)
    def sample(self,identity,kind):
        samples={};end=time.monotonic()+35
        while time.monotonic()<end:
            c=self.read().get('cinematic',{})
            if c.get('kind')==kind:
                for f in c.get('frame_performance',{}).get('samples',[]):
                    if f['elapsed']>.3:samples[f['frame']]=f
            if not c.get('busy',True) and samples:break
            time.sleep(.035)
        assert len(samples)>15,(kind,len(samples))
        return list(samples.values())
    def run(self):
        try:
            self.boot();a=self.find_raid('a');self.settle_presentation();seat=self.snapshot()['seat'];self.submit('a',a)
            identity=next(c['id'] for c in self.snapshot()['view']['players'][seat]['queue'] if c and c['card_id']=='stampede')
            samples={'raid_launch':self.sample(identity,'raid_launch')}
            self.pass_turn('a');self.settle_presentation();self.pass_turn('b');samples['event_advance']=self.sample(identity,'event_advance')
            result=dict(ok=True,package=str(self.runtime.package_root),resolution=self.dimensions,samples=samples)
            write_json(self.folder/'result.json',result);return result
        finally:
            stop_owned_process_groups(list(self.processes.values()))
            for stream in self.streams:stream.close()

def percentile(values,p):
    values=sorted(values);return values[min(len(values)-1,int((len(values)-1)*p))]

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--baseline',type=Path,required=True);p.add_argument('--candidate',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--trials',type=int,default=2)
    a=p.parse_args();a.editor=EDITOR;a.seed=1;a.ruleset='boomtown';a.timeout=600;a.settle=.1;a.extra_render_commands=['t.MaxFPS 0'];a.output.mkdir(parents=True,exist_ok=True);results=[]
    for trial in range(a.trials):
        for index,name in enumerate(('baseline','candidate') if trial%2==0 else ('candidate','baseline')):
            a.package_dir=getattr(a,name);a.port=20551+trial*2+index;out=a.output/f'{name}-{trial}';out.mkdir();r=PerformanceScenario(a,out,(1920,1080),0).run();r.update(name=name,trial=trial);results.append(r)
    comparison=[]
    for kind in ('raid_launch','event_advance'):
        row={'kind':kind}
        for name in ('baseline','candidate'):
            frames=[f for r in results if r['name']==name for f in r['samples'][kind]]
            row[name]={key:dict(median=statistics.median(v),p95=percentile(v,.95)) for key in ('frame_delta_ms','gpu_ms','game_active_ms','render_active_ms') if (v:=[f[key] for f in frames if f.get(key) is not None])};row[name]['frames']=len(frames)
        row['frame_time_change_percent']=100*(row['candidate']['frame_delta_ms']['median']/row['baseline']['frame_delta_ms']['median']-1);comparison.append(row)
    report=dict(ok=all(r['frame_time_change_percent']<=10 for r in comparison),comparison=comparison,trials=a.trials,conditions='Same machine, resolution, seed, legal commands, production rendering; uncapped fps; first 0.3s of each beat excluded. Two trial orders reversed.',results=results)
    write_json(a.output/'result.json',report);print(json.dumps({k:v for k,v in report.items() if k!='results'},indent=2))
