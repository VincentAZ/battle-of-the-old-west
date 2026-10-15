// Direct drags must be exactly an ordinary activation plus its selected choice,
// committed in one revision. Fixtures remain authoritative rules-only tests.
J gestureFor(const Engine& e,int source,const std::string& kind,int ability=-1) {
    for(const auto& a:legal(e))if(a["command"].value("source",0)==source&&
        (ability<0||a["command"].value("ability",-1)==ability))
        for(const auto& g:a.value("gestures",J::array()))
            if(g["command"].value("kind",g.contains("event_slot")?std::string("raid"):std::string())==kind)return g;
    throw std::runtime_error("Missing drag "+kind+" for "+std::to_string(source));
}
void ordinaryGesture(Engine& e,const J& cmd) {
    action(e,0,"activate",cmd["source"],cmd["ability"]);
    if(cmd["type"]=="activate")return;
    const std::string kind=cmd["kind"];
    if(saved(e)["choice"].value("prompt",std::string())=="Choose a punk or a raid")choice(e,-1,kind=="raid"?"Raid":"Gain a punk");
    if(kind=="raid"||e.IsFinished())return;
    if(kind=="sacrifice"||kind=="damage"||kind=="destroy"||kind=="gallows"){choice(e,cmd["target"]);return;}
    const J state=saved(e);
    for(const auto& o:state["choice"]["options"])if(!o["tasks"].empty()) {
        const J& t=o["tasks"][0];const J& space=cmd["placement"];
        if(t.value("column",-1)==space.value("column",-2)&&t.value("position",-1)==space.value("position",-2)&&
            t.value("replace",0)==space.value("replace",0)&&
            (kind!="move"||(t.value("target",0)==cmd["target"]&&t.value("player",-1)==cmd["player"]))) {
            act(e,0,{{"type","choose"},{"option",o["id"]}});return;
        }
    }
    throw std::runtime_error("Ordinary activation did not offer drag destination");
}
void dragActivationContracts() {
    auto e=game();J base=fixture(e);
    put(base,"widow_with_a_shotgun",0,0);put(base,"doc_holliday",0,1,false,1);put(base,"bartender",1,0);
    int emitted=0;
    // This traverses all advertised shortcut variants, including full-board
    // replacement, injured sacrifices, granted restrictions, and branch cards.
    for(bool full:{false,true})for(const std::string key:{"gunsmith","livery_barn","free_homestead","wanted_poster_board","wagon_fort",
        "cattle_ranch","coal_yard","cattlemen_s_club","stockyards","stagecoach_station","roundup_corral","boarding_house","rodeo_grounds","army_surgeon_s_tent",
        "homestead_cabin","gatling_emplacement","railroad_work_camp","silver_mine","undertaker","revival_tent","bare_knuckle_ring","rustlers_corral"}) {
        J state=base;int source=camp(state,0,2,key);
        if(full) {put(state,"vigilante",0,0);put(state,"bounty_hunter",0,1);put(state,"claim_jumper",0,2);put(state,"rustler",0,2,true);}
        else if(key=="rustlers_corral")put(state,"rustler",0,2,true);
        load(e,state);const std::string unchanged=e.SaveJson();const J actions=legal(e);
        check(unchanged==e.SaveJson(),"Advertising drags changed the game or random state");
        check(legal(e,1).empty(),"Inactive opponent was offered drags");
        for(const auto& a:actions)if(a["command"].value("source",0)==source)for(const auto& g:a.value("gestures",J::array())) {
            ++emitted;const J cmd=g["command"];
            check(!g.contains("tasks")&&!g.contains("card_id"),"Drag metadata exposed private effect data");
            auto normal=game();load(normal,state);ordinaryGesture(normal,cmd);
            load(e,state);const int revision=view(e)["revision"];act(e,0,cmd);
            check(view(e)["revision"]==revision+1,"Drop was not one atomic move");
            J expected=saved(normal),actual=saved(e);
            for(const char* field:{"cards","players","deck","discard","rng","tasks","status","winner"})
                check(expected[field]==actual[field],key+" drag differs from ordinary play in "+field);
            check(expected["choice"].is_null()==actual["choice"].is_null(),key+" lost a required follow-up choice");
            if(!expected["choice"].is_null()) {
                for(auto* v:{&expected["choice"],&actual["choice"]})for(auto& option:(*v)["options"])option.erase("id");
                check(expected["choice"]==actual["choice"],key+" changed remaining choices");
            }
        }
    }
    {
        J state=base;const int looter=put(state,"claim_jumper",0,2);
        load(e,state);
        J cmd;const J boardView=view(e);
        for(const auto& a:legal(e))if(a["command"].value("source",0)==looter)
            for(const auto& g:a.value("gestures",J::array()))
                if(g.contains("target")) {
                    const int target=g["target"];
                    for(const auto& col:boardView["players"][1]["columns"])for(const auto& card:col)
                        if(card["id"]==target&&card.value("type",std::string())=="camp")cmd=g["command"];
                }
        check(!cmd.is_null(),"Claim Jumper has no direct camp attack");
        auto normal=game();load(normal,state);ordinaryGesture(normal,cmd);
        const int water=state["players"][0]["water"],hand=state["players"][0]["hand"].size();
        act(e,0,cmd);
        check(saved(e)["players"][0]["water"]==water-2,"Claim Jumper drag charged wrong water");
        check(saved(e)["players"][0]["hand"].size()==hand+1,"Claim Jumper camp hit did not draw");
        check(entity(saved(e),cmd["target"])["damage"]==1,"Claim Jumper did not damage camp");
        for(const char* field:{"cards","players","deck","discard","rng","tasks","status","winner"})
            check(saved(e)[field]==saved(normal)[field],std::string("Claim Jumper drag differs in ")+field);
        const auto before=e.SaveJson();
        check(!J::parse(e.Apply(0,cmd.dump())).value("ok",true)&&before==e.SaveJson(),"Spent Claim Jumper attacked twice");
        auto rejectAttack=[&](const J& invalidState) {
            load(e,invalidState);const auto unchanged=e.SaveJson();
            check(!J::parse(e.Apply(0,cmd.dump())).value("ok",true)&&unchanged==e.SaveJson(),
                "Illegal camp attack changed state or spent water");
        };
        J invalid=state;invalid["players"][0]["water"]=1;rejectAttack(invalid);
        invalid=state;entity(invalid,looter)["damage"]=1;entity(invalid,looter)["ready"]=false;rejectAttack(invalid);
        invalid=state;
        for(int column=0;column<3;++column)
            for(const auto& card:boardView["players"][1]["columns"][column])
                if(card["id"]==cmd["target"])put(invalid,"widow_with_a_shotgun",1,column);
        rejectAttack(invalid);
    }
    check(emitted>150,"Too few shortcut variants exercised");
    J state=base;int labor=camp(state,0,2,"railroad_work_camp");load(e,state);
    J cmd=gestureFor(e,labor,"sacrifice")["command"];
    auto reject=[&](J bad,int seat=0) {
        const std::string before=e.SaveJson();J result=J::parse(e.Apply(seat,bad.dump()));
        check(!result.value("ok",true)&&e.SaveJson()==before,"Invalid drag was not rejected atomically");
    };
    J bad=cmd;bad["target"]=labor;reject(bad);
    bad=cmd;bad["target"]=state["players"][1]["columns"][0][0];reject(bad);
    bad=cmd;bad["revision"]=view(e)["revision"].get<int>()-1;reject(bad);
    reject(cmd,1);
    entity(state,labor)["ready"]=false;load(e,state);reject(cmd);
    entity(state,labor)["ready"]=true;entity(state,labor)["damage"]=1;load(e,state);
    act(e,0,cmd);check(!saved(e)["choice"].is_null(),"Damaged Railroad Work Camp must still offer restore");
    // A paid drag disappearing for insufficient water cannot activate anyway.
    state=base;int garage=camp(state,0,2,"cattle_ranch");load(e,state);cmd=gestureFor(e,garage,"raid")["command"];
    state["players"][0]["water"]=0;load(e,state);reject(cmd);
    // Later placements from a multi-punk camp remain draggable from that
    // same public source, without reactivating it or revealing incoming faces.
    state=base;int fortress=camp(state,0,2,"wagon_fort");load(e,state);
    act(e,0,gestureFor(e,fortress,"punk")["command"]);
    for(int remaining=0;remaining<2;++remaining) {
        J placement;
        for(const auto& a:legal(e))if(a.contains("placement")) {
            check(a.value("drag_source",0)==fortress,"Pending punk lost its drag source");
            check(a["placement"]["card"]==0&&!a["placement"].contains("card_id"),"Pending punk exposed its hidden identity");
            if(placement.is_null())placement=a["command"];
        }
        check(!placement.is_null(),"Wagon Fort lost a remaining placement");act(e,0,placement);
    }
    check(entity(saved(e),fortress)["uses"]==1,"Remaining punk drags activated Wagon Fort again");
    // Full queue / blocked advance: no misleading lit destination is offered.
    state=base;garage=camp(state,0,2,"cattle_ranch");
    int raiders=state["players"][0]["stampede"];
    int event=put(state,"cannonade",0);detach(state,event);entity(state,event)["zone"]="queue";
    state["players"][0]["queue"][0]=event;state["players"][0]["queue"][1]=raiders;entity(state,raiders)["zone"]="queue";
    load(e,state);
    for(const auto& a:legal(e))if(a["command"].value("source",0)==garage)check(!a.contains("gestures"),"Blocked Stampede showed a drop destination");
    // Moving a queued Raider must advance precisely one position.
    state["players"][0]["queue"][0]=0;entity(state,event)["zone"]="hand";state["players"][0]["hand"].push_back(event);
    load(e,state);J raid=gestureFor(e,garage,"raid");check(raid["event_slot"]==0,"Raider advance badge points to wrong slot");
    check(std::find(raid["cards"].begin(),raid["cards"].end(),J(raiders))!=raid["cards"].end(),"Queued Raider cannot initiate its own drag");
    act(e,0,raid["command"]);check(saved(e)["players"][0]["queue"][0]==raiders,"Raider did not advance");
}

