#include "OldWestRules.h"
#include "OldWestFieldActions.h"
#include "json.hpp"
#include <algorithm>
#include <fstream>
#include <functional>
#include <iostream>
#include <random>
#include <set>
#include <stdexcept>
#include <string>

using J=nlohmann::ordered_json;
using oldwest::Engine;
std::string catalog;
J definitions;
int assertions=0;
void check(bool result,const std::string& message) {
    ++assertions;if(!result)throw std::runtime_error(message);
}
J saved(const Engine& e){return J::parse(e.SaveJson());}
J view(const Engine& e,int p=0){return J::parse(e.ViewJson(p));}
J journal(const Engine& e){return view(e)["history"];}
J legal(const Engine& e,int p=0){return J::parse(e.LegalActionsJson(p));}
void load(Engine& e,const J& s){std::string error;bool ok=e.RestoreJson(s.dump(),&error);check(ok,"Fixture failed: "+error);}
void act(Engine& e,int p,J cmd){cmd["revision"]=view(e,p)["revision"];J result=J::parse(e.Apply(p,cmd.dump()));check(result.value("ok",false),"Rejected legal command: "+cmd.dump()+"\n"+result.dump());}
void action(Engine& e,int p,const std::string& type,int card=0,int ability=-1) {
    for(const auto& a:legal(e,p)){const auto& c=a["command"];if(c["type"]==type&&(!card||c.value("card",c.value("source",0))==card)&&(ability<0||c.value("ability",-1)==ability)){act(e,p,c);return;}}
    throw std::runtime_error("Missing action "+type+" for "+std::to_string(card));
}
void choice(Engine& e,int target=-1,const std::string& substring="") {
    auto s=saved(e);check(!s["choice"].is_null(),"Expected a choice");
    for(const auto& o:s["choice"]["options"]){bool match=target<0;
        if(target>=0)for(const auto& t:o["tasks"])if(t.value("target",-9)==target)match=true;
        if(match&&(substring.empty()||o["label"].get<std::string>().find(substring)!=std::string::npos)){act(e,s["choice"]["player"],{{"type","choose"},{"option",o["id"]}});return;}}
    throw std::runtime_error("No matching choice "+substring+" target "+std::to_string(target));
}
void settle(Engine& e) {for(int n=0;n<100&&!e.IsFinished()&&!saved(e)["choice"].is_null();++n)choice(e);check(e.IsFinished()||saved(e)["choice"].is_null(),"Choice sequence never ended");}
Engine game(std::uint64_t seed=1) {
    Engine e(catalog,seed,R"({"first_player":0})");
    for(int p=0;p<2;++p)act(e,p,legal(e,p)[0]["command"]);
    settle(e);return e;
}
void erase(J& array,int id){for(auto i=array.begin();i!=array.end();)if(*i==id)i=array.erase(i);else++i;}
J& entity(J& s,int id){return s["cards"][std::to_string(id)];}
const J& entity(const J& s,int id){return s["cards"][std::to_string(id)];}
void detach(J& s,int id) {
    erase(s["deck"],id);erase(s["discard"],id);
    for(auto& p:s["players"]){erase(p["hand"],id);for(auto& c:p["columns"])erase(c,id);for(auto& q:p["queue"])if(q==id)q=0;}
}
int put(J& s,const std::string& card,int p,int column=-1,bool punk=false,int damage=0,bool ready=true) {
    int id=0;for(const auto& e:s["cards"])if(e["card_id"]==card&&e["zone"]!="board"){id=e["id"];break;}
    if(!id)throw std::runtime_error("Missing fixture card "+card);detach(s,id);auto& e=entity(s,id);e["owner"]=p;e["zone"]=column<0?"hand":"board";e["punk"]=punk;e["damage"]=damage;e["ready"]=ready&&damage==0;e["uses"]=0;e["destroyed"]=false;
    if(column<0)s["players"][p]["hand"].push_back(id);else s["players"][p]["columns"][column].insert(s["players"][p]["columns"][column].begin(),id);
    return id;
}
int camp(J& s,int p,int column,const std::string& card) {
    for(int id:s["players"][p]["columns"][column]) {
        std::string previous=entity(s,id)["card_id"];for(const auto& d:definitions)if(d["id"]==previous&&d["type"]=="camp"){entity(s,id)["card_id"]=card;entity(s,id)["damage"]=0;entity(s,id)["destroyed"]=false;entity(s,id)["ready"]=true;return id;}
    }throw std::runtime_error("No fixture camp");
}
J fixture(Engine& e) {
    J s=saved(e);s["tasks"]=J::array();s["choice"]=nullptr;s["status"]="actions";s["active_player"]=0;s["turn"]=5;
    for(int p=0;p<2;++p){s["players"][p]["water"]=20;for(int c=0;c<3;++c)camp(s,p,c,"gatling_emplacement");}
    return s;
}

void damagedCampTurnCycle() {
    for(const auto& key:{"gatling_emplacement","bunkhouse","telegraph_office","general_store","logging_camp"}) {
        auto e=game();auto s=fixture(e);int id=camp(s,0,0,key);entity(s,id)["damage"]=1;entity(s,id)["ready"]=false;entity(s,id)["uses"]=1;
        load(e,s);action(e,0,"end_turn");action(e,1,"end_turn");
        auto card=view(e)["players"][0]["columns"][0][0];
        check(card["damage"]==1&&card["ready"].get<bool>(),std::string(key)+" remains damaged but readies after a complete round");
        auto actions=legal(e);bool offered=false;
        for(const auto& a:actions)if(a["command"].value("source",0)==id&&a["command"].value("type",std::string())=="activate")offered=true;
        check(offered,std::string(key)+" has a legal damaged activation after cleanup");
        check(card["ability_availability"][0]["available"].get<bool>(),std::string(key)+" owning UI shows available damaged ability");
        auto opponent=view(e,1)["players"][0]["columns"][0][0];
        check(!opponent.contains("ability_availability"),"Opponent cannot query private prerequisites");
        action(e,0,"activate",id);settle(e);
        if(!e.IsFinished())check(!entity(saved(e),id)["ready"].get<bool>(),std::string(key)+" cannot reactivate just because it is a camp");
    }
    // Every camp's ready state survives damage/cleanup, even when a printed
    // prerequisite independently prevents its ability (notably Army Fort).
    for(const auto& d:definitions)if(d["type"]=="camp") {
        auto e=game();auto s=fixture(e);int id=camp(s,0,0,d["id"]);entity(s,id)["damage"]=1;entity(s,id)["ready"]=false;
        load(e,s);action(e,0,"end_turn");action(e,1,"end_turn");
        check(entity(saved(e),id)["ready"].get<bool>(),d["id"].get<std::string>()+" damaged camp resets readiness");
    }
    auto e=game();auto s=fixture(e);int id=camp(s,0,0,"gatling_emplacement");entity(s,id)["damage"]=1;s["players"][0]["water"]=0;load(e,s);
    auto ability=view(e)["players"][0]["columns"][0][0]["ability_availability"][0];
    check(!ability["available"].get<bool>()&&ability["reason"]=="Not enough water\nCost: 2 water · Available: 0\nNeed 2 more water","Damaged ready camp explains water requirement");
}

void warRoomEventPlay() {
    auto e=game();auto s=fixture(e);const int room=camp(s,0,0,"cattlemen_s_club"),bomb=put(s,"cannonade",0);
    s["players"][0]["water"]=3;
    auto status=[&](){const auto v=view(e);for(const auto& c:v["players"][0]["hand"])if(c["id"]==bomb)return c.at("play_availability");throw std::runtime_error("Cannonade missing");};
    auto offered=[&](){for(const auto& a:legal(e))if(a["category"]=="play_event"&&a["command"]["card"]==bomb)return a;return J(nullptr);};
    for(bool ready:{true,false})for(int damage:{0,1}) {
        auto state=s;entity(state,room)["ready"]=ready;entity(state,room)["damage"]=damage;load(e,state);
        check(status()["cost"]==3&&status()["available"].get<bool>(),"Cattlemen's Club passively discounts Cannonade to three regardless of camp readiness/damage");
        check(!offered().is_null()&&offered()["cost"]==3&&offered()["event_slot"]==2,"Discounted Cannonade offers position three and costs three");
        action(e,0,"play",bomb);
        check(saved(e)["players"][0]["water"]==0&&saved(e)["players"][0]["queue"][2]==bomb,"Cannonade pays exactly three and enters position three");
        check(entity(saved(e),room)["ready"]==ready,"Passive event discount does not consume camp readiness");
    }
    load(e,s);for(const auto& a:legal(e))if(a["command"].value("source",0)==room)
        check(a["cost"]==2,"Cattlemen's Club discount does not reduce Raid activation cost");
    auto poor=s;poor["players"][0]["water"]=2;load(e,poor);
    check(status()["cost"]==3&&!status()["available"].get<bool>()&&status()["reason"]=="Needs 3 water; you have 2"&&offered().is_null(),"Unaffordable event explains discounted requirement");
    auto ruined=s;entity(ruined,room)["destroyed"]=true;entity(ruined,room)["damage"]=2;entity(ruined,room)["ready"]=false;load(e,ruined);
    check(status()["cost"]==4&&!status()["available"].get<bool>()&&offered().is_null(),"Ruined Cattlemen's Club gives no discount");
    auto occupied=s;const int other=put(occupied,"gold_rush",0);detach(occupied,other);entity(occupied,other)["zone"]="queue";occupied["players"][0]["queue"][2]=other;load(e,occupied);
    check(!status()["available"].get<bool>()&&status()["reason"]=="No open event space at or after position 3"&&offered().is_null(),"Occupied event slot explains why an affordable event cannot play");
    auto away=s;away["active_player"]=1;load(e,away);
    check(!status()["available"].get<bool>()&&status()["cost"]==3&&offered().is_null(),"Off-turn hand still displays discounted cost but cannot play");
    check(!view(e,1)["players"][0].contains("hand"),"Event availability never exposes the opponent's hand");
    auto cheap=s;const int event=put(cheap,"hard_winter",0);cheap["players"][0]["water"]=0;load(e,cheap);
    bool free=false;for(const auto& a:legal(e))if(a["category"]=="play_event"&&a["command"]["card"]==event)free=a["cost"]==0;
    check(free,"Cattlemen's Club can reduce a one-water event to zero");
}

void setupAndAtomicity() {
    Engine e(catalog,11,R"({"first_player":0})");
    check(legal(e).size()==120,"All ordered choices of three camps must be offered");
    act(e,0,legal(e)[0]["command"]);
    check(view(e,1)["players"][0]["columns"][0].empty(),"Opponent's camp selection leaked");
    auto cmd=legal(e,1)[0]["command"];act(e,1,cmd);
    auto s=saved(e);int opening=0;auto v=view(e);
    for(const auto& col:v["players"][0]["columns"])for(const auto& c:col)for(const auto& d:definitions)if(c["card_id"]==d["id"])opening+=d.value("starting_cards",0);
    check(view(e)["players"][0]["hand_count"]==opening+1,"Opening hand must include camp total and first replenishment draw");
    check(view(e)["players"][0]["water"]==1,"First player gets only one water");
    check(view(e)["log"].back()["type"]=="water"&&view(e)["log"].back()["detail"]=="1","First refill must publicly present exactly one water");
    check(!view(e)["players"][1].contains("hand"),"Opponent hand leaked");
    auto old=e.SaveJson();check(!J::parse(e.Apply(1,R"({"type":"end_turn"})"))["ok"].get<bool>(),"Out-of-turn action accepted");check(e.SaveJson()==old,"Rejected action changed state");
    check(!J::parse(e.Apply(0,R"({"type":"end_turn","revision":-1})"))["ok"].get<bool>(),"Stale command accepted");
    check(!J::parse(e.Apply(0,"{bad json"))["ok"].get<bool>(),"Bad JSON accepted");check(e.SaveJson()==old,"Bad request changed RNG or state");
    J bad=s;bad["deck"].push_back(bad["deck"][0]);check(!e.RestoreJson(bad.dump()),"Corrupt duplicate card save accepted");check(e.SaveJson()==old,"Bad restore changed state");
    action(e,0,"end_turn");check(view(e)["players"][1]["water"]==3,"Second player's first turn gets three water");
    check(view(e)["log"].back()["type"]=="water"&&view(e)["log"].back()["detail"]=="3","Later refill must publicly present exactly three water");
}

void protectionAndPunks() {
    auto e=game();J s=fixture(e);int front=put(s,"bartender",1,0,true),rear=put(s,"prospector",1,0);auto& col=s["players"][1]["columns"][0];erase(col,front);col.insert(col.begin(),front);
    int gunner=put(s,"gatling_gunner",0,0);load(e,s);
    auto publicBefore=e.ViewJson(0);auto hidden=s;entity(hidden,front)["card_id"]="quanah_parker";load(e,hidden);check(e.ViewJson(0)==publicBefore,"Punk underlying identity leaked through view");
    // Punks must not switch on hidden Karli, Argo, or Vera traits.
    int recruit=put(hidden,"widow_with_a_shotgun",1);hidden["active_player"]=1;load(e,hidden);action(e,1,"play",recruit);check(!entity(saved(e),recruit)["ready"].get<bool>(),"A punk granted hidden Karli readiness");
    load(e,s);action(e,0,"activate",gunner);check(entity(saved(e),front)["zone"]=="deck","Destroyed punk must return to deck");check(entity(saved(e),rear)["damage"]==0,"Area injury spilled through the former front card");check(saved(e)["deck"][0]==front,"Punk did not go on top of deck");
    check(view(e)["players"][1]["columns"][0][0]["id"]==rear,"Surviving rear person should become exposed");
}

