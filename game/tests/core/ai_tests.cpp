#include "OldWestAI.h"
#include "OldWestRules.h"
#include "json.hpp"
#include <algorithm>
#include <chrono>
#include <fstream>
#include <iostream>
#include <set>
#include <stdexcept>
#include <string>
using J=nlohmann::ordered_json;
using oldwest::Engine;
using oldwest::AIPlayer;
using oldwest::AIDifficulty;
std::string catalog;
int assertions=0;
void check(bool ok,const std::string& message){++assertions;if(!ok)throw std::runtime_error(message);}
J saved(const Engine& e){return J::parse(e.SaveJson());}
J legal(const Engine& e,int p){return J::parse(e.LegalActionsJson(p));}
void apply(Engine& e,int p,const J& cmd){auto result=J::parse(e.Apply(p,cmd.dump()));check(result.value("ok",false),"AI command rejected: "+cmd.dump()+" / "+result.dump());}
J decide(AIPlayer& ai,const Engine& e,int p){auto before=e.SaveJson();const std::string command=ai.Choose(e.ViewJson(p),e.LegalActionsJson(p));check(!command.empty(),"AI stalled while legal actions exist");check(e.SaveJson()==before,"Decision changed authoritative state");J c=J::parse(command);bool member=false;for(const auto& a:legal(e,p))if(a["command"]==c)member=true;check(member,"AI synthesized an action outside the legal list");check(command==ai.Choose(e.ViewJson(p),e.LegalActionsJson(p)),"Repeated query changed cached decision");return c;}
Engine started(std::uint64_t seed=1){Engine e(catalog,seed,R"({"first_player":0})");for(int p=0;p<2;++p)apply(e,p,legal(e,p)[0]["command"]);return e;}
void erase(J& array,int id){for(auto it=array.begin();it!=array.end();)if(*it==id)it=array.erase(it);else ++it;}
J& card(J& s,int id){return s["cards"][std::to_string(id)];}
void detach(J& s,int id){erase(s["deck"],id);erase(s["discard"],id);for(auto& p:s["players"]){erase(p["hand"],id);for(auto& c:p["columns"])erase(c,id);for(auto& q:p["queue"])if(q==id)q=0;}}
int put(J& s,const std::string& key,int owner,int lane=-1,bool punk=false){int id=0;for(const auto& c:s["cards"])if(c["card_id"]==key&&c["zone"]!="board"){id=c["id"];break;}check(id!=0,"Missing fixture card "+key);detach(s,id);auto& c=card(s,id);c["owner"]=owner;c["zone"]=lane<0?"hand":"board";c["damage"]=0;c["destroyed"]=false;c["punk"]=punk;c["ready"]=true;c["uses"]=0;if(lane<0)s["players"][owner]["hand"].push_back(id);else s["players"][owner]["columns"][lane].insert(s["players"][owner]["columns"][lane].begin(),id);return id;}
J fixture(Engine& e){J s=saved(e);s["tasks"]=J::array();s["choice"]=nullptr;s["status"]="actions";s["active_player"]=0;s["turn"]=5;
    for(int p=0;p<2;++p){auto hand=s["players"][p]["hand"];for(int id:hand){detach(s,id);card(s,id)["zone"]="discard";card(s,id)["owner"]=-1;s["discard"].push_back(id);}s["players"][p]["water"]=3;for(auto& col:s["players"][p]["columns"])for(int id:col){card(s,id)["card_id"]="gatling_emplacement";card(s,id)["ready"]=false;card(s,id)["damage"]=0;card(s,id)["destroyed"]=false;}}
    return s;}
