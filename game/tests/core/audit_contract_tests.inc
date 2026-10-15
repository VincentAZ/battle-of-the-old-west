// Rule/printed-card contracts independently checked against the retained 2026-09-08
// card scans and designer replies. Included after the common fixture helpers.
bool offersAbility(const Engine& e,int source,int ability=0,int owner=0) {
    for(const auto& a:legal(e,owner))if(a["command"].value("source",0)==source&&a["command"].value("ability",-1)==ability)return true;
    return false;
}

void campThresholdContracts() {
    const std::vector<std::string> people={"bartender","widow_with_a_shotgun","vigilante","prospector","bounty_hunter","hellfire_preacher"};
    for(const std::string key:{"livery_barn","toll_bridge","timber_ram"})for(int n=0;n<=6;++n) {
        auto e=game();auto s=fixture(e);int source=camp(s,0,0,key);
        for(int i=0;i<n;++i)put(s,people[i],0,i/2,i%2==0,i%2);
        load(e,s);const bool expected=key=="livery_barn"?n<=1:key=="toll_bridge"?n>=4:n>=6;
        check(offersAbility(e,source)==expected,key+": threshold must count damaged people and punks");
    }
    for(const std::string key:{"freight_warehouse","free_homestead"})for(bool ruin:{false,true})for(bool guard:{false,true}) {
        auto e=game();auto s=fixture(e);int source=camp(s,0,0,key);
        for(int c=0;c<3;++c){int target=camp(s,1,c,"gatling_emplacement");if(c==2||(c==0&&ruin)){entity(s,target)["destroyed"]=true;entity(s,target)["damage"]=2;entity(s,target)["ready"]=false;}else entity(s,target)["damage"]=1;}
        put(s,"bartender",1,1); // One surviving protected camp keeps this a live game.
        if(guard)put(s,"widow_with_a_shotgun",1,0,false,1);
        load(e,s);check(offersAbility(e,source)==(!ruin&&!guard),key+": only an exposed surviving camp satisfies the condition");
    }
    for(int punks=0;punks<=4;++punks) {
        auto e=game();auto s=fixture(e);int source=camp(s,0,0,"bunkhouse");
        for(int n=0;n<punks;++n)put(s,people[n],0,n/2,true);
        s["players"][0]["water"]=3;load(e,s);action(e,0,"activate",source);choice(e);
        check(view(e)["players"][0]["water"]==3-std::max(0,3-punks),"Bunkhouse must discount each punk but never generate water");
    }
    for(bool damage:{false,true}) {
        auto e=game();auto s=fixture(e);int cannon=camp(s,0,0,"army_fort"),village=camp(s,0,1,"quaker_settlement");
        entity(s,cannon)["damage"]=int(damage);entity(s,village)["damage"]=int(damage);load(e,s);
        check(offersAbility(e,cannon)==!damage,"Revised Army Fort's specific healthy condition must apply");
        check(offersAbility(e,village,0)==!damage&&offersAbility(e,village,1)==damage,"Quaker Settlement must choose its mode by damage state");
    }
}

void designerFieldHospitalContracts() {
    // Published ruling: injured, outside this column, must move.
    for(int column:{0,1})for(int damage:{0,1})for(bool full:{false,true}) {
        auto e=game();auto s=fixture(e);int hospital=camp(s,0,0,"army_surgeon_s_tent");
        int patient=put(s,"civil_war_veteran",0,column,false,damage);
        if(full){put(s,"bartender",0,0);if(column!=0)put(s,"widow_with_a_shotgun",0,0);}
        load(e,s);bool expected=column==1&&damage==1&&!full;
        check(offersAbility(e,hospital,0)==expected,"Army Surgeon's Tent accepted a healthy, same-column, or blocked patient");
        check(offersAbility(e,hospital,1),"Army Surgeon's Tent's raid must remain an independent option");
        if(expected){action(e,0,"activate",hospital,0);choice(e,patient);auto after=saved(e);
            check(after["players"][0]["columns"][0][0]==patient&&entity(after,patient)["damage"]==0,"Hospital did not move and restore patient");
            check(!entity(after,patient)["ready"].get<bool>()&&after["players"][0]["entered"]==0,"Hospital incorrectly readied patient or counted an entry");}
    }
}