// Independent oracle: damage changes readiness/traits, never column protection.
void damagedProtectionMatrix() {
    for(const auto& definition:definitions)if(definition["type"]=="person")for(int hurt:{0,1})for(int side:{0,1}) {
        auto e=game();J s=fixture(e);const int attacker=1-side;
        int guard=put(s,definition["id"],side,1,false,hurt),rear=camp(s,side,1,"general_store");
        int gun=camp(s,attacker,0,"gatling_emplacement");s["active_player"]=attacker;load(e,s);
        const auto before=view(e,attacker);
        const auto& column=before["players"][side]["columns"][1];
        check(!column[0]["protected"].get<bool>()&&column[1]["protected"].get<bool>(),"Living guard lost protection: "+definition["id"].get<std::string>());
        check(column[1]["protected_by"][0]["id"]==guard&&column[1]["protected_by"][0]["damage"]==hurt,"Public guard explanation mismatches condition");
        action(e,attacker,"activate",gun);
        std::set<int> offered;for(const auto& o:saved(e)["choice"]["options"].get<J>())for(const auto& t:o["tasks"])offered.insert(t.value("target",0));
        check(offered.count(guard)&&!offered.count(rear),"Normal damage bypassed a living guard");
        choice(e,guard);
        const auto after=view(e,attacker);
        check(after["players"][side]["columns"][1].back()["protected"].get<bool>()==!hurt,"Camp exposure must change only when guard is destroyed");
    }
    // Rear damaged people and damaged advanced camps also remain protectors.
    auto e=game();J s=fixture(e);int rear=put(s,"bartender",1,0,false,1),front=put(s,"duelist",1,0,false,1);
    int jug=camp(s,1,1,"riverboat"),behind=put(s,"prospector",1,1);entity(s,jug)["damage"]=1;entity(s,jug)["advance"]=2;
    s["players"][1]["columns"][1]=J::array({jug,behind});load(e,s);
    auto v=view(e);check(v["players"][1]["columns"][0][1]["protected"].get<bool>(),"Damaged rear person lost protection");
    check(v["players"][1]["columns"][0][2]["protected_by"].size()==2,"Two damaged guards not explained");
    check(v["players"][1]["columns"][1][1]["protected"].get<bool>(),"Damaged advanced camp stopped protecting");
    int sniper=put(s,"annie_oakley",0,0);load(e,s);action(e,0,"activate",sniper);choice(e,behind);
    check(entity(saved(e),behind)["damage"]==1,"Annie Oakley's any-card damage failed to bypass protection");
    s["players"][1]["exposed"]=true;load(e,s);v=view(e);
    for(const auto& col:v["players"][1]["columns"])for(const auto& c:col)check(!c["protected"].get<bool>()&&c["protected_by"].empty(),"Explicit exposure retained a guard");
}

void mutantScreenshotSequence() {
    auto e=game();J s=fixture(e);
    int mutant=put(s,"doc_holliday",0,1),friendId=put(s,"widow_with_a_shotgun",0,2,false,1);
    int supply=camp(s,1,0,"general_store"),laser=camp(s,1,1,"nitro_works"),lab=camp(s,1,2,"apothecary");
    int vanguard=put(s,"duelist",1,1,false,1),muse=put(s,"bartender",1,2,false,1);
    int punk=put(s,"prospector",1,0,true),railgun=camp(s,0,0,"gatling_emplacement");load(e,s);
    action(e,0,"activate",railgun);choice(e,punk);
    check(entity(saved(e),punk)["zone"]=="deck","Screenshot's Punk should have been destroyed");
    const J formation=saved(e);
    for(bool doDamage:{false,true})for(bool doRestore:{false,true}) {
        load(e,formation);action(e,0,"activate",mutant);
        auto pending=saved(e);std::set<int> offered;
        for(const auto& o:pending["choice"]["options"])for(const auto& t:o["tasks"])offered.insert(t.value("target",0));
        check(offered==std::set<int>({supply,vanguard,muse}),"Doc Holliday screenshot targets differ from the printed rules");
        auto publicChoice=view(e)["choice"];const auto help=publicChoice.value("help",std::string());
        check(help.find("Duelist [damaged]")!=std::string::npos&&help.find("Bartender [damaged]")!=std::string::npos,"Missing damaged-guard explanation");
        check(!view(e,1)["choice"].contains("help"),"Choice-only help sent to nonchoosing player");
        bool destructiveHint=false;for(const auto& a:legal(e))if(a["label"].get<std::string>().find("Bartender")!=std::string::npos)destructiveHint=a.value("target_detail",std::string()).find("DAMAGED · This hit destroys it")!=std::string::npos;
        check(destructiveHint,"Damage target doesn't disclose lethal second hit");
        if(doDamage)choice(e,supply);else choice(e,-1,"Skip");
        check(entity(saved(e),mutant)["damage"]==0,"Doc Holliday self-damaged before restore choice");
        if(doRestore)choice(e,friendId);else choice(e,-1,"Skip");
        auto final=saved(e);
        check(entity(final,supply)["damage"]==int(doDamage),"Doc Holliday optional damage wrong");
        check(entity(final,friendId)["damage"]==int(!doRestore)&&!entity(final,friendId)["ready"].get<bool>(),"Doc Holliday optional restore/readiness wrong");
        check(entity(final,mutant)["damage"]==1&&!entity(final,mutant)["ready"].get<bool>(),"Doc Holliday must damage itself even if both effects skipped");
        check(entity(final,laser)["damage"]==0&&entity(final,lab)["damage"]==0,"Damage spilled through a guard");
    }
    load(e,formation);action(e,0,"activate",mutant);choice(e,muse);choice(e,-1,"Skip");
    auto v=view(e);check(!v["players"][1]["columns"][2].back()["protected"].get<bool>(),"Destroying damaged Bartender must expose Apothecary");
    // Playing Doc Holliday is not activation: without Karli it enters unready.
    s=fixture(e);int incoming=put(s,"doc_holliday",0);load(e,s);action(e,0,"play",incoming);
    check(saved(e)["choice"].is_null()&&!entity(saved(e),incoming)["ready"].get<bool>(),"Doc Holliday activated on ordinary entry");
}

void raidersAndVictory() {
    auto e=game();J s=fixture(e);int garage=camp(s,0,0,"cattle_ranch");int raiders=s["players"][0]["stampede"];
    s["players"][0]["queue"][0]=raiders;entity(s,raiders)["zone"]="queue";load(e,s);action(e,0,"activate",garage);
    check(view(e)["choice"]["player"]==1,"Stampede camp target belongs to defender");check(legal(e,0).empty(),"Attacker can act during defender choice");choice(e);check(entity(saved(e),raiders)["zone"]=="special","Stampede not returned to special supply");
    s=fixture(e);int vanguard=put(s,"duelist",0,0);int last=0;
    for(int c=0;c<3;++c){int id=camp(s,1,c,"gatling_emplacement");entity(s,id)["damage"]=c<2?2:1;entity(s,id)["destroyed"]=c<2;entity(s,id)["ready"]=c==2;last=id;}
    load(e,s);action(e,0,"activate",vanguard);choice(e,last);
    check(e.IsFinished()&&e.Winner()==0,"Lethal Duelist did not win immediately");check(saved(e)["choice"].is_null(),"Duelist retaliated after the game ended");
}

void eventClock() {
    auto e=game();J s=fixture(e);int banish=put(s,"run_out_of_town",0),strafe=put(s,"ambush",0);detach(s,banish);detach(s,strafe);
    s["players"][0]["queue"]=J::array({0,banish,strafe});entity(s,banish)["zone"]="queue";entity(s,strafe)["zone"]="queue";s["active_player"]=1;
    load(e,s);action(e,1,"end_turn");check(saved(e)["players"][0]["queue"][0]==banish,"Slot two event must advance to one");check(entity(saved(e),banish)["zone"]=="queue","New slot one event resolved a turn early");
    s=fixture(e);int scout=put(s,"rustler",0,0),r=s["players"][0]["stampede"];s["players"][0]["queue"]=J::array({banish,r,strafe});entity(s,r)["zone"]="queue";load(e,s);action(e,0,"activate",scout);check(saved(e)["players"][0]["queue"][1]==r,"Stampede advanced through occupied slot");
}

void restoreAndMimic() {
    auto e=game();J s=fixture(e);int mimic=put(s,"con_man",0,0),mutant=put(s,"doc_holliday",0,1),friendId=put(s,"widow_with_a_shotgun",0,2,false,1);
    load(e,s);action(e,0,"activate",mimic);choice(e,-1,"Doc Holliday:");choice(e,-1,"Skip");choice(e,friendId);
    check(entity(saved(e),mimic)["damage"]==1,"Copied self-damage must affect Con Man");check(entity(saved(e),mutant)["damage"]==0,"Copied source was damaged");check(entity(saved(e),mutant)["ready"].get<bool>(),"Copy exhausted original person");check(!entity(saved(e),friendId)["ready"].get<bool>(),"Ordinary restore readied person");
    s=fixture(e);int garden=camp(s,0,0,"hot_springs");entity(s,friendId)["damage"]=1;load(e,s);action(e,0,"activate",garden);choice(e,friendId);check(entity(saved(e),friendId)["ready"].get<bool>(),"Hot Springs must ready restored person");
}

void directTargetActions() {
    auto e=game();J s=fixture(e);
    int labor=camp(s,0,0,"railroad_work_camp"),person=put(s,"widow_with_a_shotgun",0,1),hurt=put(s,"doc_holliday",0,2,false,1);
    load(e,s);action(e,0,"activate",labor);
    auto click=[&](int id) {
        J matches=J::array();
        for(const auto& a:legal(e))if(a.value("target",0)==id)matches.push_back(a);
        check(matches.size()==1,"Direct target must identify one exact legal choice");
        check(!matches[0].contains("tasks"),"Direct target leaked effect tasks");
        act(e,0,matches[0]["command"]);
    };
    check(legal(e,1).empty(),"Opponent received private response actions");
    click(person);click(hurt);
    check(entity(saved(e),person)["zone"]=="discard","Railroad Work Camp must sacrifice selected person");
    check(entity(saved(e),hurt)["damage"]==0,"Direct restore did not restore selected card");
}

void fullBoardAndResources() {
    auto e=game();J s=fixture(e);std::vector<std::string> people={"bartender","hellfire_preacher","prospector","widow_with_a_shotgun","vigilante","bounty_hunter"};
    for(int i=0;i<6;++i)put(s,people[i],0,i/2);int incoming=put(s,"annie_oakley",0);load(e,s);
    bool replacement=false;for(const auto& a:legal(e))if(a["command"].value("card",0)==incoming&&a["command"]["type"]=="play"){check(a["command"].contains("replace"),"Full-board placement lacks mandatory replacement");replacement=true;act(e,0,a["command"]);break;}
    check(replacement,"No full-board replacement offered");int n=0;auto v=view(e);for(const auto& c:v["players"][0]["columns"])for(const auto& x:c)if(x["type"]=="person")++n;check(n==6,"Full-board replacement changed population");
    s=fixture(e);int silo=s["players"][0]["silo"];load(e,s);action(e,0,"silo");action(e,0,"junk",silo);check(view(e)["players"][0]["water"]==20,"Silo storage and junk net should be zero");check(entity(saved(e),silo)["zone"]=="special","Silo must never enter discard");
}

void exhaustionAndDeterminism() {
    auto e=game(42);J s=fixture(e);auto deck=s["deck"];s["deck"]=J::array({deck[0]});for(std::size_t i=1;i<deck.size();++i){int id=deck[i];s["discard"].push_back(id);entity(s,id)["zone"]="discard";}
    load(e,s);action(e,0,"draw");check(saved(e)["reshuffles"]==1&&!e.IsFinished(),"First deck exhaustion must immediately reshuffle");
    s["reshuffles"]=1;load(e,s);action(e,0,"draw");check(view(e)["status"]=="draw","Second exhaustion must immediately end in draw");
    int obelisk=camp(s,1,0,"land_office");(void)obelisk;load(e,s);action(e,0,"draw");check(e.Winner()==1,"Land Office's actual final-card draw must precede draw game");
    auto a=game(1729),b=game(1729);check(a.SaveJson()==b.SaveJson(),"Same seed must reproduce same game");
    for(int i=0;i<12&&!a.IsFinished();++i){int p=view(a)["active_player"];auto cmd=legal(a,p)[0]["command"];act(a,p,cmd);act(b,p,cmd);check(a.SaveJson()==b.SaveJson(),"Replay diverged");}
}

void concealedCardHandles() {
    auto a=game(),b=game();J base=fixture(a);int rouser=put(base,"ringleader",0,0);
    int top=base["deck"][0];J alternate=base;
    std::swap(alternate["deck"][0],alternate["deck"][1]);
    load(a,base);load(b,alternate);action(a,0,"activate",rouser,0);action(b,0,"activate",rouser,0);
    choice(a);choice(b);
    check(a.ViewJson(0)==b.ViewJson(0)&&a.ViewJson(1)==b.ViewJson(1),"Hidden deck identities changed a player's view when making the same punk");
    J snapshot=saved(a);int punk=0;for(const auto& col:snapshot["players"][0]["columns"])for(int x:col)if(entity(snapshot,x)["punk"].get<bool>())punk=x;
    check(punk!=top,"A new punk reused its catalog-order deck handle");
    J s=saved(a);detach(s,punk);entity(s,punk)["zone"]="deck";entity(s,punk)["owner"]=-1;entity(s,punk)["punk"]=false;s["deck"].insert(s["deck"].begin(),punk);
    load(a,s);action(a,0,"draw");
    check(!saved(a)["cards"].contains(std::to_string(punk)),"A card drawn from the concealed deck retained a publicly trackable old handle");
    check(J::parse(a.ValidateJson())["ok"].get<bool>(),"Reidentifying a concealed card violated conservation");
}

