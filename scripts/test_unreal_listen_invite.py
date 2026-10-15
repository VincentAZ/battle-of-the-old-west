#!/usr/bin/env python3
"""Focused waiting-screen readiness, real Copy click and manual-address join.

Root must assign the native lane before invocation. Host/Join use their ordinary
local callbacks; Copy uses actual Slate pointer events and an external clipboard
read. This does not type into the join text field or test a second computer.
"""
import argparse
import copy
import hashlib
import ipaddress
import json
import re
import subprocess
import time
from pathlib import Path

from native_clipboard_probe import clipboard_matches
from native_launch import create_native_run_directory,game_net_driver_ports,stop_owned_process_groups
from native_runtime_checks import assert_runtime_assets
from test_unreal_hud import resolution
from test_unreal_interactions import InteractionScenario,EDITOR,ROOT,center,write_json
from test_unreal_portraits import portraits_ready
from test_unreal_session_lifecycle import public_state


def rendered_graphics(dimensions):
    width,height=dimensions
    # RenderOffscreen forces SDL's dummy video backend even when x11 is
    # requested explicitly. A desktop clipboard check needs a real window.
    return ['-windowed','-sdlvideodriver=x11','-ForceRes',f'-ResX={width}',f'-ResY={height}']


def observed_sdl_video_driver(log):
    drivers=re.findall(r"Using SDL video driver '([^']+)'",log)
    return drivers[-1] if drivers else None


def waiting_ready(state, port):
    snapshot=state.get('snapshot',{});hud=state.get('hud',{})
    if not(snapshot.get('hosted') and snapshot.get('connected')==1 and snapshot.get('view',{}).get('status')=='selection'):
        return False
    mine=snapshot['view']['players'][snapshot['seat']]
    ids=[c['id'] for c in mine.get('offers',[])]
    if len(ids)!=6 or not portraits_ready(hud.get('portraits',{}),ids):return False
    for scene in hud['portraits']['scenes']:
        if scene['card_id'] in ids:
            render=scene.get('render_readiness',{})
            if render.get('last_painted_placeholder') is not False or render.get('last_painted_frame',0)<=0:return False
    buttons=hud.get('invite_buttons',[]);size=hud.get('hud_size',[])
    if not buttons or len(size)!=2 or min(size)<=0:return False
    endpoints=[]
    for button in buttons:
        host,separator,number=button.get('endpoint','').rpartition(':')
        if not separator or number!=str(port):return False
        try: address=ipaddress.IPv4Address(host)
        except ipaddress.AddressValueError:return False
        if address.is_loopback or address.is_link_local or int(address)>>24 in (0,127) or int(address)>>24>=224:return False
        if len(button.get('min',[]))!=2 or len(button.get('max',[]))!=2:return False
        if not(button.get('visible') and button.get('enabled') and all(
            -1<=a<b<=limit+1 for a,b,limit in zip(button.get('min',[]),button.get('max',[]),size))):return False
        endpoints.append(button['endpoint'])
    return len(endpoints)==len(set(endpoints))