void campEffectContracts() {
    // Each independently chosen target group must preserve protection and side.
    struct AttackContract{std::string key;bool peopleOnly,any;};
    for(const auto& rule:std::vector<AttackContract>{{"gatling_emplacement",false,false},{"artillery_battery",false,true},{"rodeo_grounds",true,false},{"gallows",true,false},{"toll_bridge",false,true},{"timber_ram",false,true},{"vigilance_committee",false,true}}) {
        auto e=game();auto s=fixture(e);int source=camp(s,0,0,rule.key),rear=put(s,"bartender",1,0),front=put(s,"widow_with_a_shotgun",1,0);
        int targetCamp=camp(s,1,0,"gatling_emplacement");
        const std::vector<std::string> army={"prospector","vigilante","bounty_hunter","hellfire_preacher","gatling_gunner","doc_holliday"};
        for(int n=0;n<6;++n)put(s,army[n],0,n/2,true);
        if(rule.key=="vigilance_committee")for(const std::string k:{"run_out_of_town","prairie_fire","cholera","box_canyon","poker_night"})put(s,k,0);
        load(e,s);action(e,0,"activate",source,0);
        if(rule.key=="vigilance_committee")for(int n=0;n<5;++n)choice(e);
        auto now=saved(e);std::set<int> targets;
        for(const auto& o:now["choice"]["options"])for(const auto& t:o["tasks"])targets.insert(t.value("target",0));
        bool campsOnly=rule.key=="toll_bridge"||rule.key=="timber_ram";
        check(targets.count(front)==!campsOnly,rule.key+": exposed person eligibility wrong");
        check(targets.count(rear)==(rule.any&&!campsOnly),rule.key+": protected person eligibility wrong");
        check(targets.count(targetCamp)==(rule.any&&!rule.peopleOnly),rule.key+": protected camp eligibility wrong");
        for(int id:targets)if(id)check(entity(now,id)["owner"]==1,"Attack offered a friendly target");
        check(now["choice"]["player"]==(rule.key=="artillery_battery"?1:0),"Wrong player selects attack target");
    }
    // All camp restore boxes exclude the source, ruins, healthy cards and Bonfire.
    for(const auto& mode:std::vector<std::pair<std::string,int>>{{"stagecoach_station",1},{"jailhouse",1},{"freight_warehouse",0},{"boot_hill",0},{"barn_raising",0},{"quaker_settlement",0}}) {
        auto e=game();auto s=fixture(e);int source=camp(s,0,0,mode.first),bonfire=camp(s,0,1,"logging_camp"),hurt=put(s,"widow_with_a_shotgun",0,2,false,1);
        entity(s,source)["damage"]=mode.first=="quaker_settlement"?0:1;entity(s,bonfire)["damage"]=1;
        s["players"][0]["hurt"]=true;s["players"][0]["entered"]=2;load(e,s);action(e,0,"activate",source,mode.second);
        auto pending=saved(e);std::set<int> targets;
        for(const auto& o:pending["choice"]["options"])for(const auto& t:o["tasks"])targets.insert(t.value("target",0));
        check(targets==std::set<int>{hurt},mode.first+": restore target restrictions wrong");choice(e,hurt);
        check(entity(saved(e),hurt)["damage"]==0&&!entity(saved(e),hurt)["ready"].get<bool>(),"Camp restore incorrectly grants readiness");
    }
    // Required hand payments cannot spend the renewable Silo.
    for(const auto& cost:std::vector<std::pair<std::string,int>>{{"salvage_yard",1},{"pawn_shop",2},{"horse_trader",3},{"vigilance_committee",5}}) {
        auto e=game();auto s=fixture(e);int source=camp(s,0,0,cost.first);
        auto hand=s["players"][0]["hand"].get<std::vector<int>>();for(int id:hand){detach(s,id);entity(s,id)["zone"]="discard";entity(s,id)["owner"]=-1;s["discard"].push_back(id);}
        const std::vector<std::string> payment={"run_out_of_town","prairie_fire","cholera","box_canyon","poker_night"};
        for(int n=0;n<cost.second-1;++n)put(s,payment[n],0);
        int silo=s["players"][0]["silo"];entity(s,silo)["zone"]="hand";s["players"][0]["hand"].push_back(silo);load(e,s);
        check(!offersAbility(e,source),cost.first+": Silo incorrectly counted toward required discard payment");
        put(s,payment[cost.second-1],0);load(e,s);check(offersAbility(e,source),"Payable camp conversion missing");
        action(e,0,"activate",source);auto pending=saved(e);for(const auto& o:pending["choice"]["options"])for(const auto& t:o["tasks"])check(t.value("target",0)!=silo,"Silo offered as discard payment");
    }
}