void masqueradeInspectionSchema() {
    auto e=game();J s=fixture(e);int masquerade=camp(s,0,0,"wanted_poster_board"),eventPunk=put(s,"run_out_of_town",0,0,true),personPunk=put(s,"widow_with_a_shotgun",0,1,true),enemyPunk=put(s,"con_man",1,0,true);
    load(e,s);
    auto cardView=[&](int viewer,int owner,int id){J v=view(e,viewer);for(const auto& col:v["players"][owner]["columns"])for(const auto& card:col)if(card["id"]==id)return card;throw std::runtime_error("Missing visible card");};
    for(int id:{eventPunk,personPunk}) {
        J own=cardView(0,0,id),other=cardView(1,0,id);
        check(own["name"]=="Punk"&&own["type"]=="person"&&own["punk"].get<bool>(),"Wanted Poster Board peek changed the punk's renderer-facing identity/type");
        check(!own.contains("card_id")&&own.contains("private_peek"),"Wanted Poster Board inspection is not separated from battlefield identity");
        check(own["private_peek"]["card_id"]==entity(s,id)["card_id"],"Owner's authorized peek lost the card identity");
        check(!other.contains("private_peek")&&!other.contains("card_id")&&other["name"]=="Punk"&&other["type"]=="person","Wanted Poster Board's private face leaked to the opponent");
    }
    check(cardView(0,0,eventPunk)["private_peek"]["type"]=="event","An inspected event punk's hidden card type was lost");
    check(cardView(0,0,personPunk)["private_peek"]["type"]=="person","An inspected person punk's hidden card type was lost");
    check(!cardView(0,1,enemyPunk).contains("private_peek")&&!cardView(1,1,enemyPunk).contains("private_peek"),"Wanted Poster Board authorized inspecting the wrong player's punk");
    bool canFlipPerson=false;for(const auto& a:legal(e))if(a["command"]["type"]=="flip") {
        check(a["command"]["card"]!=eventPunk,"An inspected event can be flipped into a person");
        if(a["command"]["card"]==personPunk)canFlipPerson=true;
    }
    check(canFlipPerson,"Wanted Poster Board inspection lost the legal person-flip action");
    check(cardView(0,0,personPunk)["private_peek"].value("flip_available",false),"Affordable person inspection must offer its flip");
    check(!cardView(0,0,eventPunk)["private_peek"].value("flip_available",true)&&!cardView(0,0,eventPunk)["private_peek"].contains("flip_cost"),"Event inspection must explain that it cannot flip without offering a cost");
    J unavailable=s;unavailable["players"][0]["water"]=0;load(e,unavailable);
    J peek=cardView(0,0,personPunk)["private_peek"];
    check(!peek.value("flip_available",true)&&peek["flip_cost"]==2&&peek["flip_reason"].get<std::string>().find("Needs 2 water")!=std::string::npos,"Unaffordable flip inspection must report the effective cost and reason");
    for(const auto& a:legal(e))check(a["command"]["type"]!="flip","Unaffordable punk was offered for flipping");
    unavailable=s;unavailable["active_player"]=1;load(e,unavailable);
    check(!cardView(0,0,personPunk)["private_peek"].value("flip_available",true),"Opponent-turn inspection incorrectly permits flipping");
    unavailable=s;unavailable["players"][0]["blocked_plays"].push_back("widow_with_a_shotgun");load(e,unavailable);
    check(cardView(0,0,personPunk)["private_peek"]["flip_reason"].get<std::string>().find("Pony Express Station")!=std::string::npos,"Play-restricted punk lacks a flip explanation");
    unavailable=s;unavailable["players"][0]["water"]=0;
    int ruin=unavailable["players"][0]["columns"][1].back();entity(unavailable,ruin)["destroyed"]=true;entity(unavailable,ruin)["damage"]=2;entity(unavailable,ruin)["ready"]=false;load(e,unavailable);
    peek=cardView(0,0,personPunk)["private_peek"];
    check(peek.value("flip_available",false)&&peek["flip_cost"]==0,"Inspection must include Widow with a Shotgun's free play beside a ruin");
    load(e,s);
    const auto beforeOpponent=e.ViewJson(1);J alternate=s;entity(alternate,eventPunk)["card_id"]="poker_night";load(e,alternate);
    check(e.ViewJson(1)==beforeOpponent,"Changing a privately inspected hidden face altered the opponent's view");
    check(cardView(0,0,eventPunk)["private_peek"]["card_id"]=="poker_night","Authorized private inspection did not reflect the actual hidden face");
    J damaged=s;entity(damaged,masquerade)["damage"]=1;load(e,damaged);
    check(cardView(0,0,eventPunk).contains("private_peek"),"Damaging Wanted Poster Board incorrectly disabled its camp trait");
    entity(damaged,masquerade)["damage"]=2;entity(damaged,masquerade)["destroyed"]=true;entity(damaged,masquerade)["ready"]=false;load(e,damaged);
    check(!cardView(0,0,eventPunk).contains("private_peek"),"Destroyed Wanted Poster Board continued authorizing private inspection");
    load(e,s);const J oldColumn=s["players"][0]["columns"][1];action(e,0,"flip",personPunk);J flipped=cardView(0,0,personPunk);
    check(!flipped["punk"].get<bool>()&&flipped["card_id"]=="widow_with_a_shotgun"&&flipped["name"]=="Widow with a Shotgun"&&flipped["type"]=="person"&&!flipped.contains("private_peek"),"Actually flipping a punk failed to replace its battlefield identity");
    check(flipped["ready"].get<bool>()&&saved(e)["players"][0]["columns"][1]==oldColumn,"Wanted Poster Board flip lost readiness or moved the person");
    check(cardView(1,0,personPunk)["card_id"]=="widow_with_a_shotgun","A legally flipped person's identity remained hidden from the opponent");
}

void mimicConditionsAndVera() {
    auto e=game();J s=fixture(e);int mimic=put(s,"con_man",0,0),rouser=put(s,"ringleader",1,0),punk=put(s,"vigilante",1,1,true);
    (void)rouser;(void)punk;load(e,s);action(e,0,"activate",mimic);
    J snapshot=saved(e);bool canGainPunk=false;for(const auto& o:snapshot["choice"]["options"])for(const auto& t:o["tasks"]) {
        check(!(t.value("from",0)==rouser&&t.value("ability",-1)==1),"Con Man borrowed the enemy's punk condition");
        if(t.value("from",0)==rouser&&t.value("ability",-1)==0)canGainPunk=true;
    }
    check(canGainPunk,"Con Man lost the enemy Ringleader's unconditional punk ability");
    s=fixture(e);int muse=put(s,"bartender",0,1),vera=put(s,"charles_goodnight",0,2);entity(s,muse)["ready"]=false;entity(s,mimic)["ready"]=true;entity(s,mimic)["uses"]=0;load(e,s);action(e,0,"activate",mimic);
    snapshot=saved(e);for(const auto& o:snapshot["choice"]["options"])check(o["label"].get<std::string>().find("Bartender:")==std::string::npos,"Con Man copied an unready friendly Bartender");
    s=fixture(e);entity(s,muse)["ready"]=true;entity(s,vera)["damage"]=0;entity(s,vera)["ready"]=true;load(e,s);
    action(e,0,"activate",muse);check(entity(saved(e),muse)["ready"].get<bool>(),"Vera did not preserve first zero-cost use");
    action(e,0,"activate",muse);check(!entity(saved(e),muse)["ready"].get<bool>(),"Vera permitted a third ordinary ability use");
    check(view(e)["players"][0]["water"]==22,"Two Bartender uses failed to generate exactly two extra water");
    s=fixture(e);int garage=camp(s,0,0,"cattle_ranch"),bot=put(s,"blacksmith",0,1);entity(s,vera)["damage"]=1;entity(s,vera)["ready"]=false;load(e,s);
    action(e,0,"activate",garage);check(!entity(saved(e),garage)["ready"].get<bool>(),"Damaged Vera granted an extra use");
    action(e,0,"activate",bot);choice(e,vera);check(!entity(saved(e),garage)["ready"].get<bool>(),"Restoring Vera retroactively readied an already used camp");
    check(!entity(saved(e),vera)["ready"].get<bool>(),"Restoring Vera readied Vera herself");
}

void helperTimingAndPayments() {
    auto e=game();J s=fixture(e);int lab=camp(s,0,0,"saloon"),soldier=put(s,"civil_war_veteran",0,0,false,1,false);
    entity(s,soldier)["entered_turn"]=s["turn"];entity(s,soldier)["uses"]=1;s["players"][0]["water"]=1;
    load(e,s);action(e,0,"activate",lab);choice(e,-1,"Civil War Veteran:");choice(e);
    check(entity(saved(e),soldier)["zone"]=="discard","Adrenaline did not destroy its damaged person after use");
    check(view(e)["players"][0]["water"]==0,"Adrenaline waived the person's ability cost");
    s=fixture(e);int base=camp(s,0,0,"railroad_depot");soldier=put(s,"civil_war_veteran",0);s["players"][0]["water"]=2;load(e,s);
    int handBefore=view(e)["players"][0]["hand_count"];action(e,0,"activate",base);choice(e,soldier);choice(e,-1,"Civil War Veteran:");choice(e);
    check(view(e)["players"][0]["water"]==0,"Parachute did not charge both play and ability water");
    check(entity(saved(e),soldier)["zone"]=="discard","Parachute's post-ability damage should destroy a Soldier already damaged by its entry");
    check(view(e)["players"][0]["hand_count"]==handBefore,"Civil War Veteran's entry draw was skipped during Parachute deployment");
    s=fixture(e);base=camp(s,0,0,"railroad_depot");int rescue=put(s,"sarah_winnemucca",0);load(e,s);
    action(e,0,"activate",base);choice(e,rescue);choice(e,-1,"Sarah Winnemucca:");choice(e,rescue);
    check(entity(saved(e),rescue)["zone"]=="hand"&&entity(saved(e),rescue)["damage"]==0,"Parachute followed a rescued person into the hand with battlefield damage");
}

void helperAffordability() {
    auto e=game();J s=fixture(e);int base=camp(s,0,0,"railroad_depot"),mimic=put(s,"con_man",0);put(s,"annie_oakley",1,0);
    auto hand=s["players"][0]["hand"].get<std::vector<int>>();for(int x:hand)if(x!=mimic){detach(s,x);entity(s,x)["zone"]="discard";entity(s,x)["owner"]=-1;s["discard"].push_back(x);}
    s["players"][0]["water"]=2;load(e,s);
    for(const auto& a:legal(e))check(!(a["command"]["type"]=="activate"&&a["command"].value("source",0)==base),"Parachute offered Con Man without enough water for both deployment and copied Annie Oakley ability");
    s["players"][0]["water"]=3;load(e,s);action(e,0,"activate",base);choice(e,mimic);choice(e,-1,"Annie Oakley:");choice(e);
    check(view(e)["players"][0]["water"]==0&&entity(saved(e),mimic)["damage"]==1,"Payable Parachute Con Man failed to resolve its copied ability then take damage");
    check(saved(e)["choice"].is_null(),"Parachute stranded an unresolved choice after Con Man's ability");
    s=fixture(e);int lab=camp(s,0,0,"saloon");entity(s,mimic)["damage"]=1;s["players"][0]["water"]=1;load(e,s);
    for(const auto& a:legal(e))check(!(a["command"]["type"]=="activate"&&a["command"].value("source",0)==lab),"Adrenaline offered a damaged Con Man with no affordable copied ability");
}

void juggernautGeometry() {
    auto e=game();J s=fixture(e);int jug=camp(s,0,0,"riverboat"),old=put(s,"bartender",0,0),incoming=put(s,"vigilante",0);
    entity(s,jug)["advance"]=1;load(e,s);auto actions=legal(e);int placements=0;
    for(const auto& a:actions) {const auto& c=a["command"];if(c["type"]!="play"||c.value("card",0)!=incoming||c.value("column",-1)!=0)continue;
        load(e,s);act(e,0,c);auto col=saved(e)["players"][0]["columns"][0];
        check(col.size()==3&&col[1]==jug,"An advanced-once Riverboat allowed both people on the same side");
        check(view(e)["players"][0]["columns"][0][2]["protected"].get<bool>(),"Person behind Riverboat lost camp protection");++placements;
    }
    check(placements==2,"Advanced-once Riverboat should allow either ordering of the two people");
    s["players"][0]["columns"][0]=J::array({jug,old});entity(s,jug)["advance"]=2;load(e,s);actions=legal(e);placements=0;
    for(const auto& a:actions) {const auto& c=a["command"];if(c["type"]!="play"||c.value("card",0)!=incoming||c.value("column",-1)!=0)continue;
        load(e,s);act(e,0,c);check(saved(e)["players"][0]["columns"][0][0]==jug,"A person was placed in front of fully advanced Riverboat");++placements;
    }
    check(placements==2,"Fully advanced Riverboat should permit both person orderings behind it");
    load(e,s);action(e,0,"activate",jug);check(view(e)["choice"]["player"]==1,"Riverboat third move camp sacrifice belongs to defender");choice(e);
    check(saved(e)["players"][0]["columns"][0].back()==jug&&entity(saved(e),jug)["advance"]==0,"Riverboat failed to return to camp row after its third move");
}