void raidJunkAndPunkSupplyContracts() {
    auto e=game();J base=fixture(e);
    int assassin=put(base,"bounty_hunter",0),vigilante=put(base,"vigilante",0);
    put(base,"hellfire_preacher",0);
    int raiders=base["players"][0]["stampede"];
    for(int slot:{-1,2,1,0}) {
        J state=base;detach(state,raiders);
        entity(state,raiders)["zone"]=slot<0?"special":"queue";
        if(slot>=0)state["players"][0]["queue"][slot]=raiders;
        state["players"][0]["water"]=0;load(e,state);
        const auto before=e.SaveJson();int found=0;
        for(const auto& a:legal(e))if(a["command"]["type"]=="junk") {
            int card=a["command"]["card"];
            if(card!=assassin&&card!=vigilante)continue;
            check(a.contains("gestures")&&a["gestures"].size()==1,"Raid junk not exposed to Raider menu");
            const auto& g=a["gestures"][0];++found;
            check(g["cards"]==J::array({card,raiders})&&g["cost"]==0,"Wrong raid junk source or cost");
            check(g["command"]==a["command"],"Junk gesture invented a different command");
            if(slot>=0)check(g["event_slot"]==slot-1,"Junk Raider destination wrong");
        }
        check(found==2&&e.SaveJson()==before,"Inspecting raid junk mutated state or omitted a card");
        action(e,0,"junk",assassin);
        check(entity(saved(e),assassin)["zone"]=="discard"&&view(e)["players"][0]["water"]==0,"Raid junk failed free discard");
        if(slot>0)check(saved(e)["players"][0]["queue"][slot-1]==raiders,"Raid junk failed to advance");
    }
    J state=base;int obstacle=put(state,"cannonade",0);detach(state,obstacle);
    state["players"][0]["queue"][0]=obstacle;entity(state,obstacle)["zone"]="queue";
    state["players"][0]["queue"][1]=raiders;entity(state,raiders)["zone"]="queue";load(e,state);
    for(const auto& a:legal(e))if(a["command"]["type"]=="junk"&&a["command"]["card"]==assassin)
        check(!a.contains("gestures"),"Blocked Raider queue advertised a move");
    state=base;int fortress=camp(state,0,0,"wagon_fort");load(e,state);action(e,0,"activate",fortress);
    for(int count=3;count>0;--count) {
        J place;
        for(const auto& a:legal(e))if(a.contains("placement")&&a["placement"].value("punk",false)) {
            check(a.value("punk_remaining",0)==count,"Punk shelter batch count wrong");
            check(a["placement"]["card"]==0&&!a.contains("card_id"),"Punk supply exposed hidden identity");place=a["command"];
        }
        check(!place.is_null(),"Punk batch lost destinations");act(e,0,place);
    }
    check(saved(e)["choice"].is_null(),"Punk batch failed to finish");
}