void bookWorkedSequenceContracts() {
    // Chapter 20.1: copy the still-ready Team, two paid Bot entries, two heals.
    auto e=game();auto s=fixture(e);int mimic=put(s,"con_man",0,0),team=put(s,"sarah_winnemucca",0,1),bot=put(s,"blacksmith",0,2);
    int first=camp(s,0,0,"gatling_emplacement"),second=camp(s,0,1,"gatling_emplacement");entity(s,first)["damage"]=1;entity(s,second)["damage"]=1;
    s["players"][0]["water"]=2;load(e,s);action(e,0,"activate",mimic);choice(e,-1,"Sarah Winnemucca:");choice(e,bot);
    action(e,0,"play",bot);choice(e,first);action(e,0,"activate",team);choice(e,bot);action(e,0,"play",bot);choice(e,second);
    check(view(e)["players"][0]["water"]==0&&entity(saved(e),first)["damage"]==0&&entity(saved(e),second)["damage"]==0,"Book 20.1 repair loop ledger failed");
    check(saved(e)["players"][0]["entered"]==2&&!entity(saved(e),bot)["ready"].get<bool>(),"Book 20.1 entry/readiness ledger failed");
    // 20.2 / exercise 7: Molgur -> Plant -> Molgur, exactly three water, two camps.
    e=game();s=fixture(e);int plant=camp(s,0,0,"chuckwagon"),molgur=put(s,"cornelius_ashby_railroad_baron",0,0);
    first=camp(s,1,0,"gatling_emplacement");second=camp(s,1,1,"gatling_emplacement");s["players"][0]["water"]=3;load(e,s);
    action(e,0,"activate",molgur);choice(e,first);action(e,0,"activate",plant);action(e,0,"activate",molgur);choice(e,second);
    check(view(e)["players"][0]["water"]==0&&entity(saved(e),first)["destroyed"].get<bool>()&&entity(saved(e),second)["destroyed"].get<bool>()&&!e.IsFinished(),"Book 20.2 must destroy two camps, not three");
    // 20.9: empty Oasis/Team entry loop satisfies Nest without any water for plays.
    e=game();s=fixture(e);camp(s,0,0,"trading_post");int nest=camp(s,0,1,"bordello");team=put(s,"sarah_winnemucca",0);s["players"][0]["water"]=1;load(e,s);
    auto oasisPlay=[&](){for(const auto& a:legal(e))if(a["command"]["type"]=="play"&&a["command"].value("card",0)==team&&a["command"].value("column",-1)==0){act(e,0,a["command"]);return;}throw std::runtime_error("Missing free Trading Post deployment");};
    oasisPlay();action(e,0,"activate",team);choice(e,team);oasisPlay();action(e,0,"activate",nest);choice(e);
    check(view(e)["players"][0]["water"]==0&&saved(e)["players"][0]["entered"]==2,"Book 20.9 entry-loop budget failed");
    // 20.15: Curfew is an event action and therefore compatible with Resonator.
    e=game();s=fixture(e);int resonator=camp(s,0,0,"church_bell_tower"),truce=put(s,"curfew",0),last=camp(s,1,0,"gatling_emplacement");
    entity(s,last)["damage"]=1;put(s,"bartender",1,0);for(int c=1;c<3;++c){int ruin=camp(s,1,c,"gatling_emplacement");entity(s,ruin)["damage"]=2;entity(s,ruin)["destroyed"]=true;entity(s,ruin)["ready"]=false;}
    s["players"][0]["water"]=3;load(e,s);action(e,0,"play",truce);action(e,0,"activate",resonator);choice(e,last);
    check(e.Winner()==0&&view(e)["players"][0]["water"]==0,"Book 20.15 Truce/Resonator finish failed");
}