void allBaseEffects() {
    const auto cards=J::parse(catalog)["cards"];
    for(const auto& d:cards)if(!d.value("special",false)&&d.value("set",std::string())!="boomtown") {
        if(d["type"]=="event") {
            auto e=game();J s=fixture(e);int id=put(s,d["id"],0);put(s,"bartender",0,0);put(s,"prospector",0,1);put(s,"vigilante",1,0);put(s,"widow_with_a_shotgun",1,1);
            int zeto=put(s,"poker_alice",0,2);(void)zeto;load(e,s);action(e,0,"play",id);settle(e);check(J::parse(e.ValidateJson())["ok"].get<bool>(),"Event left invalid state: "+d["id"].get<std::string>());
        }
        for(int ability=0;ability<int(d["abilities"].size());++ability) {
            auto e=game();J s=fixture(e);int id=d["type"]=="camp"?camp(s,0,0,d["id"]):put(s,d["id"],0,0);
            put(s,"civil_war_veteran",0,1,false,1);put(s,"bartender",0,2);put(s,"widow_with_a_shotgun",0,1);put(s,"vigilante",0,2,true);put(s,"prospector",1,0,false,1);put(s,"annie_oakley",1,1);
            int injured=camp(s,0,2,"gatling_emplacement");entity(s,injured)["damage"]=1;
            s["players"][0]["entered"]=2;s["players"][0]["events_resolved"]=1;
            int ev=put(s,"run_out_of_town",1);detach(s,ev);entity(s,ev)["zone"]="queue";s["players"][1]["queue"][0]=ev;
            put(s,"blacksmith",0);put(s,"doc_holliday",0);put(s,"gatling_gunner",0);put(s,"poker_night",0);
            if(d["id"]=="livery_barn") {std::vector<int> remove;for(auto& col:s["players"][0]["columns"])for(int x:col)if(x!=id&&entity(s,x)["card_id"]!="gatling_emplacement")remove.push_back(x);for(int x:remove){detach(s,x);entity(s,x)["zone"]="discard";entity(s,x)["owner"]=-1;entity(s,x)["punk"]=false;s["discard"].push_back(x);}}
            if(d["id"]=="breaking_pen"){put(s,"bounty_hunter",0,0);put(s,"hellfire_preacher",0,0);}
            load(e,s);try{action(e,0,"activate",id,ability);settle(e);}catch(const std::exception& err){throw std::runtime_error(d["id"].get<std::string>()+"/"+std::to_string(ability)+": "+err.what());}
        }
    }
}

void allExpansionEffects() {
    for(const auto& d:definitions)if(d.value("set",std::string())=="boomtown")for(int ability=0;ability<int(d["abilities"].size());++ability) {
        auto e=game();J s=fixture(e);int source=camp(s,0,0,d["id"]);
        int muse=put(s,"bartender",0,0),soldier=put(s,"civil_war_veteran",0,0,false,1);
        put(s,"doc_holliday",0,1,false,1);put(s,"hellfire_preacher",0,1);put(s,"vigilante",0,2,true);put(s,"prospector",0,2);
        put(s,"prospector",1,0,false,1);put(s,"annie_oakley",1,1);entity(s,muse)["entered_turn"]=s["turn"];
        entity(s,camp(s,0,1,"gatling_emplacement"))["damage"]=1;int ruin=camp(s,0,2,"gatling_emplacement");entity(s,ruin)["damage"]=2;entity(s,ruin)["destroyed"]=true;entity(s,ruin)["ready"]=false;
        for(const auto& id:{"wyatt_earp","quanah_parker","charles_goodnight","cornelius_ashby_railroad_baron","augustus_powder_pike","poker_night"})put(s,id,0);
        s["players"][0]["hurt"]=true;
        if((d["id"]=="army_surgeon_s_tent"||d["id"]=="jailhouse")&&ability==0){detach(s,soldier);entity(s,soldier)["zone"]="discard";entity(s,soldier)["owner"]=-1;s["discard"].push_back(soldier);}
        if(d["id"]=="quaker_settlement")entity(s,source)["damage"]=ability;
        try{load(e,s);action(e,0,"activate",source,ability);settle(e);check(J::parse(e.ValidateJson())["ok"].get<bool>(),"Expansion ability invalidated state");}
        catch(const std::exception& error){throw std::runtime_error(d["id"].get<std::string>()+"/"+std::to_string(ability)+": "+error.what());}
    }
}

void expansionTimingAndPolicies() {
    auto e=game();J s=fixture(e);camp(s,0,0,"robbers_roost");camp(s,0,1,"courthouse");int r=s["players"][0]["stampede"];
    s["players"][0]["queue"][0]=r;entity(s,r)["zone"]="queue";s["active_player"]=1;s["players"][0]["water"]=0;
    int banish=put(s,"run_out_of_town",1),napalm=put(s,"prairie_fire",1);detach(s,banish);detach(s,napalm);entity(s,banish)["zone"]="queue";entity(s,napalm)["zone"]="queue";s["players"][1]["queue"]=J::array({banish,0,napalm});
    load(e,s);action(e,1,"end_turn");
    check(view(e)["players"][0]["water"]==0&&!view(e)["choice"].is_null(),"Events must finish before turn water arrives");
    check(view(e)["log"].back()["type"]!="water","Refill was presented before the pending event choice");
    choice(e);
    check(view(e)["players"][0]["water"]==4,"Bandit water from Events was discarded during replenishment");
    check(view(e)["log"].back()["type"]=="water"&&view(e)["log"].back()["detail"]=="3","Refill presentation must report the three-water addition, not the four-water balance");
    check(saved(e)["players"][1]["queue"][1]==banish&&saved(e)["players"][1]["queue"][2]==napalm,"Derby did not push legal events while retaining a blocked back event");
    s=fixture(e);int gas=camp(s,0,0,"coal_yard");put(s,"poker_alice",0,0);s["players"][0]["events_played"]=0;s["players"][0]["queue"]=J::array({0,0,0});entity(s,r)["zone"]="special";load(e,s);action(e,0,"activate",gas);
    check(view(e)["choice"]["player"]==1&&entity(saved(e),r)["zone"]=="special","Confirmed ruling: Zeto must make the first Coal Yard launch immediate");
    settle(e);
    s=fixture(e);int plant=camp(s,0,0,"chuckwagon"),muse=put(s,"bartender",0,1);put(s,"charles_goodnight",0,2);load(e,s);
    action(e,0,"activate",muse);action(e,0,"activate",muse);action(e,0,"activate",plant);action(e,0,"activate",muse);
    check(!entity(saved(e),muse)["ready"].get<bool>()&&entity(saved(e),muse)["uses"]==3,"Chuckwagon reset Vera's first-use history");
    s=fixture(e);int market=camp(s,0,0,"smuggler_s_landing"),foe=put(s,"blacksmith",1,2);entity(s,foe)["entered_turn"]=s["turn"];entity(s,market)["damage"]=1;load(e,s);action(e,0,"activate",market);choice(e,-1,"Blacksmith:");
    for(const auto& a:legal(e))check(a["label"].get<std::string>().find("Smuggler's Landing")==std::string::npos,"Smuggler's Landing offered forbidden self-restoration");settle(e);
}

void guillotineAndRecruitment() {
    auto e=game();J s=fixture(e);int guillotine=camp(s,0,0,"gallows"),muse=put(s,"bartender",1,0);s["players"][1]["water"]=0;load(e,s);
    action(e,0,"activate",guillotine);choice(e,muse);check(entity(saved(e),muse)["zone"]=="discard","Gallows must destroy before offering an ability");choice(e,-1,"Bartender:");
    check(view(e)["players"][1]["water"]==1,"Gallows Bartender did not generate free out-of-turn water");action(e,0,"end_turn");check(view(e)["players"][1]["water"]==4,"Gallows Bartender bonus did not survive to its owner's turn");
    s=fixture(e);guillotine=camp(s,0,0,"gallows");int leader=put(s,"hellfire_preacher",1,0);load(e,s);action(e,0,"activate",guillotine);choice(e,leader);
    check(legal(e,1).size()==1&&legal(e,1)[0]["label"]=="Skip","Destroyed lone Hellfire Preacher was allowed to sacrifice itself");choice(e);
    s=fixture(e);int asylum=camp(s,0,0,"jailhouse"),soldier=put(s,"civil_war_veteran",1,1,false,1);s["players"][0]["entered"]=0;load(e,s);int hand=view(e)["players"][0]["hand_count"];
    action(e,0,"activate",asylum,0);choice(e,soldier);check(entity(saved(e),soldier)["owner"]==0&&entity(saved(e),soldier)["damage"]==1,"Jailhouse failed to preserve damage on recruitment");
    check(view(e)["players"][0]["hand_count"]==hand&&saved(e)["players"][0]["entered"]==0,"Jailhouse improperly retriggered entry draw/counters");
}

void miningAndRescueRestrictions() {
    auto e=game();J s=fixture(e);int mining=camp(s,0,0,"boarding_house"),ruin=camp(s,0,1,"gatling_emplacement");entity(s,ruin)["damage"]=2;entity(s,ruin)["destroyed"]=true;entity(s,ruin)["ready"]=false;
    put(s,"bartender",0,1);put(s,"prospector",0,1);int holdout=put(s,"widow_with_a_shotgun",0);load(e,s);action(e,0,"activate",mining,0);choice(e,ruin);choice(e);
    check(entity(saved(e),ruin)["zone"]=="removed","Mining did not remove the ruin");bool found=false;
    for(const auto& a:legal(e))if(a["command"]["type"]=="play"&&a["command"].value("card",0)==holdout&&a["command"].value("column",-1)==1){check(a["cost"]==2,"Widow with a Shotgun retained its discount after the ruin was removed");act(e,0,a["command"]);found=true;break;}
    check(found&&saved(e)["players"][0]["columns"][1].size()==3,"Mining did not create a third person slot");
    // Removing an enemy ruin must still leave the damage choice for Mining Camp.
    e=game();s=fixture(e);mining=camp(s,0,0,"boarding_house");
    ruin=camp(s,1,0,"gatling_emplacement");entity(s,ruin)["damage"]=2;entity(s,ruin)["destroyed"]=true;entity(s,ruin)["ready"]=false;
    const int victim=camp(s,1,1,"gatling_emplacement");load(e,s);
    action(e,0,"activate",mining,0);choice(e,ruin);
    check(entity(saved(e),ruin)["zone"]=="removed","Boarding House failed to remove the enemy ruin");
    check(saved(e)["choice"]["prompt"]=="Choose a damage target","Boarding House lost its damage step after removing an enemy ruin");
    for(const auto& a:legal(e)) {
        check(oldwest::FieldActionMatches(a,mining),"Boarding House cannot drag to its follow-up damage target");
        check(oldwest::FieldActionMatches(a,-3002),"Water drag cannot complete the paid Boarding House action");
    }
    choice(e,victim);
    check(entity(saved(e),victim)["damage"]==1,"Boarding House did not apply its follow-up damage");
    e=game();s=fixture(e);int post=camp(s,0,0,"pony_express_station"),base=camp(s,0,1,"railroad_depot"),mask=camp(s,0,2,"wanted_poster_board");(void)mask;
    int recovered=put(s,"blacksmith",0,0),copy=put(s,"blacksmith",0,2,true);load(e,s);action(e,0,"activate",post);choice(e,recovered);
    for(const auto& a:legal(e))check(!((a["command"]["type"]=="play"&&a["command"].value("card",0)==recovered)||(a["command"]["type"]=="flip"&&a["command"].value("card",0)==copy)),"Pony Express Station allowed same-turn faceup entry of a returned card/copy");
    bool canUseBase=false;for(const auto& a:legal(e))if(a["command"].value("source",0)==base)canUseBase=true;
    if(canUseBase){action(e,0,"activate",base);J state=saved(e);for(const auto& o:state["choice"]["options"])for(const auto& t:o["tasks"])check(t.value("target",0)!=recovered,"Parachute bypassed Pony Express Station's entry restriction");}
}