class InviteScenario(InteractionScenario):
    def launch(self,name,url,rendered=False):
        stream=(self.folder/f'{name}-console.log').open('w');self.streams.append(stream)
        graphics=rendered_graphics(self.dimensions) if rendered else ['-nullrhi']
        # A LAN listener must not inherit InteractionScenario's loopback-only MULTIHOME.
        self.processes[name]=subprocess.Popen(self.runtime.argv+[url,'-game',*graphics,
            '-OldWestLifecycleTest','-OldWestVisualTest',f'-OldWestTestSeed={self.args.seed}',
            f'-OldWestLifecycleControl={self.folder}/{name}.control.json',
            f'-OldWestLifecycleReport={self.folder}/{name}.json',f'-port={self.port}',
            f'-OldWestProfileRoot={self.folder}/profiles',f'-OldWestProfile={name}',
            f'-GameUserSettingsINI={self.folder}/{name}.settings.ini',f'-abslog={self.folder}/{name}.log',
            '-ExecCmds=t.MaxFPS 60','-nosound','-unattended','-nosplash','-NoLiveCoding',
            '-stdout','-FullStdOutLogOutput'],cwd=self.runtime.cwd,env=self.runtime.env,stdout=stream,
            stderr=subprocess.STDOUT,start_new_session=True)

    def wait_ready(self,label):
        since=None
        def ready():
            nonlocal since
            if not waiting_ready(self.read(),self.actual_port):since=None;return False
            if since is None:since=time.monotonic()
            # Compiler/PSO/paint gates are the acceptance predicates. This
            # additional stable interval lets transient editor notices fade;
            # actual notification occlusion still needs screenshot review.
            return time.monotonic()-since>=2.
        self.wait(label,ready,120)

    def run(self):
        result={'ok':False}
        try:
            self.launch('a','/Game/Maps/WaterDepotV2',True)
            self.wait('rendered main menu',lambda:self.snapshot().get('hosted') is False and self.hud(),120)
            video_driver=observed_sdl_video_driver((self.folder/'a.log').read_text(errors='replace'))
            self.evidence['clipboard_video_backend']={'actual_sdl_driver':video_driver,
                'required':'x11','render_offscreen':False,'visible_window':True}
            assert video_driver=='x11','Clipboard observer requires the actual SDL x11 video backend'
            self.command('a','host',ruleset=self.args.ruleset)
            self.wait('host authenticates its own seat',lambda:self.snapshot().get('connected')==1,60)
            ports=self.wait('actual named GameNetDriver listener port',lambda:game_net_driver_ports(
                (self.folder/'a.log').read_text(errors='replace')),20)
            self.actual_port=ports[-1]
            assert self.actual_port==self.port,'Actual listen port differs from requested custom port'
            self.wait_ready('six painted final portraits and all waiting invite buttons ready')
            before=copy.deepcopy(self.read());self.capture('00-waiting-ready')
            after=copy.deepcopy(self.read())
            assert waiting_ready(before,self.actual_port) and waiting_ready(after,self.actual_port),'Readiness changed across waiting capture'
            write_json(self.folder/'00-waiting-ready.bracket.json',{'before':before,'after':after})
            self.checked('Six actual waiting portraits are fully ready and invite endpoints contain the actual custom driver port')
            buttons=self.hud()['invite_buttons'];endpoint=buttons[0]['endpoint']
            snapshots=copy.deepcopy(self.snapshot())
            spot=center(buttons[0]);self.event('move',spot);self.event('down',spot);self.event('up',spot)
            copied=clipboard_matches(endpoint)
            self.evidence['clipboard']={**copied,'expected_endpoint':endpoint,'pointer_hud_position':spot}
            self.evidence['waiting_endpoints']=buttons
            assert copied['matches_expected_endpoint'],'Actual clipboard does not equal the clicked endpoint'
            assert self.snapshot()==snapshots,'Copy click changed authoritative state'
            self.checked('Real Slate Copy click places the exact displayed host:port on the platform clipboard')
            self.launch('b','/Game/Maps/WaterDepotV2')
            self.wait('second process opens ordinary menu',lambda:self.snapshot('b').get('hosted') is False,90)
            manual=f'127.0.0.1:{self.actual_port}'
            assert manual not in [b['endpoint'] for b in buttons],'Loopback unexpectedly offered as LAN suggestion'
            self.command('b','join',address=manual)
            self.wait('manual unsuggested endpoint joins two distinct seats',lambda:self.agree() and
                {self.snapshot(n)['seat'] for n in ('a','b')}=={0,1},90)
            assert public_state(self.snapshot('a'))==public_state(self.snapshot('b'))
            self.wait('waiting-only invite buttons disappear after connection',lambda:not self.hud().get('invite_buttons'),10)
            self.evidence['manual_join']={'endpoint':manual,'suggested':False,'method':'ordinary JoinMatch local callback',
                'distinct_seats':[self.snapshot(n)['seat'] for n in ('a','b')],'public_views_equal':True}
            self.checked('Ordinary manual JoinMatch accepts an unsuggested endpoint and preserves matching public state')
            self.capture('01-joined-selection')
            result.update(ok=True,runtime_assets=assert_runtime_assets([self.folder/'a.log',self.folder/'b.log']))
        except Exception as error:
            result.update(failure=str(error),last_reports=self.reports)
            raise
        finally:
            try:
                stop_owned_process_groups(list(self.processes.values()),self.streams)
                result['owned_process_cleanup_complete']=True
            except Exception as error:
                result.update(ok=False,owned_process_cleanup_complete=False,cleanup_failure=str(error))
                raise
            finally:
                result.update(resolution=list(self.dimensions),checks=self.checks,screenshots=self.captures,evidence=self.evidence,
                    limitations=['Two local processes, not physical LAN/Internet/Windows connectivity.',
                        'Host and Join invoke ordinary local callbacks; no address text-entry or Join button hit test.',
                        'Clipboard probe requires Linux X11/XWayland selection support and only reads after this test Copy click.',
                        'Host opens a real SDL x11 window; this is explicit X11/XWayland evidence, not default Wayland backend coverage.',
                        'Post-click clipboard equality does not prove a change event if the clipboard already contained the exact endpoint.',
                        'Readiness telemetry covers portraits; visual inspection must still check transient editor notifications and text overlap.',
                        'No full match, deployment, AI, rematch or reconnect coverage in this focused observer.'])
                write_json(self.folder/'result.json',result)
        return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--editor',type=Path,default=EDITOR)
    parser.add_argument('--package-dir',type=Path)
    parser.add_argument('--resolutions',nargs='+',type=resolution,default=[(1280,720),(1920,1080)])
    parser.add_argument('--port',type=int,default=19679)
    parser.add_argument('--timeout',type=float,default=300)
    parser.add_argument('--settle',type=float,default=.3)
    parser.add_argument('--seed',type=int,default=2623)
    parser.add_argument('--ruleset',choices=['base_2024','boomtown'],default='boomtown')
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    if not 1<=args.port<=65535-len(args.resolutions)+1:parser.error('Invalid test port range')
    output=args.output.resolve() if args.output else create_native_run_directory('oldwest-listen-invite-')
    output.mkdir(parents=True,exist_ok=True)
    assert not (output/'observer-inputs.json').exists(),'Preserve previous observer evidence'
    paths=[Path(__file__),Path(__file__).with_name('native_clipboard_probe.py'),
        Path(__file__).with_name('test_unreal_interactions.py'),Path(__file__).with_name('test_unreal_portraits.py')]
    inputs={str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    write_json(output/'observer-inputs.json',inputs);results=[];failure=None;immutable=False
    print('Focused invite observer: '+str(output),flush=True)
    try:
        for index,dimensions in enumerate(args.resolutions):
            results.append(InviteScenario(args,output,dimensions,index).run())
        immutable=all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in inputs.items())
        assert immutable,'Observer inputs changed during native run'
    except Exception as error:
        failure=str(error)
        raise
    finally:
        immutable=all(Path(p).is_file() and hashlib.sha256(Path(p).read_bytes()).hexdigest()==h
            for p,h in inputs.items())
        write_json(output/'result.json',{'ok':failure is None and immutable and len(results)==len(args.resolutions) and all(r['ok'] for r in results),
            'failure':failure,'observer_inputs_unchanged':immutable,
            'results':results,'resolution_reports':[str(output/f'{w}x{h}'/'result.json') for w,h in args.resolutions],
            'runtime_validation_status':'Only complete per-resolution results are evidence.'})


if __name__=='__main__':main()