void readinessAndSourceContracts() {
    // Rules pp. 8/11: a damaged camp can act; restoration never refunds its use.
    auto e=game();auto s=fixture(e);int gun=camp(s,0,0,"gatling_emplacement"),bot=put(s,"blacksmith",0,1);
    entity(s,gun)["damage"]=1;load(e,s);check(offersAbility(e,gun),"Damaged camp lost its ordinary ability");
    action(e,0,"activate",gun);choice(e);action(e,0,"activate",bot);choice(e,gun);
    check(entity(saved(e),gun)["damage"]==0&&!offersAbility(e,gun),"Restoration refunded a used camp activation");
    // Restored Karli's trait works at once, while her own activation remains used.
    e=game();s=fixture(e);int karli=put(s,"quanah_parker",0,0,false,1);bot=put(s,"blacksmith",0,1);
    int recruit=put(s,"vigilante",0);load(e,s);action(e,0,"activate",bot);choice(e,karli);
    check(!offersAbility(e,karli),"Restoring Karli incorrectly readied her");action(e,0,"play",recruit);
    check(entity(saved(e),recruit)["ready"].get<bool>(),"Restored Karli did not enable immediate entry readiness");
    // Granted punk abilities require readiness, just like printed abilities.
    for(bool immediate:{false,true}) {
        e=game();s=fixture(e);int armory=camp(s,0,0,"gunsmith");put(s,"wyatt_earp",0,1);
        if(immediate)put(s,"quanah_parker",0,2);load(e,s);action(e,0,"activate",armory);choice(e);
        int punk=0;auto after=saved(e);for(const auto& col:after["players"][0]["columns"])for(int id:col)if(entity(after,id)["punk"].get<bool>())punk=id;
        check(punk&&offersAbility(e,punk,100)==immediate&&offersAbility(e,punk,101)==immediate,"Argo/Armory punk grants bypassed readiness or ignored Karli");
    }
    // A single ready card cannot spend both printed boxes without another effect.
    e=game();s=fixture(e);int outpost=camp(s,0,0,"stagecoach_station");put(s,"bartender",0,0,false,1);load(e,s);
    action(e,0,"activate",outpost,0);check(!offersAbility(e,outpost,1),"Two Stagecoach Station boxes bypassed shared readiness");
    // Church Bell Tower's whole-turn restriction survives Vera and counts zero-cost uses.
    e=game();s=fixture(e);int resonator=camp(s,0,0,"church_bell_tower"),muse=put(s,"bartender",0,0);put(s,"charles_goodnight",0,1);load(e,s);
    action(e,0,"activate",resonator);choice(e);check(!offersAbility(e,resonator)&&!offersAbility(e,muse),"Vera bypassed Church Bell Tower's whole-turn lock");
    load(e,s);action(e,0,"activate",muse);check(!offersAbility(e,resonator),"Zero-water activation failed to prohibit Church Bell Tower");
    // Indirect restoration still belongs to the activating camp (FAQ pp.12/13).
    for(const std::string key:{"smuggler_s_landing","apothecary"}) {
        e=game();s=fixture(e);int source=camp(s,0,0,key),patient=camp(s,0,1,"gatling_emplacement");
        entity(s,source)["damage"]=1;entity(s,patient)["damage"]=1;
        int gunner=put(s,"gatling_gunner",0,key=="smuggler_s_landing"?1:-1);
        if(key=="smuggler_s_landing")entity(s,gunner)["entered_turn"]=s["turn"];
        else {detach(s,gunner);entity(s,gunner)["owner"]=-1;entity(s,gunner)["zone"]="deck";s["deck"].insert(s["deck"].begin(),gunner);}
        load(e,s);action(e,0,"activate",source);
        choice(e,-1,"Gatling Gunner:"); // Select the Market entry or Lab's revealed junk before its heal target.
        auto pending=saved(e);std::set<int> targets;for(const auto& o:pending["choice"]["options"])for(const auto& t:o["tasks"])targets.insert(t.value("target",0));
        check(targets==std::set<int>{patient},key+": indirect junk restored its own source");choice(e,patient);
        check(entity(saved(e),source)["damage"]==1&&entity(saved(e),patient)["damage"]==0,"Indirect restoration resolved incorrectly");
    }
    // Killing a camp leaves its people in place (including protected damaged ones).
    e=game();s=fixture(e);int molgur=put(s,"cornelius_ashby_railroad_baron",0,0),campId=camp(s,1,0,"gatling_emplacement"),person=put(s,"bartender",1,0,false,1);
    load(e,s);action(e,0,"activate",molgur);choice(e,campId);
    check(entity(saved(e),person)["zone"]=="board"&&entity(saved(e),person)["damage"]==1,"Camp destruction removed or changed its surviving person");
}