void expansionCompoundResolution() {
    auto e=game();J s=fixture(e);int lobo=camp(s,0,0,"crimp_house"),patient=put(s,"prospector",0,1,false,1),known=put(s,"doc_holliday",0);
    detach(s,known);entity(s,known)["zone"]="deck";entity(s,known)["owner"]=-1;s["deck"].insert(s["deck"].begin(),known);load(e,s);
    action(e,0,"activate",lobo);choice(e,patient);J state=saved(e);
    check(entity(state,patient)["zone"]=="discard","Crimp House failed to destroy the replaced person");
    int replacement=state["players"][0]["columns"][1][0];check(entity(state,replacement)["punk"].get<bool>()&&replacement!=patient,"Crimp House did not place a fresh punk at the exact former position");
    check(view(e)["players"][0]["water"]==20&&state["players"][0]["entered"]==1,"Crimp House failed its refund or new-entry trigger");
    e=game();s=fixture(e);int incinerator=camp(s,0,0,"pawn_shop"),heal=camp(s,0,1,"gatling_emplacement"),foeCamp=camp(s,1,0,"gatling_emplacement"),punk=put(s,"bartender",1,0,true),injure=put(s,"con_man",0),repair=put(s,"gatling_gunner",0);
    entity(s,heal)["damage"]=1;entity(s,incinerator)["damage"]=1;
    auto hand=s["players"][0]["hand"].get<std::vector<int>>();for(int x:hand)if(x!=injure&&x!=repair){detach(s,x);entity(s,x)["zone"]="discard";entity(s,x)["owner"]=-1;s["discard"].push_back(x);}
    load(e,s);
    bool waterCanActivate=false;
    for(const auto& a:legal(e))if(a["command"].value("source",0)==incinerator&&a["command"]["type"]=="activate") {
        check(oldwest::FieldActionMatches(a,incinerator),"Camp cannot initiate its own action by drag");
        waterCanActivate=oldwest::FieldActionMatches(a,-3002);
    }
    check(waterCanActivate,"Water cannot initiate paid Pawn Shop ability");
    action(e,0,"activate",incinerator);
    for(const auto& a:legal(e)) {
        check(oldwest::FieldActionMatches(a,incinerator),"Camp cannot complete its targetless discard choice by drag");
        check(oldwest::FieldActionMatches(a,-3003),"Bunkhouse cannot complete discard choice by drag");
    }
    choice(e,repair);choice(e,injure);choice(e,-1,"Con Man:");choice(e,punk);choice(e,-1,"Gatling Gunner:");choice(e,heal);choice(e,foeCamp);
    state=saved(e);check(entity(state,punk)["zone"]=="deck"&&entity(state,foeCamp)["damage"]==1,"Pawn Shop failed to clear protection before its final damage");
    check(entity(state,heal)["damage"]==0&&entity(state,incinerator)["damage"]==1,"Pawn Shop restored the wrong card or itself");
    // Report the screenshot's two missing costs together, excluding Water Silo.
    e=game();s=fixture(e);incinerator=camp(s,0,0,"pawn_shop");
    const auto oldHand=s["players"][0]["hand"];
    for(int x:oldHand){detach(s,x);entity(s,x)["zone"]="discard";entity(s,x)["owner"]=-1;s["discard"].push_back(x);}
    put(s,"rustler",0);
    const int silo=s["players"][0]["silo"];detach(s,silo);entity(s,silo)["zone"]="hand";entity(s,silo)["owner"]=0;s["players"][0]["hand"].push_back(silo);
    for(int water:{0,1}) {
        s["players"][0]["water"]=water;load(e,s);
        const auto card=view(e)["players"][0]["columns"][0][0];
        const auto status=card["ability_availability"][0];
        check(!status["available"].get<bool>(),"Pawn Shop must require two non-Silo cards");
        check(status["reason"].get<std::string>().find("you have "+std::to_string(water)+" water and 1 eligible card(s)")!=std::string::npos,"Pawn Shop must explain both current resources without counting Silo");
        check(card["public_abilities"][0]["activation_label"].get<std::string>().find("water + discard 2 hand cards")!=std::string::npos,"Pawn Shop must display its full activation cost");
        for(const auto& a:legal(e))check(a["command"].value("source",0)!=incinerator,"Blocked Pawn Shop must not offer an action");
    }
    // Earlier ordinary junk actions do not satisfy Pawn Shop's separate payment.
    e=game();s=fixture(e);incinerator=camp(s,0,0,"pawn_shop");
    int earlyOne=put(s,"claim_jumper",0),earlyTwo=put(s,"rustler",0);
    int payOne=put(s,"box_canyon",0),payTwo=put(s,"poker_night",0);
    load(e,s);action(e,0,"junk",earlyOne);action(e,0,"junk",earlyTwo);
    const int waterBefore=view(e)["players"][0]["water"];
    action(e,0,"activate",incinerator);
    check(saved(e)["choice"]["prompt"]=="Discard 2 card(s) for Pawn Shop","Earlier junks incorrectly paid Pawn Shop's discard cost");
    check(view(e)["players"][0]["water"]==waterBefore-1,"Pawn Shop activation must spend exactly one water");
    choice(e,payOne);
    check(saved(e)["choice"]["prompt"]=="Discard 1 card(s) for Pawn Shop","Pawn Shop must collect both new discards before junk effects");
    choice(e,payTwo);
    check(saved(e)["choice"]["prompt"]=="Use a discarded junk effect","Pawn Shop did not advance after its two discards");
    settle(e);
    check(saved(e)["choice"].is_null(),"Pawn Shop sequence became stuck after ordinary prior junks");
    e=game();s=fixture(e);int boulder=camp(s,0,0,"rockslide_ridge");for(int p=0;p<2;++p)for(int c=0;c<3;++c)if(!(p==0&&c==0)&&!(p==1&&c==2)){int x=camp(s,p,c,"gatling_emplacement");entity(s,x)["damage"]=2;entity(s,x)["destroyed"]=true;entity(s,x)["ready"]=false;}
    int last=camp(s,1,2,"gatling_emplacement");entity(s,last)["damage"]=1;put(s,"bartender",1,2);load(e,s);action(e,0,"activate",boulder);choice(e,-1,"lane 3");
    check(e.Winner()==0&&!entity(saved(e),boulder)["destroyed"].get<bool>(),"Lethal Rockslide Ridge continued into its own destruction");
    e=game();s=fixture(e);int guillotine=camp(s,0,0,"gallows"),argo=put(s,"wyatt_earp",1,0);load(e,s);action(e,0,"activate",guillotine);choice(e,argo);
    check(legal(e,1).size()==2,"Gallows lost Argo's printed damage ability");choice(e,-1,"Wyatt Earp:");choice(e);
}

void simulatedMatches(const std::string& ruleset="base_2024") {
    std::mt19937 random(20260906);int finished=0,accepted=0;std::set<std::string> used;
    for(int match=0;match<40;++match){Engine e(catalog,random(),J{{"first_player",-1},{"ruleset",ruleset}}.dump());
        for(int p=0;p<2;++p){auto options=legal(e,p);act(e,p,options[random()%options.size()]["command"]);}
        for(int step=0;step<2200&&!e.IsFinished();++step){auto v=view(e);int p=v["choice"].is_null()?v["active_player"].get<int>():v["choice"]["player"].get<int>();auto options=legal(e,p);check(!options.empty(),"Match deadlocked");
            std::vector<int> weighted;for(int i=0;i<int(options.size());++i){std::string kind=options[i]["category"];int weight=kind=="ability"?5:kind=="turn"?3:1;for(int n=0;n<weight;++n)weighted.push_back(i);}
            auto cmd=options[weighted[random()%weighted.size()]]["command"];used.insert(cmd["type"]);auto before=e.SaveJson();J result=J::parse(e.Apply(p,cmd.dump()));
            if(!result["ok"].get<bool>()){std::ofstream("/tmp/oldwest-failed-state.json")<<before;throw std::runtime_error("Simulation "+std::to_string(match)+" step "+std::to_string(step)+": "+cmd.dump()+" "+result.dump());}
            ++accepted;
            if(step%53==0){Engine restored(catalog,99);check(restored.RestoreJson(e.SaveJson()),"Checkpoint failed to restore");check(restored.ViewJson(0)==e.ViewJson(0)&&restored.ViewJson(1)==e.ViewJson(1),"Restored views differ");}
        }
        if(e.IsFinished())++finished;
    }
    check(finished>=35,"Too many simulated games failed to finish");
    std::cout<<"Simulations: "<<finished<<"/40 finished, "<<accepted<<" accepted commands, "<<used.size()<<" action types\n";
}

void spatialChoiceMetadata() {
    auto inspect=[](Engine& e,bool expectPunk,bool expectMoving) {
        auto actions=legal(e);auto state=saved(e);
        check(!actions.empty(),"Missing spatial choices");
        check(legal(e,1).empty(),"Nonchoosing player received legal spatial options");
        check(!view(e,1)["choice"].contains("options"),"Other player received private choice options");
        int destinations=0;
        for(const auto& a:actions) if(a.contains("placement")) {
            ++destinations;const auto& p=a["placement"];
            const std::set<std::string> allowed={"player","column","position","card","moving","punk","replace","row"};
            for(const auto& field:p.items())check(allowed.count(field.key()),"Spatial metadata includes private task data");
            check(p["punk"]==expectPunk&&p["moving"]==expectMoving,"Incorrect spatial choice kind");
            check(p["column"].get<int>()>=0&&p["column"].get<int>()<3,"Invalid public destination");
            check(a["command"].size()==2&&a["command"]["type"]=="choose","Spatial UI replaced opaque choice authority");
            if(expectPunk)check(p["card"]==0,"Punk placement leaks the next drawn card handle");
            load(e,state);act(e,0,a["command"]);check(J::parse(e.ValidateJson())["ok"].get<bool>(),"Spatial choice breaks rules invariants");
        }
        check(destinations>0,"No machine-readable spatial destinations");
    };
    {auto e=game();auto s=fixture(e);std::string id;for(const auto& d:definitions)if(d.value("junk",std::string())=="punk"){id=d["id"];break;}
        const int card=put(s,id,0);load(e,s);action(e,0,"junk",card);inspect(e,true,false);}
    {auto e=game();auto s=fixture(e);const int base=camp(s,0,0,"roundup_corral");put(s,"annie_oakley",0,0);put(s,"bartender",1,1);load(e,s);action(e,0,"activate",base,0);inspect(e,false,true);}
    {auto e=game();auto s=fixture(e);const int base=camp(s,0,0,"railroad_depot");put(s,"civil_war_veteran",0);load(e,s);action(e,0,"activate",base,0);inspect(e,false,false);}
    {auto e=game();auto s=fixture(e);const int base=camp(s,0,0,"jailhouse");put(s,"annie_oakley",1,1,false,1);load(e,s);action(e,0,"activate",base,0);inspect(e,false,true);}
    {auto e=game();auto s=fixture(e);const int base=camp(s,0,0,"army_surgeon_s_tent");put(s,"annie_oakley",0,1,false,1);load(e,s);action(e,0,"activate",base,0);inspect(e,false,true);}
    {auto e=game();auto s=fixture(e);put(s,"poker_alice",0,0);const int card=put(s,"box_canyon",0);put(s,"annie_oakley",0,1);put(s,"bartender",0,2);load(e,s);action(e,0,"play",card);choice(e,-1,"Rearrange");
        for(const auto& a:legal(e))if(a.contains("placement"))check(a["placement"].contains("row"),"Rearrangement lacks planned-row preview");
        inspect(e,false,true);}

}

void eventDestinationMetadata() {
    auto checkDestination=[](Engine& e,int card,int expected) {
        for(const auto& a:legal(e))if(a.value("category",std::string())=="play_event"&&a["command"].value("card",0)==card) {
            check(a.value("event_slot",-99)==expected,"Event drop marker names the wrong destination");
            check(a["command"].size()==2,"Event presentation metadata changed the authoritative command");
            act(e,0,a["command"]);
            const auto after=saved(e);
            if(expected>=0)check(after["players"][0]["queue"][expected]==card,"Event did not enter its previewed queue slot");
            else check(entity(after,card)["zone"]!="queue","Play-now marker scheduled an event instead");
            check(J::parse(e.ValidateJson())["ok"].get<bool>(),"Event drop breaks rules invariants");
            return;
        }
        throw std::runtime_error("Missing event action for destination check");
    };
    {auto e=game();auto s=fixture(e);const int card=put(s,"gold_rush",0);load(e,s);checkDestination(e,card,1);}
    {auto e=game();auto s=fixture(e);const int card=put(s,"run_out_of_town",0),occupied=put(s,"prairie_fire",0),occupied2=put(s,"cholera",0);
        detach(s,occupied);detach(s,occupied2);entity(s,occupied)["zone"]="queue";entity(s,occupied2)["zone"]="queue";
        s["players"][0]["queue"]=J::array({occupied,occupied2,0});load(e,s);checkDestination(e,card,2);}
    {auto e=game();auto s=fixture(e);const int card=put(s,"curfew",0);load(e,s);checkDestination(e,card,-1);}
    {auto e=game();auto s=fixture(e);put(s,"poker_alice",0,0);const int card=put(s,"cannonade",0);load(e,s);checkDestination(e,card,-1);}
}

void publicAbilityOverview() {
    auto e=game();auto s=fixture(e);
    const int box=camp(s,0,0,"homestead_cabin"),armory=camp(s,0,1,"gunsmith");
    const int argo=put(s,"wyatt_earp",0,0),punk=put(s,"bartender",0,1,true),sniper=put(s,"annie_oakley",1,0,false,0,false);
    load(e,s);
    auto findCard=[](const J& v,int id)->J {for(const auto& p:v["players"])for(const auto& col:p["columns"])for(const auto& c:col)if(c["id"]==id)return c;throw std::runtime_error("Missing overview card");};
    const auto own=findCard(view(e),punk),enemy=findCard(view(e,1),punk);
    check(own["public_abilities"]==enemy["public_abilities"],"Public granted abilities differ by viewer");
    check(enemy["public_abilities"].size()==2,"Punk overview omits Argo or Gunsmith grant");
    check(!enemy.contains("card_id")&&!enemy.contains("private_peek"),"Overview exposed a punk face");
    check(enemy["public_abilities"][0]["cost"]==1&&enemy["public_abilities"][1]["cost"]==2,"Granted ability costs incorrect");
    auto alternate=s;entity(alternate,punk)["card_id"]="quanah_parker";load(e,alternate);
    check(findCard(view(e,1),punk)==enemy,"Overview depends on the hidden punk identity");
    load(e,s);const auto tired=findCard(view(e),sniper);
    check(!tired["ready"].get<bool>()&&tired["public_abilities"].size()==1,"Exhaustion hides printed enemy ability");
    check(tired["public_abilities"][0]["effect"]=="Hit any enemy crew member or holding","Enemy ability meaning missing");
    check(!tired["public_abilities"][0].contains("available"),"Public overview includes private legality inference");
    const int ruin=camp(s,0,2,"gatling_emplacement");entity(s,ruin)["destroyed"]=true;entity(s,ruin)["damage"]=2;entity(s,ruin)["ready"]=false;load(e,s);
    check(findCard(view(e),box)["public_abilities"][0]["cost"]==2,"Overview misses current reduced Homestead Cabin cost");
    check(findCard(view(e),ruin)["public_abilities"].size()==1,"Repair planning loses ruined camp abilities");
    (void)armory;(void)argo;
}