void load(Engine& e,const J& s){std::string error;const bool restored=e.RestoreJson(s.dump(),&error);check(restored,"Invalid fixture: "+error);}
void legalAndPrivate(){
    for(auto level:{AIDifficulty::Easy,AIDifficulty::Normal,AIDifficulty::Hard}){
        Engine a(catalog,99),b(catalog,99);AIPlayer first(catalog,level,18),second(catalog,level,18);
        check(decide(first,a,0)==decide(second,b,0),"Seeded draft not deterministic");
        auto state=saved(b);std::reverse(state["deck"].begin(),state["deck"].end());state["rng"]=91919;load(b,state);
        check(a.ViewJson(0)==b.ViewJson(0)&&a.LegalActionsJson(0)==b.LegalActionsJson(0),"Hidden-deck fixture changed public input");
        first.Reset(18);second.Reset(18);check(decide(first,a,0)==decide(second,b,0),"Hidden RNG/deck affected decision");
        apply(a,0,decide(first,a,0));check(first.Choose(a.ViewJson(0),a.LegalActionsJson(0)).empty(),"Selected player acted again during draft");
        check(first.Choose("{bad", "[]").empty(),"Malformed view did not fail closed");
        check(first.Choose("{}", "{}").empty(),"Malformed legal list did not fail closed");
    }
    auto a=started();auto state=fixture(a);int own=put(state,"widow_with_a_shotgun",0);(void)own;int enemy=put(state,"bartender",1);int punk=put(state,"prospector",1,0,true);load(a,state);
    auto b=started();auto changed=state;card(changed,enemy)["card_id"]="cornelius_ashby_railroad_baron";card(changed,punk)["card_id"]="quanah_parker";std::reverse(changed["deck"].begin(),changed["deck"].end());load(b,changed);
    check(a.ViewJson(0)==b.ViewJson(0)&&a.LegalActionsJson(0)==b.LegalActionsJson(0),"Hidden identities leaked before policy");
    for(auto level:{AIDifficulty::Easy,AIDifficulty::Normal,AIDifficulty::Hard}){AIPlayer x(catalog,level,47),y(catalog,level,47);check(decide(x,a,0)==decide(y,b,0),"Opponent hidden hand or punk affected policy");}
}
void lethalAndDefense(){
    for(auto level:{AIDifficulty::Normal,AIDifficulty::Hard}){
        auto e=started();auto s=fixture(e);int molgur=put(s,"cornelius_ashby_railroad_baron",0,0);int last=0;for(int lane=0;lane<3;++lane){int id=s["players"][1]["columns"][lane].back();last=id;if(lane<2){card(s,id)["destroyed"]=true;card(s,id)["damage"]=2;}}
        load(e,s);AIPlayer ai(catalog,level,7);auto cmd=decide(ai,e,0);check(cmd.value("source",0)==molgur,"AI missed available immediate winning activation");apply(e,0,cmd);apply(e,0,decide(ai,e,0));check(e.IsFinished()&&e.Winner()==0,"AI failed to choose final enemy camp");
        (void)last;
        e=started();s=fixture(e);int raiders=s["players"][1]["stampede"];s["players"][1]["queue"][0]=raiders;card(s,raiders)["zone"]="queue";s["active_player"]=1;int vulnerable=s["players"][0]["columns"][0][0];card(s,vulnerable)["damage"]=1;
        // Resolve an opposing Stampede already at the front of its queue.
        int scout=put(s,"rustler",1,0);load(e,s);apply(e,1,J{{"type","activate"},{"source",scout},{"ability",0}});ai.Reset(7);auto chosen=decide(ai,e,0);apply(e,0,chosen);check(card(s=saved(e),vulnerable)["damage"]==1&&!card(s,vulnerable)["destroyed"].get<bool>(),"Defender needlessly destroyed its damaged camp against Stampede");
    }
}
void victoryPrecedesRetaliation(){
    for(auto level:{AIDifficulty::Normal,AIDifficulty::Hard}){
        auto e=started();auto s=fixture(e);int attacker=put(s,"duelist",0,0);
        for(int p=0;p<2;++p)for(int lane=0;lane<3;++lane){int id=s["players"][p]["columns"][lane].back();card(s,id)["damage"]=lane==1?1:2;card(s,id)["destroyed"]=lane!=1;}
        load(e,s);AIPlayer ai(catalog,level,7);auto cmd=decide(ai,e,0);check(cmd.value("source",0)==attacker,"AI feared retaliation after an immediate win");apply(e,0,cmd);apply(e,0,decide(ai,e,0));check(e.IsFinished()&&e.Winner()==0,"AI did not finish before Duelist retaliation");
    }
}
void hardPlansTwoAttacks(){
    auto e=started();auto s=fixture(e);int cheap=put(s,"widow_with_a_shotgun",0,0),expensive=put(s,"claim_jumper",0,1),incoming=put(s,"cornelius_ashby_railroad_baron",0);(void)incoming;
    int guard=put(s,"bartender",1,0,true);(void)guard;int last=s["players"][1]["columns"][0].back();card(s,last)["damage"]=1;
    for(int lane=1;lane<3;++lane){int id=s["players"][1]["columns"][lane][0];card(s,id)["destroyed"]=true;card(s,id)["damage"]=2;}
    load(e,s);AIPlayer normal(catalog,AIDifficulty::Normal,4),hard(catalog,AIDifficulty::Hard,4);
    const J normalCmd=decide(normal,e,0),hardCmd=decide(hard,e,0);
    check(hardCmd["type"]=="activate"&&(hardCmd.value("source",0)==cheap||hardCmd.value("source",0)==expensive),"Hard missed clear-guard then lethal attack sequence");
    check(normalCmd!=hardCmd,"Hard tactical lookahead did not improve over greedy policy in designed position");
    for(int step=0;step<5&&!e.IsFinished();++step)apply(e,0,decide(hard,e,0));check(e.IsFinished()&&e.Winner()==0,"Hard did not complete planned same-turn win");
}
void siloAndDefense(){
    auto e=started();auto s=fixture(e);s["players"][0]["water"]=1;load(e,s);AIPlayer ai(catalog,AIDifficulty::Hard,7);
    auto cmd=decide(ai,e,0);check(cmd["type"]=="silo","AI failed to preserve unused water");apply(e,0,cmd);
    cmd=decide(ai,e,0);check(cmd["type"]=="end_turn","AI cycled Silo store/junk without productive use");
    e=started();s=fixture(e);put(s,"widow_with_a_shotgun",0);int campId=s["players"][0]["columns"][2][0];card(s,campId)["damage"]=1;
    put(s,"vigilante",0,0);put(s,"prospector",0,1);load(e,s);ai.Reset(3);cmd=decide(ai,e,0);check(cmd["type"]=="play"&&cmd.value("column",-1)==2,"AI did not shield exposed damaged camp");
}
void completeMatches(){
    int wins=0,draws=0,totalCommands=0;double longestMs=0;
    for(const std::string ruleset:{"base_2024","boomtown"})for(int level=0;level<3;++level)for(int sample=0;sample<3;++sample){
        Engine e(catalog,1000+sample*47+level,J{{"ruleset",ruleset}}.dump());AIPlayer a(catalog,AIDifficulty(level),701+sample),b(catalog,AIDifficulty((level+1)%3),909+sample);
        int steps=0;for(;steps<2200&&!e.IsFinished();++steps){int player=-1;for(int p=0;p<2;++p)if(!legal(e,p).empty()){player=p;break;}check(player>=0,"Unfinished match has no actor");auto start=std::chrono::steady_clock::now();J cmd=decide(player?b:a,e,player);double ms=std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-start).count();longestMs=std::max(longestMs,ms);apply(e,player,cmd);check(J::parse(e.ValidateJson())["ok"].get<bool>(),"AI match violated core invariant");}
        check(e.IsFinished(),"AI match did not terminate within 2200 commands: "+ruleset+" level="+std::to_string(level)+" sample="+std::to_string(sample));totalCommands+=steps;if(e.Winner()<0)++draws;else ++wins;
    }
    std::cout<<"AI completed 18 matches ("<<wins<<" wins, "<<draws<<" draws), "<<totalCommands<<" accepted commands; slowest checked decision "<<longestMs<<" ms\n";
}
void feedbackInvestigation(){
    J report;
    for(const std::string ruleset:{"base_2024","boomtown"}) {
        int starts[2]={0,0};
        for(int seed=1;seed<=2048;++seed) {
            Engine e(catalog,seed,J{{"ruleset",ruleset}}.dump());
            for(int p=0;p<2;++p)apply(e,p,legal(e,p)[0]["command"]);
            const int first=saved(e)["first_player"];check(first==0||first==1,"Invalid starting seat");++starts[first];
        }
        check(starts[0]>0&&starts[1]>0,"Starting seat never varied");
        report["first_player"][ruleset]={{"seeds",2048},{"seat_0",starts[0]},{"seat_1",starts[1]}};
    }
    for(bool damaged:{false,true}) {
        auto e=started();auto s=fixture(e);
        const int garden=s["players"][0]["columns"][0].back();
        card(s,garden)["card_id"]="hot_springs";card(s,garden)["ready"]=true;
        const int person=put(s,"bounty_hunter",0,0);card(s,person)["damage"]=int(damaged);card(s,person)["ready"]=!damaged;
        load(e,s);int chosen=0,available=0,paidWithoutRestore=0;
        for(const auto& a:legal(e,0))if(a["command"].value("source",0)==garden)++available;
        for(int seed=1;seed<=128;++seed){
            load(e,s);AIPlayer ai(catalog,AIDifficulty::Easy,seed);auto cmd=decide(ai,e,0);
            if(cmd.value("source",0)==garden){
                ++chosen;apply(e,0,cmd);
                for(int step=0;step<8&&!saved(e)["choice"].is_null();++step)apply(e,0,decide(ai,e,0));
                const auto result=saved(e);
                if(result["players"][0]["water"]==s["players"][0]["water"].get<int>()-2&&result["cards"][std::to_string(person)]["damage"]==int(damaged))++paidWithoutRestore;
            }
        }
        report["hot_springs"][damaged?"damaged_person":"no_damaged_person"]={{"legal_activations",available},{"easy_selections",chosen},{"paid_without_restore",paidWithoutRestore},{"samples",128}};
    }
    for(int population:{0,5,6}) {
        int skipped=0,placed=0;
        for(int seed=1;seed<=64;++seed) {
            auto e=started();auto s=fixture(e);
            const std::vector<std::string> bodies={"bounty_hunter","hellfire_preacher","pinkerton_agent","gatling_gunner","widow_with_a_shotgun","claim_jumper"};
            for(int i=0;i<population;++i)put(s,bodies[i],0,i/2);
            const int uprising=put(s,"gold_rush",0);detach(s,uprising);card(s,uprising)["zone"]="queue";
            s["players"][0]["queue"][0]=uprising;s["active_player"]=1;load(e,s);
            apply(e,1,J{{"type","end_turn"}});
            AIPlayer ai(catalog,AIDifficulty::Easy,seed);
            for(int step=0;step<8&&!saved(e)["choice"].is_null();++step){auto cmd=decide(ai,e,0);apply(e,0,cmd);}
            check(saved(e)["choice"].is_null(),"Easy stalled resolving Gold Rush");
            const auto final=saved(e);int punks=0;for(const auto& c:final["cards"])if(c.value("owner",-1)==0&&c.value("zone",std::string())=="board"&&c.value("punk",false))++punks;
            placed+=punks;if(punks==0)++skipped;
        }
        report["gold_rush"][std::to_string(population)]={{"samples",64},{"zero_punks",skipped},{"total_punks",placed}};
    }
    std::cout<<"FEEDBACK_INVESTIGATION "<<report.dump()<<"\n";
}
int main(int argc,char** argv){try{check(argc==2,"Expected catalog path");std::ifstream in(argv[1]);catalog.assign(std::istreambuf_iterator<char>(in),{});legalAndPrivate();lethalAndDefense();victoryPrecedesRetaliation();hardPlansTwoAttacks();siloAndDefense();completeMatches();feedbackInvestigation();std::cout<<"PASS "<<assertions<<" AI assertions\n";return 0;}catch(const std::exception& e){std::cerr<<"FAIL "<<e.what()<<"\n";return 1;}}
