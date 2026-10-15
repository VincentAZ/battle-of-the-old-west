"""Legal two-peer delivery replay; inspect native transforms and real captures."""
import copy
import json
import math
import test_unreal_bonus_whiskey as bonus
from test_unreal_action_showcase import signature
from test_unreal_interactions import write_json


def validate_delivery(d):
    parts=d['parts'];animals=d['animals']
    assert len(animals)==4 and all(a['collision_enabled']==0 for a in animals)
    assert all(abs(v-.36)<1e-5 for a in animals for v in a['scale'])
    assert all(p['collision_enabled']==0 for p in parts)
    assert sum('SM_Delivery_OxYoke' in p['mesh'] for p in parts)==2
    assert sum('Chain' in p['mesh'] for p in parts)==2
    wheels=[p for p in parts if p['wheel_radius_cm']>0]
    assert len(wheels)==4
    cargo=[p for p in parts if 'SM_Action_WhiskeyCase' in p['mesh'] or 'SM_Action_CargoCrate' in p['mesh']]
    assert len(cargo)==d['cargo_count']
    assert all(('WhiskeyCase' in p['mesh'])==d['whiskey'] for p in cargo)
    assert not any(any(old in p['mesh'] for old in ['CartChassis','CartWheel','Winch','RailBase','TowCable']) for p in parts)
    yaw=math.atan2(d['to'][1]-d['from'][1],d['to'][0]-d['from'][0])-math.pi/2
    root=[a+(b-a)*d['travel_cm']/d['route_cm'] for a,b in zip(d['from'],d['to'])]
    # Verify measured cargo bounds against the actual authored floor, rather
    # than only checking their height. Native routes are axis-aligned, so these
    # transformed world bounds also retain the exact horizontal box extents.
    assert abs(math.sin(2*yaw))<1e-5,'Cargo bound audit requires an axis-aligned route'
    local_boxes=[]
    for p in cargo:
        points=[]
        for x in [p['bounds'][0][0],p['bounds'][1][0]]:
            for y in [p['bounds'][0][1],p['bounds'][1][1]]:
                dx,dy=(x-root[0])/.4,(y-root[1])/.4
                points.append((math.cos(yaw)*dx+math.sin(yaw)*dy,-math.sin(yaw)*dx+math.cos(yaw)*dy))
        box=[min(q[0] for q in points),min(q[1] for q in points),max(q[0] for q in points),max(q[1] for q in points)]
        assert -55.66<=box[0]<=box[2]<=55.66 and -183.01<=box[1]<=box[3]<=183.01,'Cargo overhangs wagon floor'
        assert abs((p['bounds'][0][2]-root[2])/.4-96)<.25,'Cargo bottom is not supported by floor'
        for other in local_boxes:
            assert min(box[2],other[2])-max(box[0],other[0])<=.01 or min(box[3],other[3])-max(box[1],other[1])<=.01,'Cargo boxes overlap'
        local_boxes.append(box)
    # Compare the rendered wheel quaternion with rolling distance,
    # independently accounting for either direction of the wagon.
    for w in wheels:
        a=-d['travel_cm']/w['wheel_radius_cm']/2
        expected=[math.cos(yaw/2)*math.sin(a),math.sin(yaw/2)*math.sin(a),
                  math.sin(yaw/2)*math.cos(a),math.cos(yaw/2)*math.cos(a)]
        assert abs(sum(x*y for x,y in zip(expected,w['rotation'])))>1-1e-5
    if d['walking']:
        for i,a in enumerate(animals):
            expected=(d['travel_cm']/(59.5238095*.9*.4)+(i%2)*.6)%1.2
            delta=abs(a['seconds']-expected)
            assert min(delta,abs(delta-1.2))<.002,'Gait phase differs from actual travel'


class DeliveryScenario(bonus.BonusScenario):
    def __init__(self,*args):
        super().__init__(*args)
        self.delivery_samples={}
        self.build['delivery_harness']=signature(__file__)
        for name in ['OldWestDeliveryVisuals.cpp','OldWestDeliveryVisuals.h','OldWestAssetHistory.h','OldWestCardHover.cpp']:
            self.build[name]=signature(bonus.ROOT/'game/OldWest/Source/OldWestGame/Private'/name)
        write_json(self.folder/'build.json',self.build)

    def observe(self,state):
        super().observe(state)
        c=state.get('cinematic',{})
        if not c.get('busy'):return
        for d in c.get('deliveries',[]):
            validate_delivery(d)
            if c.get('kind')=='water' and c.get('sequence') in self.water_events:
                event=self.water_events[c['sequence']]
                if event['detail']:
                    assert d['cargo_count']==int(event['detail']) and d['whiskey']
            self.delivery_samples.setdefault(c['sequence'],[]).append(copy.deepcopy(d))

    def run(self):
        try:return super().run()
        finally:
            report=json.loads((self.folder/'result.json').read_text())
            required={s for s,e in self.water_events.items() if e['detail']}
            complete=required.issubset(self.delivery_samples)
            for seq in required:
                rows=self.delivery_samples.get(seq,[])
                complete &= any(r['walking'] and .1<r['travel_cm']<r['route_cm']-.1 for r in rows)
                complete &= any(not r['walking'] and r['age']>r['move_seconds']+.18 for r in rows)
            directions={1 if d['to'][1]>d['from'][1] else -1 for rows in self.delivery_samples.values() for d in rows}
            complete &= directions=={-1,1}
            related=(self.note or {}).get('related',{})
            complete &= related.get('key')=='trail-delivery' and len(related.get('body','').splitlines())==3
            report.update(ok=report['ok'] and complete,delivery_samples={s:len(v) for s,v in self.delivery_samples.items()},
                          delivery_refills_verified=sorted(required),delivery_directions=sorted(directions),
                          delivery_limits=['This replay covers ordinary three-case refills in both directions and the existing bonus glass. Medical, Native-source, all cargo counts, skip/reconnect and other regions still require review.'])
            write_json(self.folder/'delivery-samples.json',self.delivery_samples)
            write_json(self.folder/'result.json',report)


if __name__=='__main__':
    bonus.BonusScenario=DeliveryScenario
    bonus.main()