void publicAbilityPresentation() {
    auto ability=[](const Engine& e,int source,int seat=0)->J {
        const J logs=view(e,seat)["log"];
        for(auto it=logs.rbegin();it!=logs.rend();++it)
            if((*it)["type"]=="ability"&&(*it)["source"]==source)return *it;
        throw std::runtime_error("Expected public ability presentation log");
    };
    for(int index:{0,1}) {
        auto e=game();auto s=fixture(e);
        const int rouser=put(s,"ringleader",0,0);put(s,"bartender",0,1,true);
        load(e,s);action(e,0,"activate",rouser,index);
        const J entry=ability(e,rouser);
        check(entry["ability_index"]==index,"Ringleader abilities share an ambiguous presentation log");
        check(entry==ability(e,rouser,1),"Public ability choice differs by viewer");
    }
    {
        auto e=game();auto s=fixture(e);
        const int mimic=put(s,"con_man",0,0),rouser=put(s,"ringleader",1,0);
        put(s,"bartender",0,1,true);load(e,s);action(e,0,"activate",mimic,0);
        bool invoked=false;
        const J options=saved(e)["choice"]["options"];
        for(const auto& option:options) {
            bool match=false;for(const auto& task:option["tasks"])
                match=match||(task.value("from",0)==rouser&&task.value("ability",-1)==1);
            if(match){act(e,0,{{"type","choose"},{"option",option["id"]}});invoked=true;break;}
        }
        check(invoked,"Copied multi-ability fixture has no legal selected ability");
        const J entry=ability(e,mimic);
        check(entry["ability_index"]==1&&entry["target"]==rouser,"Con Man lost the chosen copied ability or public source");
        check(entry==ability(e,mimic,1),"Copied ability presentation differs by viewer");
    }
    for(int index:{100,101}) {
        auto e=game();auto s=fixture(e);
        put(s,"wyatt_earp",0,0);camp(s,0,1,"gunsmith");const int punk=put(s,"bartender",0,2,true);
        load(e,s);action(e,0,"activate",punk,index);const J first=ability(e,punk,1);
        check(first["ability_index"]==index,"Granted ability presentation lost its public index");
        entity(s,punk)["card_id"]="quanah_parker";load(e,s);action(e,0,"activate",punk,index);
        check(ability(e,punk,1)==first,"Presentation metadata depends on a hidden punk face");
        check(!first.contains("card_id")&&!first.contains("ability_card_id")&&!first.contains("private_peek"),
              "Ability presentation includes hidden identity fields");
    }
}


void publicQueueTransitions() {
    auto events=[](const Engine& e,int seat=0)->J {
        const J current=view(e,seat);J result=J::array();for(const auto& entry:current["log"])
            if(entry["type"]=="event_advance")result.push_back(entry);
        return result;
    };
    auto enqueue=[](J& s,const std::string& name,int p,int slot)->int {
        int id=put(s,name,p);detach(s,id);entity(s,id)["zone"]="queue";
        s["players"][p]["queue"][slot]=id;return id;
    };
    auto expect=[](const J& entry,int id,int from,int to,int cause,const std::string& reason) {
        check(entry["source"]==id&&entry["target"]==0,"Queue log lost its public event entity");
        check(entry["from_slot"]==from&&entry["to_slot"]==to,"Queue log lost its actual intermediate positions");
        check(entry["cause_source"]==cause&&entry["move_reason"]==reason,"Queue log lost its public cause");
        check(!entry.contains("card_id")&&!entry.contains("private_peek"),"Queue movement exposed private identity");
    };
    {
        auto e=game();auto s=fixture(e);s["log"]=J::array();
        int a=enqueue(s,"run_out_of_town",0,1),b=enqueue(s,"ambush",0,2);
        s["active_player"]=1;load(e,s);action(e,1,"end_turn");const J logs=events(e);
        check(logs.size()==2,"Turn clock did not record both actual event moves");
        expect(logs[0],a,1,0,0,"turn_start");expect(logs[1],b,2,1,0,"turn_start");
        check(logs==events(e,1),"Public turn movement differs by viewer");
    }
    for(bool blocked:{false,true}) {
        auto e=game();auto s=fixture(e);s["log"]=J::array();
        int a=enqueue(s,"run_out_of_town",1,0),b=enqueue(s,"ambush",1,1);
        if(blocked)enqueue(s,"prairie_fire",1,2);
        int actor=put(s,"pinkerton_agent",0);load(e,s);action(e,0,"play",actor);if(!blocked)choice(e,-1,"Delay");const J logs=events(e);
        check(logs.size()==(blocked?0:2),"Pinkerton Agent invented blocked movement or lost a delay");
        if(!blocked){expect(logs[0],b,1,2,actor,"queue_delay");expect(logs[1],a,0,1,actor,"queue_delay");}
        check(logs==events(e,1),"Public delayed queue differs by viewer");
    }
    for(int slot:{0,1,2}) {
        auto e=game();auto s=fixture(e);s["log"]=J::array();
        int clock=camp(s,0,0,"telegraph_office"),event=enqueue(s,"run_out_of_town",1,slot);
        put(s,"bartender",0,1);load(e,s);action(e,0,"activate",clock);choice(e,event);const J logs=events(e);
        check(logs.size()==(slot==0?0:1),"Telegraph Office movement/resolution boundary changed");
        if(slot)expect(logs[0],event,slot,slot-1,clock,"chosen_advance");
        else {bool resolved=false;const J current=view(e);for(const auto& entry:current["log"])
            resolved|=entry["type"]=="event_resolve"&&entry["source"]==event;
            check(resolved,"Slot-zero event no longer resolves");}
        check(logs==events(e,1),"Chosen public event movement differs by viewer");
    }
    for(bool blocked:{false,true}) {
        auto e=game();auto s=fixture(e);s["log"]=J::array();
        int scout=put(s,"rustler",0,0),r=s["players"][0]["stampede"];
        s["players"][0]["queue"][1]=r;entity(s,r)["zone"]="queue";
        if(blocked)enqueue(s,"run_out_of_town",0,0);
        load(e,s);action(e,0,"activate",scout);const J logs=events(e);
        check(logs.size()==(blocked?0:1),"Stampede movement count changed");
        if(!blocked)expect(logs[0],r,1,0,scout,"raid_ability");
    }
}

// Core fixtures deliberately control deck order. These are rule/metadata tests,
// not ordinary-gameplay, animation or private-state rendering evidence.
void publicAnalysisSelection() {
    auto logs=[](const Engine& e,const std::string& kind,int seat=0) {
        const J snapshot=view(e,seat);J out=J::array();for(const auto& event:snapshot["log"])
            if(event["type"]==kind)out.push_back(event);return out;
    };
    auto top=[](J& s,const std::vector<std::string>& cards) {
        std::set<int> used;J ordered=J::array();
        for(const auto& name:cards){
            int id=0;for(const auto& card:s["cards"])
                if(card["card_id"]==name&&card["zone"]!="board"&&!used.count(card["id"].get<int>())){id=card["id"];break;}
            if(!id)throw std::runtime_error("Missing ordered reveal fixture "+name);
            used.insert(id);detach(s,id);auto& card=entity(s,id);
            card["owner"]=-1;card["zone"]="deck";card["punk"]=false;card["ready"]=false;
            card["damage"]=0;card["uses"]=0;ordered.push_back(id);
        }
        for(int id:s["deck"])ordered.push_back(id);s["deck"]=ordered;
    };
    auto decision=[&](const Engine& e,int source,int sequence,int index,int handle,const std::string& effect) {
        const J all=logs(e,"analysis_choice");check(all.size()==1,"Exactly one accepted analysis decision expected");
        const J item=all[0];
        check(item["source"]==source&&item["analysis_sequence"]==sequence,"Analysis lost actual performer or initiating activation");
        check(item["reveal_index"]==index&&item["target"]==handle&&item["junk_effect"]==effect,"Analysis selected wrong historical reveal ordinal/handle/effect");
        check(item["selection"]==(index<0?"skip":"selected"),"Analysis selected/Skip discriminator incorrect");
        check(item["revision"]==view(e)["revision"],"Decision used activation rather than accepted choice revision");
        check(all==logs(e,"analysis_choice",1),"Accepted public analysis decision differs by viewer");
        const std::set<std::string> allowed={"sequence","revision","turn","type","player","source","target","detail",
            "analysis_sequence","reveal_index","junk_effect","selection"};
        for(auto it=item.begin();it!=item.end();++it)check(allowed.count(it.key())==1,"Analysis event exposes unapproved task/card metadata");
        return item;
    };
    for(int index:{0,1,2}) {
        auto e=game();auto s=fixture(e);s["log"]=J::array();
        const int scientist=put(s,"prospector",0,0),punk=put(s,"con_man",1,0,true);
        top(s,{"rustler","claim_jumper","rustler"});const int next=s["next_id"],water=s["players"][0]["water"];
        load(e,s);action(e,0,"activate",scientist,0);
        const J ability=logs(e,"ability"),reveals=logs(e,"reveal_discard");
        check(ability.size()==1&&ability[0]["ability_index"]==0,"Expected one printed Prospector activation");
        const int sequence=ability[0]["sequence"];
        check(reveals.size()==3&&logs(e,"analysis_choice").empty(),"Activation did not reveal exactly three, or guessed a future selection");
        check(reveals==logs(e,"reveal_discard",1),"Revealed public information differs by viewer");
        for(int n=0;n<3;++n){
            check(reveals[n]["source"]==scientist&&reveals[n]["target"]==next+n,"Reveal handle/source incorrect");
            check(reveals[n]["analysis_sequence"]==sequence&&reveals[n]["reveal_index"]==n&&reveals[n]["junk_effect"]=="water","Reveal annotation incorrect");
        }
        check(reveals[0]["detail"]==reveals[2]["detail"],"Duplicate-name ambiguity fixture missing");
        check(view(e)["choice"]["options"].size()==4,"Original three alternatives plus Skip changed");
        check(!view(e,1)["choice"].contains("options")&&legal(e,1).empty(),"Opponent received private alternatives or commands");
        check(!view(e,1)["players"][0].contains("hand"),"Analysis published opponent hand");
        const J publicChoice=view(e)["choice"];
        for(const auto& option:publicChoice["options"])
            check(option.size()==2&&option.contains("id")&&option.contains("label"),"Pending internal analysis/task data leaked");
        for(const auto& offer:legal(e))check(!offer.contains("analysis")&&!offer.contains("tasks"),"Private option annotation leaked into legal action");
        // Change only concealed information after the public reveals. Neither
        // viewer's public representation may depend on those unseen values.
        auto pending=saved(e),hidden=pending;const auto own=e.ViewJson(0),other=e.ViewJson(1);
        std::swap(entity(hidden,hidden["deck"][0])["card_id"],entity(hidden,hidden["deck"][1])["card_id"]);
        entity(hidden,punk)["card_id"]="quanah_parker";load(e,hidden);
        check(e.ViewJson(0)==own&&e.ViewJson(1)==other,"Analysis metadata depends on hidden deck or punk face");
        load(e,pending);const J command=legal(e)[index]["command"];
        const std::string untouched=e.SaveJson();
        J stale=command;stale["revision"]=-1;
        check(!J::parse(e.Apply(0,stale.dump()))["ok"].get<bool>()&&e.SaveJson()==untouched,"Rejected stale selection emitted a decision or changed state");
        act(e,0,command);const J selected=decision(e,scientist,sequence,index,next+index,"water");
        const J waterLogs=logs(e,"water");check(waterLogs.size()==1&&waterLogs[0]["source"]==scientist,"Selected water effect changed");
        check(selected["sequence"].get<int>()<waterLogs[0]["sequence"].get<int>(),"Selection must publish before effect task result");
        check(view(e)["players"][0]["water"]==water,"Selection charged twice or failed to deliver one water");
        check(saved(e)["choice"].is_null()&&saved(e)["tasks"].empty(),"Metadata introduced pending gameplay work");
    }
    {
        auto e=game();auto s=fixture(e);s["log"]=J::array();const int scientist=put(s,"prospector",0,0);
        top(s,{"gatling_gunner","rustler","claim_jumper"});load(e,s);action(e,0,"activate",scientist,0);
        const int sequence=logs(e,"ability")[0]["sequence"],handle=logs(e,"reveal_discard")[2]["target"];
        check(view(e)["choice"]["options"][0]["label"]=="Gatling Gunner: restore","No-target effect was pruned or reordered");
        const auto command=legal(e)[2]["command"];act(e,0,command);
        decision(e,scientist,sequence,2,handle,"water");
    }
    {
        auto e=game();auto s=fixture(e);s["log"]=J::array();const int scientist=put(s,"prospector",0,0);
        top(s,{"gatling_gunner","rustler","claim_jumper"});load(e,s);action(e,0,"activate",scientist,0);
        const int sequence=logs(e,"ability")[0]["sequence"],handle=logs(e,"reveal_discard")[0]["target"];
        act(e,0,legal(e)[0]["command"]);decision(e,scientist,sequence,0,handle,"restore");
        check(logs(e,"restore").empty()&&!saved(e)["choice"].is_null(),"No-target restore invented a result or lost its optional Skip");
        check(legal(e).size()==1&&legal(e)[0]["label"]=="Skip","Nested restore legality changed");
        act(e,0,legal(e)[0]["command"]);
        check(logs(e,"analysis_choice").size()==1&&logs(e,"restore").empty(),"Nested generic Skip fabricated another analysis decision/effect");
    }
    {
        auto e=game();auto s=fixture(e);s["log"]=J::array();const int scientist=put(s,"prospector",0,0);
        top(s,{"rustler","claim_jumper","rustler"});load(e,s);action(e,0,"activate",scientist,0);
        const int sequence=logs(e,"ability")[0]["sequence"];
        const J before=saved(e);act(e,0,legal(e)[3]["command"]);
        decision(e,scientist,sequence,-1,0,"");const J after=saved(e);
        for(const auto& key:{"players","cards","deck","discard","rng","next_id"})
            if(before.contains(key))check(before[key]==after[key],std::string("Optional Skip changed ")+key);
        check(logs(e,"water").empty()&&logs(e,"draw_card").empty()&&saved(e)["choice"].is_null(),"Skip produced a junk effect");
    }
    {
        auto e=game();auto s=fixture(e);s["log"]=J::array();const int mimic=put(s,"con_man",0,0),scientist=put(s,"prospector",1,0);
        top(s,{"rustler","claim_jumper","rustler"});load(e,s);action(e,0,"activate",mimic,0);choice(e,-1,"Prospector:");
        const J abilities=logs(e,"ability");check(abilities.size()==2&&abilities[1]["source"]==mimic&&abilities[1]["target"]==scientist,"Copied Prospector public source contract changed");
        const int sequence=abilities[1]["sequence"],handle=logs(e,"reveal_discard")[1]["target"];
        act(e,0,legal(e)[1]["command"]);decision(e,mimic,sequence,1,handle,"water");
        check(entity(saved(e),scientist)["ready"].get<bool>(),"Analysis metadata exhausted copied Prospector");
    }
    {
        auto e=game();auto s=fixture(e);s["log"]=J::array();const int lab=camp(s,0,0,"apothecary");
        top(s,{"rustler"});load(e,s);action(e,0,"activate",lab,0);
        check(logs(e,"reveal_discard").size()==1&&legal(e).size()==2,"Apothecary's existing one-card count changed");
        const int sequence=logs(e,"ability")[0]["sequence"],handle=logs(e,"reveal_discard")[0]["target"];
        act(e,0,legal(e)[0]["command"]);decision(e,lab,sequence,0,handle,"water");
    }
    {
        auto e=game();auto s=fixture(e);s["log"]=J::array();const int scientist=put(s,"prospector",0,0);
        top(s,{"rustler","claim_jumper","rustler"});const auto deck=s["deck"];
        s["deck"]=J::array({deck[0]});s["reshuffles"]=1;
        for(std::size_t i=1;i<deck.size();++i){const int id=deck[i];s["discard"].push_back(id);entity(s,id)["zone"]="discard";}
        load(e,s);action(e,0,"activate",scientist,0);
        check(e.IsFinished()&&view(e)["status"]=="draw","Second depletion no longer ends immediately");
        check(logs(e,"reveal_discard").size()==1&&logs(e,"analysis_choice").empty()&&saved(e)["choice"].is_null(),"Depletion invented unrevealed cards or an accepted decision");
    }
}

void battleHistoryAndTurnOrder() {
    auto e=game();auto s=fixture(e);s["history"]=J::array();s["log"]=J::array();
    camp(s,0,0,"robbers_roost");camp(s,0,1,"courthouse");
    int r=s["players"][0]["stampede"],next=put(s,"run_out_of_town",0),foe=put(s,"annie_oakley",1,0);
    detach(s,next);entity(s,next)["zone"]="queue";entity(s,r)["zone"]="queue";
    s["players"][0]["queue"]=J::array({r,next,0});s["players"][0]["water"]=0;s["active_player"]=1;
    load(e,s);action(e,1,"end_turn");
    auto h=view(e)["history"];int start=-1,resolve=-1;
    for(int i=0;i<int(h.size());++i){if(h[i]["type"]=="turn_start")start=i;if(h[i]["type"]=="event_resolve")resolve=i;}
    check(start>=0&&resolve>start,"Journal resolves an event before its turn starts");
    check(saved(e)["status"]=="events"&&legal(e,0).empty(),"Actions unlocked before defender completes starting Stampede");
    check(view(e)["players"][0]["water"]==0,"Replenishment ran before event response");
    choice(e);
    check(saved(e)["choice"].is_null()&&saved(e)["status"]=="actions","Events failed to complete before Actions");
    check(saved(e)["players"][0]["queue"][0]==next&&entity(saved(e),foe)["damage"]==0,"An advanced event resolved one turn early");
    check(view(e)["players"][0]["water"]==4,"Starting Bandit bonus lost during refill");
    h=view(e)["history"];int advance=-1,draw=-1,refill=-1,actions=-1;
    for(int i=0;i<int(h.size());++i){if(h[i]["type"]=="event_advance")advance=i;if(h[i]["type"]=="draw_card")draw=i;if(h[i]["type"]=="water"&&h[i]["detail"]=="3")refill=i;if(h[i]["phase"]=="actions"&&h[i]["type"]=="phase")actions=i;}
    check(advance>resolve&&draw>advance&&refill>draw&&actions>refill,"Event/advance/draw/water/action history order is wrong");
}

void completeRollingHistory() {
    auto e=game();auto s=fixture(e);s["history"]=J::array();s["history_serial"]=0;s["log"]=J::array();
    s["players"][0]["water"]=20;load(e,s);
    const int silo=s["players"][0]["silo"];
    for(int i=0;i<45;++i){action(e,0,"silo");action(e,0,"junk",silo);}
    const auto first=view(e)["history"];
    check(first.size()>200,"Long turn journal truncated");
    check(saved(e)["log"].size()<=80,"History unbounded the cinematic feed");
    check(first.front()["sequence"]==1,"First action disappeared from long turn");
    for(std::size_t i=1;i<first.size();++i)check(first[i]["sequence"].get<int>()==first[i-1]["sequence"].get<int>()+1,"History sequence has a gap");
    action(e,0,"end_turn");auto h=view(e)["history"];
    check(h.front()==first.front(),"Last turn lost when the new turn began");
    check(h==view(e,1)["history"],"Public histories differ by viewer");
    const auto checkpoint=e.SaveJson();Engine resumed(catalog,93);check(resumed.RestoreJson(checkpoint),"History save rejected");
    check(view(resumed)["history"]==h,"Reconnect changed history");
    action(e,1,"end_turn");
    check(journal(e).front()==first.front(),"Previous turn of the active player disappeared");
    action(e,0,"end_turn");
    check(journal(e).front()==first.front(),"Four-turn history discarded one player's previous turn");
    std::set<int> turns;for(const auto& entry:journal(e))turns.insert(entry["turn"].get<int>());
    check(turns==std::set<int>({5,6,7,8}),"History does not include the latest two turns of each player");
    action(e,1,"end_turn");
    for(const auto& entry:journal(e))check(entry["turn"].get<int>()>=6,"History retained a fifth-oldest turn");
    const auto before=e.SaveJson();check(!J::parse(e.Apply(1,R"({"type":"draw"})"))["ok"].get<bool>(),"Opponent acted out of turn");
    check(before==e.SaveJson(),"Rejected command changed journal/state");
}

void journalPrivacyAndIdentity() {
    auto a=game(),b=game();auto s=fixture(a);s["history"]=J::array();s["history_serial"]=0;
    int rouser=put(s,"ringleader",0,0);auto alternate=s;std::swap(alternate["deck"][0],alternate["deck"][1]);
    load(a,s);load(b,alternate);action(a,0,"activate",rouser);action(b,0,"activate",rouser);choice(a);choice(b);
    check(view(a,1)["history"]==view(b,1)["history"],"History identifies a hidden punk");
    s=fixture(a);s["history"]=J::array();alternate=s;std::swap(alternate["deck"][0],alternate["deck"][1]);
    load(a,s);load(b,alternate);action(a,0,"draw");action(b,0,"draw");
    check(view(a,1)["history"]==view(b,1)["history"],"History reveals a drawn card");
    for(const auto& h:journal(a)) {
        check(!h.contains("tasks")&&!h.contains("options")&&!h.contains("card_id"),"Journal serialized private rules payload");
        if(h["type"]=="draw_card")check(h.value("source",0)==0&&h.value("target",0)==0,"Draw journal exposes concealed handle");
    }
    a=game();s=fixture(a);s["history"]=J::array();int assassin=put(s,"bounty_hunter",0,0),punk=put(s,"prospector",1,0,true);
    load(a,s);action(a,0,"activate",assassin);choice(a,punk);
    auto recorded=view(a)["history"];bool found=false;
    for(const auto& h:recorded)if(h["type"]=="destroy"&&h["target"]==punk){found=true;check(h["target_name"]=="Punk","Destroyed punk revealed its face in journal");}
    check(found,"Missing punk destruction");action(a,0,"draw");
    for(const auto& h:journal(a))if(h["type"]=="destroy")check(h["target_name"]=="Punk","Later draw rewrote a historical name");
}

void asylumNeedsSpace() {
    auto e=game();auto s=fixture(e);const int asylum=camp(s,0,0,"jailhouse");
    std::vector<std::string> ids={"bartender","widow_with_a_shotgun","prospector","gatling_gunner","bounty_hunter","vigilante"};
    for(int i=0;i<6;++i)put(s,ids[i],0,i/2);
    const int enemy=put(s,"annie_oakley",1,0,false,1);load(e,s);
    for(const auto& a:legal(e))check(!(a["command"].value("source",0)==asylum&&a["command"].value("ability",-1)==0),"Jailhouse offered replacement on a full battlefield");
    const int removed=s["players"][0]["columns"][2][0];detach(s,removed);entity(s,removed)["zone"]="discard";entity(s,removed)["owner"]=-1;s["discard"].push_back(removed);
    load(e,s);action(e,0,"activate",asylum,0);
    for(const auto& a:legal(e)) {
        check(!a.value("placement",J::object()).contains("replace"),"Recruitment offered a sacrifice");
        check(a["placement"]["column"]==2,"Recruitment offered a full column");
    }
    choice(e,enemy);check(entity(saved(e),enemy)["owner"]==0&&entity(saved(e),enemy)["damage"]==1,"Valid Jailhouse recruitment changed damage");
}

void eventSequenceOracles() {
    const std::vector<std::string> names={"run_out_of_town","cannonade","hard_winter","box_canyon","poker_night","prairie_fire","cholera","ambush","curfew","gold_rush"};
    for(const auto& key:names) {
        auto e=game();auto s=fixture(e);
        int own=put(s,"bartender",0,0),ownHurt=put(s,"widow_with_a_shotgun",0,1,false,1);
        int rear=put(s,"prospector",1,0),front=put(s,"rustler",1,0),hurt=put(s,"vigilante",1,1,false,1);
        int eventId=put(s,key,0);
        if(key=="cannonade") {
            int ruin=camp(s,1,0,"gatling_emplacement"),damaged=camp(s,1,1,"gatling_emplacement");
            entity(s,ruin)["destroyed"]=true;entity(s,ruin)["damage"]=2;entity(s,ruin)["ready"]=false;entity(s,damaged)["damage"]=1;
        }
        // All effects start from the same public formation. Queued events must
        // finish before the turn draw; zero-delay events resolve as paid plays.
        bool immediate=key=="poker_night"||key=="ambush"||key=="curfew";
        if(!immediate){detach(s,eventId);entity(s,eventId)["zone"]="queue";s["players"][0]["queue"][0]=eventId;s["active_player"]=1;}
        load(e,s);int hand0=view(e)["players"][0]["hand_count"],hand1=view(e)["players"][1]["hand_count"];
        if(immediate)action(e,0,"play",eventId);else action(e,1,"end_turn");
        if(key=="poker_night") {
            for(int remaining=4;remaining>1;--remaining) {
                const auto choices=legal(e);
                check(choices.size()==static_cast<size_t>(remaining),"Poker Night must mark only remaining new draws");
                check(legal(e,1).empty(),"Opponent must not receive private discard choices");
                for(const auto& a:choices) {
                    const int target=a.value("target",0);
                    check(a.value("discard_choice",false)&&target>0,"Discard highlight needs an explicit target");
                    check(std::find(s["players"][0]["hand"].begin(),s["players"][0]["hand"].end(),target)==s["players"][0]["hand"].end(),"Old hand card highlighted as a Poker Night draw");
                    check(oldwest::FieldActionMatches(a,target),"Highlighted draw must offer its discard action");
                    for(const auto& other:choices)if(other["target"]!=target)
                        check(!oldwest::FieldActionMatches(a,other["target"]),"Discard action leaked to a different draw");
                }
                act(e,0,choices[0]["command"]);
            }
        }
        if(key=="run_out_of_town")choice(e,rear);
        else if(key=="prairie_fire")choice(e,-1,"lane 1");
        else if(key=="hard_winter"){choice(e,-1,"Keep Bartender");choice(e,-1,"Keep Rustler");}
        else if(key=="box_canyon")choice(e,-1,"Skip");
        else settle(e);
        auto now=saved(e);const auto observed=view(e);
        auto zone=[&](int id){return entity(now,id).value("zone",std::string());};
        auto damage=[&](int id){return entity(now,id).value("damage",0);};
        check(now["choice"].is_null()&&now["status"]=="actions",key+" left a pending sequence");
        if(key=="run_out_of_town")check(zone(rear)=="discard"&&zone(front)=="board","Run Out of Town did not ignore protection");
        if(key=="cannonade") {
            int ruins=0,damaged=0;for(const auto& col:observed["players"][1]["columns"])for(const auto& c:col)if(c["type"]=="camp"){ruins+=c["destroyed"].get<bool>();damaged+=c["damage"]==1;}
            check(ruins==2&&damaged==1,"Cannonade camp damage order/outcome wrong");
            check(view(e)["players"][0]["hand_count"]==hand0+3,"Cannonade must draw for existing plus newly ruined camps, then replenish");
        }
        if(key=="hard_winter")check(zone(own)=="board"&&zone(front)=="board"&&zone(ownHurt)=="discard"&&zone(rear)=="discard"&&zone(hurt)=="discard","Hard Winter keeper choices failed");
        if(key=="box_canyon")for(const auto& col:observed["players"][1]["columns"])for(const auto& c:col)check(!c["protected"].get<bool>(),"Box Canyon skip incorrectly canceled exposure");
        if(key=="poker_night")check(view(e)["players"][0]["hand_count"]==hand0,"Poker Night's play/draw-four/discard-three count wrong");
        if(key=="prairie_fire")check(zone(front)=="discard"&&zone(rear)=="discard"&&zone(hurt)=="board","Prairie Fire missed protected person or crossed columns");
        if(key=="cholera")check(damage(own)==1&&damage(front)==1&&damage(rear)==1&&zone(ownHurt)=="discard"&&zone(hurt)=="discard","Cholera must injure both sides including protected people");
        if(key=="ambush")check(damage(front)==1&&damage(rear)==0&&zone(hurt)=="discard"&&damage(own)==0,"Ambush failed fixed unprotected-enemy target set");
        if(key=="curfew")check(view(e)["players"][0]["hand_count"]==hand0+1&&view(e)["players"][1]["hand_count"]==hand1+3&&zone(own)=="hand"&&damage(ownHurt)==0,"Curfew failed return counts or clean hand state");
        if(key=="gold_rush") {
            int punks=0;for(const auto& col:observed["players"][0]["columns"])for(const auto& c:col)punks+=c["punk"].get<bool>();
            check(punks==3,"Gold Rush did not resolve three sequential punk gains");
        }
    }
}

// Independent expectations from the published rulings, retrieved 2026-09-08.
void printedWatchtowerEitherEvent() {
    // Physical card: ANY event this turn, including the opponent's event
    // resolved by Omen Clock. Mere placement/advancement does not qualify.
    for(int eventOwner:{0,1})for(bool raid:{false,true}) {
        auto e=game();auto s=fixture(e);int clock=camp(s,0,0,"telegraph_office"),tower=camp(s,0,1,"mountain_hideout");
        int eventId=raid?s["players"][eventOwner]["stampede"].get<int>():put(s,"box_canyon",eventOwner);
        detach(s,eventId);entity(s,eventId)["zone"]="queue";
        s["players"][eventOwner]["queue"]=J::array({0,eventId,0});
        s["players"][0]["events_resolved"]=0;s["players"][1]["events_resolved"]=0;
        auto available=[&](){for(const auto& a:legal(e))if(a["command"].value("source",0)==tower)return true;return false;};
        load(e,s);check(!available(),"Mountain Hideout activated before any event resolved");
        action(e,0,"activate",clock);choice(e,eventId);
        check(!available(),"Moving an event into slot 1 must not activate Mountain Hideout");
        s=saved(e);entity(s,clock)["ready"]=true;load(e,s);
        action(e,0,"activate",clock);choice(e,eventId);settle(e);
        check(available(),"Mountain Hideout must accept ANY resolved event, regardless of owner");
        action(e,0,"activate",tower);settle(e);
        action(e,0,"end_turn");settle(e);action(e,1,"end_turn");settle(e);
        check(!available(),"Mountain Hideout reused an event from an earlier turn");
    }
}

void printedDoomsayerChoice() {
    // Reported gameplay: a lone Box Canyon marked IMMINENT must be delayable.
    // Check both player seats and all three starting spaces, including the
    // legitimate no-room case at the back of the queue.
    for(int p:{0,1})for(int slot:{0,1,2}) {
        auto e=game();auto s=fixture(e);s["active_player"]=p;
        int doom=put(s,"pinkerton_agent",p),high=put(s,"box_canyon",1-p);
        detach(s,high);entity(s,high)["zone"]="queue";
        s["players"][1-p]["queue"][slot]=high;
        load(e,s);action(e,p,"play",doom);
        const auto pending=view(e,p)["choice"];
        check(pending.is_null()==(slot==2),"Lone Box Canyon must offer Pinkerton Agent delay except in space 3");
        if(slot<2) {
            check(pending["player"]==p,"Pinkerton Agent delay belongs to the entering player");
            choice(e,-1,"Delay");
        }
        J expected=J::array({0,0,0});expected[std::min(slot+1,2)]=high;
        check(saved(e)["players"][1-p]["queue"]==expected,"Box Canyon must move back exactly one space when possible");
    }
    for(bool delay:{false,true}) {
        auto e=game();auto s=fixture(e);int doom=put(s,"pinkerton_agent",0),first=put(s,"run_out_of_town",1),second=put(s,"cholera",1);
        for(int id:{first,second}){detach(s,id);entity(s,id)["zone"]="queue";}
        s["players"][1]["queue"]=J::array({first,second,0});load(e,s);action(e,0,"play",doom);
        check(!view(e)["choice"].is_null()&&view(e)["choice"]["player"]==0,"Pinkerton Agent's printed may requires the entering player's decision");
        check(saved(e)["players"][1]["queue"]==J::array({first,second,0}),"Enemy events moved before Pinkerton Agent's optional entry decision");
        choice(e,-1,delay?"Delay":"Skip");
        check(saved(e)["players"][1]["queue"]==(delay?J::array({0,first,second}):J::array({first,second,0})),"Pinkerton Agent must move all movable events or none, as chosen");
    }
}

void printedArgoAbility() {
    auto e=game();auto s=fixture(e);int lab=camp(s,0,0,"saloon"),argo=put(s,"wyatt_earp",0,1,false,1),punk=put(s,"bartender",0,2,true);
    load(e,s);bool labOffered=false;
    for(const auto& a:legal(e))labOffered|=a["command"].value("source",0)==lab;
    check(labOffered,"Damaged Argo retains its printed attack for Saloon even though its granting trait is inactive");
    const auto before=view(e);for(const auto& col:before["players"][0]["columns"])for(const auto& c:col)
        if(c["id"]==punk)check(c["public_abilities"].empty(),"Damaged Argo must not grant an attack to other people");
    int target=s["players"][1]["columns"][0].back();action(e,0,"activate",lab);choice(e,-1,"Wyatt Earp:");choice(e,target);
    check(entity(saved(e),target)["damage"]==1&&entity(saved(e),argo)["zone"]=="discard","Adrenaline Argo must attack then be destroyed");
}

void designerGasZeto() {
    for(int damaged=0;damaged<2;++damaged)for(int prior=0;prior<2;++prior) {
        auto e=game();auto s=fixture(e);int gas=camp(s,0,0,"coal_yard");put(s,"poker_alice",0,0,false,damaged);
        s["players"][0]["events_played"]=prior;int raiders=s["players"][0]["stampede"];
        load(e,s);action(e,0,"activate",gas);
        if(!damaged&&!prior) {
            check(view(e)["choice"]["player"]==1,"Zeto/Gas Station first launch must resolve immediately");
            check(entity(saved(e),raiders)["zone"]=="special","Immediate Stampede must leave the queue");
            choice(e);check(saved(e)["players"][0]["events_played"]==1,"Immediate launch must consume first-event benefit");
        } else check(saved(e)["players"][0]["queue"][2]==raiders,"Without active first-event Zeto, Coal Yard must launch at 3");
    }
}

void designerRescuePunk() {
    for(bool punk:{false,true}) {
        auto e=game();auto s=fixture(e);int post=camp(s,0,0,"pony_express_station");camp(s,0,1,"wanted_poster_board");
        int rescued=put(s,"blacksmith",0,0,punk),copy=put(s,"blacksmith",0,2,true);
        load(e,s);action(e,0,"activate",post);choice(e,rescued);
        bool play=false,flip=false;
        for(const auto& a:legal(e)) {
            const auto& cmd=a["command"];
            play|=cmd["type"]=="play"&&cmd.value("card",0)==rescued;
            flip|=cmd["type"]=="flip"&&cmd.value("card",0)==copy;
        }
        check(play==punk,"Pony Express Station restricts a returned faceup person, never a returned punk's hidden face");
        check(flip==punk,"Returning a punk must not prohibit faceup copies via Wanted Poster Board");
        if(punk){action(e,0,"play",rescued);settle(e);check(entity(saved(e),rescued)["zone"]=="board","Returned punk must be replayable faceup");}
    }
}

void designerMasqueradeBatch() {
    for(bool event:{false,true})for(bool skipRest:{false,true}) {
        auto e=game();auto s=fixture(e);camp(s,0,0,"wanted_poster_board");int fortress=camp(s,0,1,"wagon_fort");
        int known=put(s,"bartender",0,2,true);load(e,s);
        if(event) {
            s=saved(e);int uprising=put(s,"gold_rush",0);detach(s,uprising);entity(s,uprising)["zone"]="queue";
            s["players"][0]["queue"][0]=uprising;s["active_player"]=1;load(e,s);action(e,1,"end_turn");
        } else action(e,0,"activate",fortress);
        for(int n=0;n<3;++n) {
            choice(e,-1,(skipRest&&n>0)?"Skip":"Punk in");
            auto v=view(e);bool stillChoosing=!v["choice"].is_null();
            for(int q=0;q<2;++q){const auto observer=view(e,q);for(const auto& col:observer["players"][0]["columns"])for(const auto& c:col)if(c["punk"].get<bool>()) {
                bool expected=q==0&&(c["id"]==known||!stillChoosing);
                check(c.contains("private_peek")==expected,"Wanted Poster Board must wait until all Fortress/Uprising placements finish; opponent never peeks");
            }}
        }
        check(saved(e)["choice"].is_null(),"Punk batch must finish after its three placement/skip decisions");
    }
}

#include "audit_contract_tests.inc"
#include "drag_contract_tests.inc"

void waterBundleFilters() {
    for(int amount=1;amount<=5;++amount)for(int cost=0;cost<=5;++cost) {
        J action={{"command",{{"type","ability"},{"source",42}}},{"cost",cost}};
        check(oldwest::FieldActionMatches(action,-4000)==(cost>0),"Single water source offers every paid action and no free action");
        check(oldwest::FieldActionMatches(action,-4000-amount)==(amount==cost),"Water bundle must pay exactly its selected quantity");
    }
    J silo={{"command",{{"type","silo"}}},{"cost",1}};
    check(oldwest::FieldActionMatches(silo,-4001),"One water can stores in silo");
    check(!oldwest::FieldActionMatches(silo,-4002),"Silo cannot store multiple water");
    J choice={{"command",{{"type","choose"}}},{"category","choice"}};
    check(!oldwest::FieldActionMatches(choice,-4001),"Water cannot pay a free pending choice");
}
void forfeitPreservesBattlefield() {
    auto e=game();auto before=saved(e);
    check(!e.Forfeit(-1)&&e.SaveJson()==before.dump(),"Invalid forfeit changes nothing");
    check(e.Forfeit(1),"Either player can forfeit outside their turn");
    auto after=saved(e);
    check(e.IsFinished()&&e.Winner()==0,"Forfeit awards opponent victory");
    check(after["cards"]==before["cards"]&&after["players"]==before["players"],"Forfeit preserves battlefield and hands");
    check(after["revision"].get<int>()==before["revision"].get<int>()+1,"Forfeit advances revision");
    check(legal(e,0).empty()&&legal(e,1).empty(),"Finished game has no legal actions");
    check(!e.Forfeit(0)&&saved(e)==after,"Finished result cannot be overwritten");
    Engine selection(catalog,1);
    check(selection.Forfeit(0)&&selection.Winner()==1,"Camp selection can be forfeited");
}

int main(int argc,char** argv) {
    try {
        if(argc<2||argc>3)throw std::runtime_error("Usage: oldwest_rules_tests cards.json [test name filter]");std::ifstream f(argv[1]);catalog=std::string(std::istreambuf_iterator<char>(f),{});check(!catalog.empty(),"Missing catalog");definitions=J::parse(catalog)["cards"];
        const std::vector<std::pair<std::string,std::function<void()>>> tests={
            {"water bundle quantities",waterBundleFilters},
            {"audit camp thresholds",campThresholdContracts},{"audit Army Surgeon's Tent",designerFieldHospitalContracts},
            {"audit camp effect contracts",campEffectContracts},{"audit book worked sequences",bookWorkedSequenceContracts},
            {"damaged camp full turn cycle and UI availability",damagedCampTurnCycle},
            {"audit readiness and source contracts",readinessAndSourceContracts},
            {"printed Mountain Hideout either event",printedWatchtowerEitherEvent},
            {"printed Pinkerton Agent choice",printedDoomsayerChoice},{"printed Argo ability",printedArgoAbility},
            {"designer Gas/Zeto",designerGasZeto},{"designer Rescue Punk",designerRescuePunk},{"designer Wanted Poster Board batch",designerMasqueradeBatch},
            {"damaged protection matrix",damagedProtectionMatrix},{"Doc Holliday screenshot sequence",mutantScreenshotSequence},
            {"all event sequence outcomes",eventSequenceOracles},
            {"turn history order",battleHistoryAndTurnOrder},{"complete rolling history",completeRollingHistory},
            {"journal privacy/identity",journalPrivacyAndIdentity},{"Jailhouse requires available space",asylumNeedsSpace},
            {"public analysis selection",publicAnalysisSelection},
            {"public ability presentation",publicAbilityPresentation},
            {"public ability overview",publicAbilityOverview},
            {"spatial choice metadata",spatialChoiceMetadata},
            {"event destination metadata",eventDestinationMetadata},
            {"war room event play",warRoomEventPlay},
            {"forfeit preserves battlefield",forfeitPreservesBattlefield},{"setup/atomicity",setupAndAtomicity},{"protection/punks",protectionAndPunks},
            {"raiders/victory",raidersAndVictory},{"event clock",eventClock},{"public queue transitions",publicQueueTransitions},
            {"raid junk and punk supply",raidJunkAndPunkSupplyContracts},{"drag activation contracts",dragActivationContracts},{"direct target actions",directTargetActions},{"restore/mimic",restoreAndMimic},{"full board/resources",fullBoardAndResources},
            {"exhaustion/determinism",exhaustionAndDeterminism},{"concealed handles",concealedCardHandles},
            {"masquerade inspection schema",masqueradeInspectionSchema},
            {"mimic/vera",mimicConditionsAndVera},{"helper timing/payments",helperTimingAndPayments},
            {"helper affordability",helperAffordability},
            {"juggernaut geometry",juggernautGeometry},{"all base effects",allBaseEffects},
            {"all expansion effects",allExpansionEffects},{"expansion timing/policies",expansionTimingAndPolicies},
            {"guillotine/recruitment",guillotineAndRecruitment},{"mining/rescue",miningAndRescueRestrictions},
            {"expansion compound resolution",expansionCompoundResolution},
            {"base simulated matches",[]{simulatedMatches();}},{"expansion simulated matches",[]{simulatedMatches("boomtown");}}};
        int ran=0;for(const auto& test:tests){if(argc==3&&test.first.find(argv[2])==std::string::npos)continue;++ran;try{test.second();}catch(const std::exception& error){throw std::runtime_error(test.first+": "+error.what());}}
        check(ran>0,"No tests matched the requested filter");
        std::cout<<"PASS: "<<assertions<<" assertions\n";return 0;
    } catch(const std::exception& e){std::cerr<<"FAIL: "<<e.what()<<"\n";return 1;}
}
