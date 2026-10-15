#include "OldWestRules.h"
#include "../OldWestCrewCatalog.h"
#include "json.hpp"
#include <algorithm>
#include <array>
#include <functional>
#include <map>
#include <set>
#include <sstream>
#include <stdexcept>
#include <utility>
#include <vector>

namespace oldwest {
using J = nlohmann::ordered_json;
namespace {
int number(const J& j, const char* key, int fallback=0) {
    return j.contains(key) && j[key].is_number_integer() ? j[key].get<int>() : fallback;
}
std::vector<int> ints(const J& j) { return j.get<std::vector<int>>(); }
void eraseId(J& a,int id) { auto v=ints(a); v.erase(std::remove(v.begin(),v.end(),id),v.end()); a=v; }
J task(const std::string& op,int p,int s=0) { return J{{"op",op},{"player",p},{"source",s}}; }
}

struct Engine::Impl {
    J catalog, s;
    std::map<int,std::string> cosmetic;
    std::map<std::string,int> cosmeticCopies;
    void rebuildCosmetics() {
        cosmetic.clear(); cosmeticCopies.clear();
        std::vector<int> ids; for(const auto& card:s["cards"])ids.push_back(number(card,"id"));
        std::sort(ids.begin(),ids.end());
        for(int id:ids) assignCosmetic(id,ent(id).value("card_id",std::string()));
    }
    void assignCosmetic(int id,const std::string& card) {
        if(!OldWestCrew::ForCopy(card))return;
        if(const auto* entry=OldWestCrew::ForCopy(card,++cosmeticCopies[card]))
            cosmetic[id]=entry->Visual;
    }
    std::map<std::string,J> defs;
    explicit Impl(const std::string& text,std::uint64_t seed,const std::string& options) {
        catalog=J::parse(text); J opt=J::parse(options);
        for (const auto& d:catalog.at("cards")) defs[d.at("id").get<std::string>()]=d;
        s={{"version",1},{"revision",0},{"rng",seed ? seed : 0x9E3779B97F4A7C15ULL},
           {"status","selection"},{"winner",-1},{"active_player",-1},{"turn",0},
           {"first_player",number(opt,"first_player",-1)},{"reshuffles",0},{"next_id",1},
           {"cards",J::object()},{"deck",J::array()},{"discard",J::array()},
           {"players",J::array()},{"tasks",J::array()},{"choice",nullptr},{"log",J::array()},
           {"ruleset",opt.value("ruleset",std::string("base_2024"))}};
        for(int p=0;p<2;++p) s["players"].push_back(J{{"hand",J::array()},
           {"columns",J::array({J::array(),J::array(),J::array()})},{"queue",J::array({0,0,0})},
           {"water",0},{"silo",0},{"stampede",0},{"offers",J::array()},{"selected",false},
           {"entered",0},{"abilities",0},{"events_played",0},{"events_resolved",0},
           {"raids_resolved",0},{"hurt",false},{"exposed",false},{"resonator_lock",false},
           {"blocked_plays",J::array()}});
        J rules=catalog.at("rulesets").at(s["ruleset"].get<std::string>());
        for(const auto& item:rules.at("shared_deck")) {
            std::string id=item.value("card_id",item.value("id",std::string()));
            for(int n=0;n<number(item,"copies",1);++n) {
                int uid=create(id,-1,"deck"); s["deck"].push_back(uid);
            }
        }
        shuffle(s["deck"]);
        J camps=rules.at("camp_ids"); shuffle(camps);
        if(camps.size()<12) throw std::runtime_error("Camp pool must contain at least twelve camps");
        for(int p=0;p<2;++p) {
            for(int n=0;n<6;++n) player(p)["offers"].push_back(camps[p*6+n]);
            player(p)["silo"]=create("hip_flask",p,"special");
            player(p)["stampede"]=create("stampede",p,"special");
        }
    }
    J& player(int p) { return s["players"][p]; }
    const J& player(int p) const { return s["players"][p]; }
    J& ent(int id) { return s["cards"].at(std::to_string(id)); }
    const J& ent(int id) const { return s["cards"].at(std::to_string(id)); }
    const J& def(int id) const { return defs.at(ent(id)["card_id"].get<std::string>()); }
    std::string cid(int id) const { return ent(id)["card_id"].get<std::string>(); }
    std::string name(int id) const { return ent(id).value("punk",false) ? "Punk" : def(id).value("name",cid(id)); }
    std::uint64_t random() { std::uint64_t x=s["rng"].get<std::uint64_t>(); x^=x>>12; x^=x<<25; x^=x>>27; s["rng"]=x; return x*2685821657736338717ULL; }
    void shuffle(J& a) { for(std::size_t n=a.size();n>1;--n) std::swap(a[n-1],a[random()%n]); }
    int create(const std::string& card,int owner,const std::string& zone) {
        if(!defs.count(card)) throw std::runtime_error("Catalog missing "+card);
        int uid=s["next_id"]; s["next_id"]=uid+1;
        s["cards"][std::to_string(uid)]={{"id",uid},{"card_id",card},{"owner",owner},{"zone",zone},
          {"damage",0},{"destroyed",false},{"punk",false},{"ready",false},{"uses",0},{"entered_turn",-1}};
        assignCosmetic(uid,card);
        return uid;
    }
    bool isCamp(int id) const { return def(id).value("type",std::string())=="camp"; }
    bool alive(int id) const { return s["cards"].contains(std::to_string(id)) && ent(id).value("zone",std::string())=="board" && !ent(id).value("destroyed",false); }
    std::vector<int> board(int p,bool camps=true,bool people=true) const {
        std::vector<int> out; for(const auto& col:player(p)["columns"]) for(int id:ints(col))
            if(alive(id) && ((isCamp(id)&&camps)||(!isCamp(id)&&people))) out.push_back(id);
        return out;
    }
    std::pair<int,int> locate(int id) const {
        for(int p=0;p<2;++p) for(int c=0;c<3;++c) { auto a=ints(player(p)["columns"][c]);
            if(std::find(a.begin(),a.end(),id)!=a.end()) return {p,c}; }
        return {-1,-1};
    }
    int countPeople(int p) const { return int(board(p,false,true).size()); }
    int punks(int p) const { int n=0;for(int id:board(p,false,true)) if(ent(id)["punk"])++n;return n; }
    bool trait(int p,const std::string& id) const {
        for(int uid:board(p)) if(!ent(uid)["punk"].get<bool>() && cid(uid)==id && (isCamp(uid)||number(ent(uid),"damage")==0)) return true;
        return false;
    }
    int capacity(int p,int c) const { for(int id:ints(player(p)["columns"][c])) if(isCamp(id))return 2; return 3; }
    int population(int p,int c) const { int n=0;for(int id:ints(player(p)["columns"][c]))if(!isCamp(id))++n;return n; }
    bool full(int p) const { for(int c=0;c<3;++c)if(population(p,c)<capacity(p,c))return false;return true; }
    bool protectedCard(int id) const {
        auto pos=locate(id); if(pos.first<0||player(pos.first)["exposed"].get<bool>())return false;
        for(int prior:ints(player(pos.first)["columns"][pos.second])) {
            if(prior==id)return false;
            if(alive(prior))return true;
        } return false;
    }
    int ruins(int p) const { int n=0;for(const auto& col:player(p)["columns"])for(int id:ints(col))if(isCamp(id)&&ent(id)["destroyed"].get<bool>())++n;return n; }
    bool exposedCamp(int p) const { for(int id:board(p,true,false))if(!protectedCard(id))return true;return false; }
    bool finished() const { auto st=s["status"].get<std::string>();return st=="won"||st=="draw"; }
    // A separate public journal retains complete turns; the bounded animation
    // feed remains unchanged. Never store deck/hand identities or private tasks.
    std::string publicName(int id) const {
        if(!id||!s["cards"].contains(std::to_string(id)))return "";
        const auto zone=ent(id).value("zone",std::string());
        return zone=="board"||zone=="queue"||zone=="discard"||zone=="special"?name(id):"";
    }
    void history(J entry) {
        if(number(s,"turn")==0)return;
        if(!s.contains("history"))s["history"]=J::array();
        const int serial=number(s,"history_serial")+1;s["history_serial"]=serial;
        entry["sequence"]=serial;entry["revision"]=s["revision"];entry["turn"]=s["turn"];
        entry["active_player"]=s["active_player"];entry["phase"]=s["status"];
        entry["water"]=J::array({player(0)["water"],player(1)["water"]});
        s["history"].push_back(std::move(entry));
        while(!s["history"].empty()&&number(s["history"].front(),"turn")<number(s,"turn")-3)
            s["history"].erase(s["history"].begin());
    }
    void note(const std::string& kind,int p,const std::string& detail,int source=0,int target=0) {
        history(J{{"type",kind},{"player",p},{"detail",detail},{"source",source},{"target",target},
            {"source_name",publicName(source)},{"target_name",publicName(target)}});
    }
    void pay(int p,int amount,int source=0) {
        player(p)["water"]=number(player(p),"water")-amount;
        note("payment",p,"Spend "+std::to_string(amount)+" water",source);
    }
    void log(const std::string& kind,int p,int source=0,int target=0,const std::string& detail="") {
        int serial=number(s,"log_serial")+1;s["log_serial"]=serial;
        J e={{"sequence",serial},{"revision",number(s,"revision")},{"turn",s["turn"]},{"type",kind},{"player",p},{"source",source},{"target",target},{"detail",detail}};
        s["log"].push_back(e);if(s["log"].size()>80)s["log"].erase(s["log"].begin());
        e["source_name"]=publicName(source);e["target_name"]=publicName(target);
        if(target&&s["cards"].contains(std::to_string(target))) {
            e["target_owner"]=ent(target)["owner"];e["target_damage"]=ent(target)["damage"];
            const auto pos=locate(target);if(pos.second>=0)e["column"]=pos.second;
        }
        if((kind=="event_play"||kind=="raid_launch")&&p>=0) {
            const int id=kind=="event_play"?source:target;
            for(int slot=0;slot<3;++slot)if(player(p)["queue"][slot]==id)e["queue_slot"]=slot;
        }
        if(kind=="camp_advance")e["advance"]=number(ent(source),"advance");
        if((kind=="enter"||kind=="restore")&&target)e["ready"]=ent(target)["ready"];
        history(std::move(e));
    }
    void logAbility(int p,int source,int index,int copiedFrom=0) {
        // The selected public ability disambiguates multi-ability and copied
        // scenes. Numeric indices include public grants100/101; never attach
        // a hidden punk's underlying card definition to the presentation log.
        log("ability",p,source,copiedFrom);
        s["log"].back()["ability_index"]=index;
        if(s.contains("history")&&!s["history"].empty()) {
            s["history"].back()["ability_index"]=index;
            s["history"].back()["detail"]=index>=100?"Damage":def(copiedFrom?copiedFrom:source)["abilities"][index].value("effect",std::string());
        }
    }
    void logEventMove(int p,int id,int from,int to,int cause,const char* reason) {
        // Public queue positions and cause only; the authoritative mutation
        // already happened. Preserve each intermediate transition in order.
        log("event_advance",p,id);
        J& entry=s["log"].back();entry["from_slot"]=from;entry["to_slot"]=to;
        entry["cause_source"]=cause;entry["move_reason"]=reason;
        if(s.contains("history")&&!s["history"].empty()) {
            s["history"].back()["from_slot"]=from;s["history"].back()["to_slot"]=to;
            s["history"].back()["move_reason"]=reason;
        }
    }
    void win(int p,const std::string& why) { s["status"]="won";s["winner"]=p;s["choice"]=nullptr;s["tasks"]=J::array();log("victory",p,0,0,why); }
    void victory() { if(s["status"]=="selection"||finished())return;for(int p=0;p<2;++p)if(board(p,true,false).empty()){win(1-p,"All enemy camps destroyed");return;} }
    void front(const J& tasks) { J a=tasks;for(const auto& t:s["tasks"])a.push_back(t);s["tasks"]=a; }
    void push(J t) { s["tasks"].push_back(std::move(t)); }
    void detach(int id) {
        for(int p=0;p<2;++p) { eraseId(player(p)["hand"],id);for(auto& c:player(p)["columns"])eraseId(c,id);
            for(auto& e:player(p)["queue"])if(e==id)e=0; }
        eraseId(s["deck"],id);eraseId(s["discard"],id);
    }
    void discard(int id) { detach(id);ent(id)["zone"]="discard";ent(id)["owner"]=-1;ent(id)["punk"]=false;ent(id)["ready"]=false;ent(id)["damage"]=0;ent(id)["uses"]=0;s["discard"].push_back(id); }
    void destroy(int id) {
        if(!alive(id))return;
        int p=ent(id)["owner"]; player(p)["hurt"]=true;
        log("destroy",p,0,id,name(id));
        if(isCamp(id)) {
            auto pos=locate(id);ent(id)["destroyed"]=true;ent(id)["damage"]=2;ent(id)["ready"]=false;ent(id)["advance"]=0;
            eraseId(player(p)["columns"][pos.second],id);player(p)["columns"][pos.second].push_back(id);
        } else if(ent(id)["punk"].get<bool>()) {
            detach(id);ent(id)["zone"]="deck";ent(id)["owner"]=-1;ent(id)["punk"]=false;ent(id)["ready"]=false;s["deck"].insert(s["deck"].begin(),id);
        } else discard(id);
        victory();
    }
    void damage(int id,int source=0) {
        if(!alive(id))return;
        int p=ent(id)["owner"];player(p)["hurt"]=true;log("damage",1-p,source,id);
        if(ent(id)["punk"].get<bool>()||number(ent(id),"damage")>0)destroy(id);
        else { ent(id)["damage"]=1;if(!isCamp(id))ent(id)["ready"]=false; }
    }
    bool restorable(int id,int source) const { return alive(id)&&id!=source&&number(ent(id),"damage")==1&&cid(id)!="logging_camp"; }
    void restore(int id,int source,bool ready=false) {
        if(!restorable(id,source))return;
        ent(id)["damage"]=0;if(!isCamp(id))ent(id)["ready"]=ready;log("restore",ent(id)["owner"],source,id);
    }
    void toHand(int id,int p) { if(!alive(id)||isCamp(id))return;log("return",p,0,id);detach(id);ent(id)["owner"]=p;ent(id)["zone"]="hand";ent(id)["punk"]=false;ent(id)["damage"]=0;ent(id)["ready"]=false;player(p)["hand"].push_back(id); }
    bool ensureDeck() {
        if(!s["deck"].empty())return true;
        if(number(s,"reshuffles")>=1||s["discard"].empty()) {s["status"]="draw";s["choice"]=nullptr;s["tasks"]=J::array();log("draw_game",-1);return false;}
        s["deck"]=s["discard"];s["discard"]=J::array();s["reshuffles"]=1;shuffle(s["deck"]);
        for(int id:ints(s["deck"])) {ent(id)["zone"]="deck";}
        log("reshuffle",-1);return true;
    }
    int takeTop(int p,bool drawing) {
        if(finished()||!ensureDeck())return 0;
        const int hiddenId=s["deck"][0];s["deck"].erase(s["deck"].begin());
        // A public handle identifies this appearance, never the hidden physical
        // card. Catalog-order IDs and handles seen before a shuffle must not
        // reveal a punk's face or let clients track cards through a shuffle.
        // Monotonic handles also reveal no values from the private shuffle RNG.
        const int id=number(s,"next_id");s["next_id"]=id+1;
        J card=ent(hiddenId);card["id"]=id;
        // Follow the physical copy without adding identity fields to rules state.
        if(auto found=cosmetic.find(hiddenId);found!=cosmetic.end()) {
            const auto appearance=found->second; cosmetic.erase(found); cosmetic[id]=appearance;
        }
        s["cards"].erase(std::to_string(hiddenId));
        s["cards"][std::to_string(id)]=std::move(card);
        if(drawing){ent(id)["owner"]=p;ent(id)["zone"]="hand";player(p)["hand"].push_back(id);log("draw_card",p);}
        // Revised Land Office is a draw trigger, never triggered by milling or punks.
        if(drawing&&s["deck"].empty()) {
            for(int q=0;q<2;++q)if(trait(q,"land_office")){win(q,"Land Office: final deck card drawn");break;}
            if(!finished())ensureDeck();
        }
        return id;
    }
    J option(const std::string& label,J tasks) const { return J{{"label",label},{"tasks",std::move(tasks)}}; }
    void choose(int p,const std::string& prompt,J options,bool optional=false) {
        if(optional)options.push_back(option("Skip",J::array()));
        if(options.empty())return;
        for(std::size_t i=0;i<options.size();++i)options[i]["id"]=std::to_string(number(s,"revision"))+":"+std::to_string(i);
        s["choice"]={{"player",p},{"prompt",prompt},{"options",std::move(options)}};
    }
    int cost(int id,int a) const {
        std::string k=cid(id);int p=ent(id)["owner"];
        if(k=="bunkhouse"||k=="command_post_legacy")return std::max(0,3-punks(p));
        if(k=="homestead_cabin")return std::max(0,3-ruins(p));
        if(a==100)return 1;
        if(a==101)return 2;
        const auto& d=def(id);if(!d.contains("abilities")||a<0||a>=int(d["abilities"].size()))return -1;
        return number(d["abilities"][a],"cost",0);
    }
    int playCost(int id,int p,int c=-1) const {
        int n=number(def(id),"play_cost");if(def(id).value("type",std::string())=="event")return std::max(0,n-(trait(p,"cattlemen_s_club")?1:0));
        if(cid(id)=="widow_with_a_shotgun"&&c>=0)for(int camp:ints(player(p)["columns"][c]))if(isCamp(camp)&&ent(camp)["destroyed"].get<bool>())n=0;
        if(c>=0&&population(p,c)==0)for(int camp:ints(player(p)["columns"][c]))if(alive(camp)&&cid(camp)=="trading_post")--n;
        return std::max(0,n);
    }
    std::string junk(int id) const { const auto& j=def(id).at("junk");return j.is_string()?j.get<std::string>():j.value("effect",std::string()); }
    int handCount(int p) const { int n=0;for(int id:ints(player(p)["hand"]))if(cid(id)!="hip_flask")++n;return n; }
    bool blockedPlay(int p,int id) const {for(const auto& key:player(p)["blocked_plays"])if(key==cid(id))return true;return false;}
    bool anyDamaged(int p,bool peopleOnly=false,int except=0)const{for(int id:board(p,!peopleOnly,true))if(restorable(id,except))return true;return false;}
    bool condition(int id,int a,int actor=0,int controller=-1) const {
        int subject=actor?actor:id;int p=controller>=0?controller:number(ent(subject),"owner"),o=1-p;std::string k=cid(id);auto pos=locate(subject);
        if(a>=100)return true;
        if(k=="con_man")return !abilityOptions(subject,p,true).empty();
        if(k=="railroad_depot")return !parachuteOptions(subject,p).empty();
        if(k=="saloon") {
            for(int x:board(p,false,true))if(number(ent(x),"damage")>0&&!abilityOptions(x,p).empty())return true;
            return false;
        }
        if(k=="livery_barn")return countPeople(p)<=1;
        if(k=="army_fort")return number(ent(id),"damage")==0;
        if(k=="toll_bridge")return countPeople(p)>=4;
        if(k=="breaking_pen")return pos.second>=0&&population(p,pos.second)>=2;
        if(k=="bordello"||k=="barn_raising")return number(player(p),"entered")>=2;
        if(k=="mountain_hideout")return number(player(0),"events_resolved")+number(player(1),"events_resolved")>0;
        if(k=="freight_warehouse"||k=="free_homestead")return exposedCamp(o);
        if(k=="church_bell_tower")return number(player(p),"abilities")==0;
        if(k=="ringleader"&&a==1)return punks(p)>0;
        if(k=="pinkerton_agent")for(const auto& e:player(o)["queue"])if(e!=0)return true;
        if(k=="pinkerton_agent")return false;
        if(k=="hellfire_preacher"||k=="silver_mine"||k=="railroad_work_camp"||k=="undertaker"||k=="dynamite_shack"||k=="bare_knuckle_ring"||k=="revival_tent")return countPeople(p)>0;
        if(k=="timber_ram")return countPeople(p)>=6;
        if(k=="bounty_office")return punks(o)==0;
        if(k=="vigilance_committee")return handCount(p)>=5;
        if(k=="pawn_shop")return handCount(p)>=2;
        if(k=="salvage_yard")return handCount(p)>0;
        if(k=="horse_trader")return handCount(p)>=3;
        if(k=="rustlers_corral")return punks(p)>0;
        if(k=="boot_hill")return player(p)["hurt"].get<bool>();
        if(k=="dance_hall")return countPeople(p)>0&&countPeople(o)>0;
        if(k=="quaker_settlement")return number(ent(id),"damage")==a;
        if(k=="boarding_house"&&a==0)return ruins(0)+ruins(1)>0;
        if(k=="hot_springs"||k=="saloon"||k=="crimp_house")return anyDamaged(p,true,id);
        if(k=="smuggler_s_landing"){for(int q=0;q<2;++q)for(int x:board(q,false,true))if(!ent(x)["punk"].get<bool>()&&number(ent(x),"entered_turn")==number(s,"turn"))return true;return false;}
        if(k=="jailhouse"&&a==0)return anyDamaged(o,true)&&!placements(p,-1,0,false).empty();
        if(k=="army_surgeon_s_tent"&&a==0){if(pos.second<0||population(p,pos.second)>=capacity(p,pos.second))return false;for(int x:board(p,false,true))if(restorable(x,id)&&locate(x).second!=pos.second)return true;return false;}
        if(k=="pony_express_station"){for(int x:board(p,false,true))if(number(ent(x),"entered_turn")!=number(s,"turn"))return true;return false;}
        if(k=="packer_s_cabin"){for(int x:board(p))if(number(ent(x),"damage")==0)return true;return false;}
        return true;
    }
    std::vector<int> abilities(int id,bool copied=false,int controller=-1) const {
        std::vector<int> out;int p=controller>=0?controller:number(ent(id),"owner");
        if(!ent(id)["punk"].get<bool>()) {const auto& d=def(id);if(d.contains("abilities"))for(int n=0;n<int(d["abilities"].size());++n)out.push_back(n);}
        // Argo's own printed attack exists independently of its granting trait.
        // The trait supplies that attack to other people, including punks.
        if(!isCamp(id)&&trait(p,"wyatt_earp")&&(ent(id)["punk"].get<bool>()||cid(id)!="wyatt_earp"))out.push_back(100);
        if(ent(id)["punk"].get<bool>()&&trait(p,"gunsmith"))out.push_back(101);
        (void)copied;return out;
    }
    int eventDelay(int p,int id,int forced=-1)const{
        // Confirmed ruling: Zeto's first-event trait overrides Coal Yard's 3.
        if(trait(p,"poker_alice")&&number(player(p),"events_played")==0)return 0;
        return forced>=0?forced:number(def(id),"event_delay");
    }
    J punkBatch(int p,int source,int count) const {
        // Wanted Poster Board cannot inspect these faces until every placement/skip in
        // the effect is complete. Existing, already inspectable punks stay so.
        J tasks=J::array();
        for(int n=0;n<count;++n){J t=task("punk",p,source);t["defer_peek"]=true;tasks.push_back(t);}
        tasks.push_back(task("reveal_punks",p,source));return tasks;
    }
    int eventSlot(int p,int delay)const{if(delay==0)return -1;for(int x=delay-1;x<3;++x)if(player(p)["queue"][x]==0)return x;return -2;}
    J eventPlayAvailability(int id,int p) const {
        const int price=playCost(id,p),slot=eventSlot(p,eventDelay(p,id));
        std::string reason;
        if(s["status"]!="actions"||!s["choice"].is_null())reason="Finish the current choice first";
        else if(number(s,"active_player")!=p)reason="Play this event on your turn";
        else if(blockedPlay(p,id))reason="This card cannot be played again this turn";
        else if(number(player(p),"water")<price)reason="Needs "+std::to_string(price)+" water; you have "+std::to_string(number(player(p),"water"));
        else if(slot==-2)reason="No open event space at or after position "+std::to_string(eventDelay(p,id));
        return J{{"cost",price},{"event_slot",slot},{"available",reason.empty()},{"reason",reason}};
    }
    J legal(int p) const {
        J out=J::array();if(p<0||p>1||finished())return out;
        auto add=[&](std::string label,J cmd,std::string category,int water=0){J a={{"label",label},{"command",cmd},{"category",category},{"cost",water}};if(cmd.contains("source"))a["source"]=cmd["source"];if(cmd.contains("target"))a["target"]=cmd["target"];out.push_back(a);};
        if(s["status"]=="selection") {
            if(player(p)["selected"].get<bool>())return out;
            for(int a=0;a<6;++a)for(int b=0;b<6;++b)for(int c=0;c<6;++c) { if(a==b||a==c||b==c)continue;
                J ids=J::array({player(p)["offers"][a],player(p)["offers"][b],player(p)["offers"][c]});
                std::string label;for(const auto& id:ids){if(!label.empty())label+=" / ";label+=defs.at(id.get<std::string>()).value("name",id.get<std::string>());}add(label,{{"type","select_camps"},{"camps",ids}},"selection");
            }
        return out;
        }
        if(!s["choice"].is_null()) {
            if(s["choice"]["player"]!=p)return out;
            for(const auto& o:s["choice"]["options"]) {
                add(o["label"],{{"type","choose"},{"option",o["id"]}},"choice");
                if(o.contains("public_target"))out.back()["target"]=o["public_target"];
                if(o.contains("target_detail"))out.back()["target_detail"]=o["target_detail"];
                // Public spatial affordance for the choosing player. Expose
                // only destinations and already-known subjects, never task
                // lists, hidden punk identities, or future draws.
                if(!o["tasks"].empty()) {
                    const auto& t=o["tasks"][0];const std::string op=t.value("op",std::string());
                    if(op=="discard_id") {
                        out.back()["discard_choice"]=true;
                        out.back()["target"]=number(t,"target");
                    }
                    const int origin=number(t,"source");
                    if(origin>0&&!publicName(origin).empty())out.back()["choice_source"]=origin;
                    if(o.contains("placement")) out.back()["placement"]=o["placement"];
                    else if(op=="place_punk"||op=="move_id"||op=="parachute_play"||op=="recruit_id"||op=="hospital_id") {
                        J v={{"player",number(t,"player")},{"column",number(t,"column")},
                            {"position",number(t,"position")},{"card",op=="place_punk"?0:number(t,"target")},
                            {"moving",op=="move_id"||op=="recruit_id"||op=="hospital_id"},{"punk",op=="place_punk"}};
                        if(t.contains("replace"))v["replace"]=t["replace"];
                        out.back()["placement"]=std::move(v);
                    }
                    if(out.back().contains("placement"))out.back()["drag_source"]=number(t,"source");
                    if(out.back().contains("placement")&&out.back()["placement"].value("punk",false)) {
                        int remaining=1;
                        for(const auto& waiting:s["tasks"]) {
                            if(waiting.value("op",std::string())!="punk"||number(waiting,"player")!=p)break;
                            ++remaining;
                        }
                        out.back()["punk_remaining"]=remaining;
                    }
                }
            }
            return out;
        }
        if(s["active_player"]!=p||s["status"]!="actions")return out;
        int water=player(p)["water"];
        add("End turn",{{"type","end_turn"}},"turn");
        if(water>=2)add("Draw a card",{{"type","draw"}},"draw",2);
        int silo=player(p)["silo"];if(water>=1&&ent(silo)["zone"]=="special")add("Store water in Silo",{{"type","silo"}},"silo",1);
        for(int id:ints(player(p)["hand"])) {
            add("Junk "+name(id)+" — "+junk(id),{{"type","junk"},{"card",id}},"junk");
            if(junk(id)=="raid") {
                const int destination=raidDestination(p);
                if(destination!=-2)out.back()["gestures"]=J::array({J{
                    {"cards",J::array({id,number(player(p),"stampede")})},
                    {"command",J{{"type","junk"},{"card",id}}},{"event_slot",destination},
                    {"label","Junk "+name(id)+" · raid"},{"cost",0}}});
            }
            if(cid(id)=="hip_flask")continue;
            auto blocked=player(p)["blocked_plays"].get<std::vector<std::string>>();if(std::find(blocked.begin(),blocked.end(),cid(id))!=blocked.end())continue;
            if(def(id).value("type",std::string())=="event") {
                const J availability=eventPlayAvailability(id,p);
                if(availability["available"].get<bool>()){add("Play "+name(id),{{"type","play"},{"card",id}},"play_event",number(availability,"cost"));out.back()["event_slot"]=availability["event_slot"];}
            } else {
                for(int c=0;c<3;++c)if((population(p,c)<capacity(p,c)||full(p))&&water>=playCost(id,p,c)) {
                    for(const auto& placement:placements(p,c)) {
                        J cmd=placement;cmd["type"]="play";cmd["card"]=id;
                        add("Deploy "+name(id)+" to lane "+std::to_string(c+1)+", position "+std::to_string(number(cmd,"position")+1)+(cmd.contains("replace")?" (replace "+name(number(cmd,"replace"))+")":""),cmd,"play_person",playCost(id,p,c));
                    }
                }
            }
        }
        for(int id:board(p))if(ent(id)["ready"].get<bool>()&&(isCamp(id)||number(ent(id),"damage")==0)&&!player(p)["resonator_lock"].get<bool>()) {
            for(int a:abilities(id))if(cost(id,a)>=0&&water>=cost(id,a)&&condition(id,a)) {
                std::string label="Use "+name(id);if(a<100&&def(id).contains("abilities"))label+=" — "+def(id)["abilities"][a].value("effect",std::string("ability ")+std::to_string(a+1));else label+=" — Damage";
                add(label,{{"type","activate"},{"source",id},{"ability",a}},"ability",cost(id,a));
                const J gestures=activationGestures(p,id,a);
                if(!gestures.empty())out.back()["gestures"]=gestures;
            }
        }
        if(trait(p,"wanted_poster_board"))for(int id:board(p,false,true))if(ent(id)["punk"].get<bool>()&&def(id).value("type",std::string())=="person"&&!blockedPlay(p,id)){
            int c=locate(id).second;if(water>=playCost(id,p,c))add("Reveal "+def(id).value("name",cid(id)),{{"type","flip"},{"card",id}},"flip",playCost(id,p,c));
        }
        return out;
    }
    void use(int id,int p) {
        bool twice=trait(p,"charles_goodnight")&&number(ent(id),"uses")==0;
        ent(id)["uses"]=number(ent(id),"uses")+1;ent(id)["ready"]=twice&&(isCamp(id)||number(ent(id),"damage")==0);
        player(p)["abilities"]=number(player(p),"abilities")+1;
        if(cid(id)=="church_bell_tower")player(p)["resonator_lock"]=true;
    }
    // Position is an insertion index in front-to-back order, including a moving
    // camp. This permits choosing either side of an advanced Juggernaut.
    void normalizeMobileCamp(std::vector<int>& column) const {
        auto camp=std::find_if(column.begin(),column.end(),[&](int x){return x!=0&&isCamp(x);});
        if(camp==column.end()||ent(*camp)["destroyed"].get<bool>())return;
        const int id=*camp,advance=number(ent(id),"advance");
        if(advance==2||(advance==1&&column.size()==3)) {
            column.erase(camp);
            column.insert(column.begin()+(advance==2?0:1),id);
        }
    }
    J placements(int p,int onlyColumn=-1,int moving=0,bool replacement=true) const {
        J out=J::array();
        for(int c=0;c<3;++c)if(onlyColumn<0||c==onlyColumn) {
            std::vector<int> victims{0};
            if(population(p,c)>=capacity(p,c)&&locate(moving)!=std::make_pair(p,c)) {
                if(!replacement||!full(p))continue;
                victims.clear();for(int id:ints(player(p)["columns"][c]))if(!isCamp(id))victims.push_back(id);
            }
            for(int victim:victims) {
                auto col=ints(player(p)["columns"][c]);col.erase(std::remove_if(col.begin(),col.end(),[&](int x){return x==moving||x==victim;}),col.end());
                int first=0,last=int(col.size());
                if(!col.empty()&&isCamp(col.back())&&(ent(col.back())["destroyed"].get<bool>()||number(ent(col.back()),"advance")==0))--last;
                for(int x:col)if(isCamp(x)&&!ent(x)["destroyed"].get<bool>()&&number(ent(x),"advance")==2)first=1;
                std::set<std::vector<int>> arrangements;
                for(int pos=first;pos<=last;++pos) {
                    std::vector<int> placed;placed.reserve(col.size()+1);
                    for(std::size_t index=0;index<=col.size();++index) {
                        if(index==static_cast<std::size_t>(pos))placed.push_back(0);
                        if(index<col.size())placed.push_back(col[index]);
                    }
                    normalizeMobileCamp(placed);
                    if(!arrangements.insert(placed).second)continue;
                    J v={{"column",c},{"position",pos}};if(victim)v["replace"]=victim;out.push_back(v);
                }
            }
        }
        return out;
    }
    void insertPerson(int id,int p,int c,int position,bool forceReady=false,bool entry=true) {
        detach(id);auto col=ints(player(p)["columns"][c]);
        position=std::clamp(position,0,int(col.size()));col.insert(col.begin()+position,id);
        normalizeMobileCamp(col);
        player(p)["columns"][c]=col;ent(id)["owner"]=p;ent(id)["zone"]="board";
        if(entry){ent(id)["entered_turn"]=number(s,"turn");ent(id)["uses"]=0;ent(id)["ready"]=forceReady||trait(p,"quanah_parker")||(!ent(id)["punk"].get<bool>()&&(cid(id)=="quanah_parker"||cid(id)=="sarah_winnemucca"));player(p)["entered"]=number(player(p),"entered")+1;log("enter",p,0,id,name(id));entryEffects(id,p);}
    }
    void entryEffects(int id,int p) {
        if(ent(id)["punk"].get<bool>())return;
        std::string k=cid(id);J a=J::array();
        if(!def(id).value("trait",std::string()).empty())note("trait",p,def(id).value("trait",std::string()),id);
        if(k=="wyatt_earp"||k=="duelist")a.push_back(task("punk",p,id));
        if(k=="blacksmith")a.push_back(task("restore",p,id));
        if(k=="civil_war_veteran"){a.push_back(task("draw",p,id));J t=task("damage_id",p,id);t["target"]=id;a.push_back(t);}
        if(k=="pinkerton_agent")a.push_back(task("optional_push_queue",p,id));
        front(a);
    }
    void selectTargets(J t,const std::vector<int>& targets,const std::string& prompt,bool optional=false) {
        if(targets.empty())note("no_effect",number(t,"player"),prompt+": no eligible target",number(t,"source"));
        J opts=J::array();for(int id:targets){
            J effect=t;effect["target"]=id;effect["op"]=t["op"].get<std::string>()+"_id";
            J entry=option(name(id)+" (lane "+std::to_string(locate(id).second+1)+")",J::array({effect}));
            const std::string op=t["op"];
            if(op=="damage"||op=="destroy"||op=="gallows"||op=="restore") {
                std::string detail=isCamp(id)?"CAMP":"PERSON";
                detail+=number(ent(id),"damage")?" · DAMAGED":" · UNDAMAGED";
                if(op=="damage")detail+=(number(ent(id),"damage")||ent(id)["punk"].get<bool>())?" · This hit destroys it":" · This hit damages it";
                else if(op=="restore")detail+=(isCamp(id)?ent(id)["ready"].get<bool>():t.value("ready",false))?" · Restore, ready":" · Restore, not ready";
                else detail+=" · Destroy";
                entry["target_detail"]=detail;
            }
            entry["public_target"]=id;
            opts.push_back(std::move(entry));
        }
        choose(number(t,"player"),prompt,opts,optional);
    }
    void event(int id,int p) {
        detach(id);if(cid(id)=="stampede")ent(id)["zone"]="special";else discard(id);
        player(p)["events_resolved"]=number(player(p),"events_resolved")+1;
        log("event_resolve",p,id,0,def(id).value("name",cid(id)));
        J t=task("event_effect",p,id);front(J::array({t}));
    }
    void beginTurn(int p) {
        s["active_player"]=p;s["turn"]=number(s,"turn")+1;s["status"]="events";
        for(int q=0;q<2;++q){player(q)["exposed"]=false;player(q)["hurt"]=false;player(q)["entered"]=0;player(q)["abilities"]=0;player(q)["events_resolved"]=0;player(q)["raids_resolved"]=0;player(q)["events_played"]=0;player(q)["resonator_lock"]=false;player(q)["blocked_plays"]=J::array();}
        log("turn_start",p);
        note("phase",p,"Events: resolve slot 1, then advance the remaining events");
        int first=player(p)["queue"][0];player(p)["queue"][0]=0;
        push(task("advance_phase",p));push(task("replenish",p));if(first)event(first,p);
    }
    J activationTasks(int id,int a,int p,int copiedFrom=0) const {
        int source=copiedFrom?copiedFrom:id;std::string k=cid(source);J aTasks=J::array();
        auto add=[&](const std::string& op,int owner=-1){aTasks.push_back(task(op,owner<0?p:owner,id));};
        auto exact=[&](const std::string& op,int target){J t=task(op,p,id);t["target"]=target;aTasks.push_back(t);};
        auto target=[&](const std::string& op,const std::string& kind,bool any=false,int owner=-1){J t=task(op,p,id);t["kind"]=kind;t["any"]=any;t["owner"]=owner<0?1-p:owner;aTasks.push_back(t);};
        if(a>=100){target("damage","card");return aTasks;}
        if(k=="con_man"){add("copy");return aTasks;}
        if(k=="bounty_hunter"||k=="gallows"){target(k=="gallows"?"gallows":"destroy","person");}
        else if(k=="hellfire_preacher"||k=="revival_tent"){add("sacrifice");target("damage","card");}
        else if(k=="wyatt_earp"||k=="pinkerton_agent"||k=="widow_with_a_shotgun"||k=="quanah_parker"||k=="civil_war_veteran"||k=="gatling_emplacement"||k=="army_fort"||k=="bunkhouse"||k=="command_post_legacy"||k=="bordello"||k=="homestead_cabin"||k=="breaking_pen"||k=="mountain_hideout"||k=="church_bell_tower")target("damage","card");
        else if(k=="regulator")add("exterminate");
        else if(k=="gatling_gunner")add("ambush");
        else if(k=="claim_jumper"){target("damage","card");aTasks.back()["claim_jumper"]=true;}
        else if(k=="augustus_powder_pike")add("magnus");
        else if(k=="cornelius_ashby_railroad_baron"||k=="timber_ram")target("destroy","camp",true);
        else if(k=="bartender"||k=="silver_mine"){if(k=="silver_mine")add("sacrifice");add("water");}
        else if(k=="doc_holliday"){target("damage","card");aTasks.back()["optional"]=true;add("restore");exact("damage_id",id);}
        else if(k=="barn_burner")target("damage","camp");
        else if(k=="ringleader"){if(a==0)add("punk");else target("damage","card");}
        else if(k=="blacksmith"||k=="freight_warehouse"||k=="boot_hill"||k=="barn_raising")add("restore");
        else if(k=="sarah_winnemucca"||k=="pony_express_station")add(k=="pony_express_station"?"pony_express_station":"rescue");
        else if(k=="prospector"||k=="apothecary"){
            add("mill_junk");aTasks.back()["count"]=k=="prospector"?3:1;
            // Both direct and copied activations have just logged the public
            // ability. Retain that occurrence, not a later mutable card ID.
            aTasks.back()["analysis_sequence"]=number(s,"log_serial");
        }
        else if(k=="rustler"||k=="cattle_ranch"||k=="courthouse"||k=="coal_yard"||k=="cattlemen_s_club"){add("raid");if(k=="coal_yard")aTasks.back()["delay"]=3;}
        else if(k=="annie_oakley")target("damage","card",true);
        else if(k=="duelist"||k=="dance_hall"){target("damage","card");J t=task("damage",1-p,id);t["kind"]=k=="dance_hall"?"person":"card";t["owner"]=p;aTasks.push_back(t);}
        else if(k=="charles_goodnight"||k=="vigilante")target("damage","person");
        else if(k=="poker_alice"){add("draw_discard");aTasks.back()["draw"]=3;aTasks.back()["discard"]=3;aTasks.back()["restricted"]=false;}
        else if(k=="saloon")add("adrenaline");
        else if(k=="livery_barn"||k=="gunsmith"||k=="free_homestead"||k=="wanted_poster_board")add("punk");
        else if(k=="hot_springs"){add("restore");aTasks.back()["people_only"]=true;aTasks.back()["ready"]=true;}
        else if(k=="logging_camp"){exact("damage_id",id);add("restore_all");}
        else if(k=="stockyards"){add("raid");add("punk");}
        else if(k=="dynamite_shack"){target("damage","card",true);add("sacrifice");}
        else if(k=="roundup_corral"){if(a==0)add("move");else add("raid");}
        else if(k=="riverboat")add("riverboat");
        else if(k=="railroad_work_camp"){add("sacrifice");add("restore");}
        else if(k=="toll_bridge"||k=="bounty_office"){target("damage","camp",true);if(k=="bounty_office")add("punk",1-p);}
        else if(k=="undertaker"){add("sacrifice");add("draw");}
        else if(k=="telegraph_office")add("advance_event");
        else if(k=="stagecoach_station"||k=="rodeo_grounds"||k=="jailhouse"||k=="army_surgeon_s_tent"){
            if(k=="stagecoach_station"){if(a==0)add("raid");else add("restore");}
            if(k=="rodeo_grounds"){if(a==0)target("damage","person");else add("raid");}
            if(k=="jailhouse"){if(a==0)add("recruit");else add("restore");}
            if(k=="army_surgeon_s_tent"){if(a==0)add("hospital");else add("raid");}
        }
        else if(k=="railroad_depot")add("parachute");
        else if(k=="powder_magazine"){exact("destroy_id",id);add("destroy_all_people");}
        else if(k=="salvage_yard"){add("discard_payment");aTasks.back()["count"]=1;add("punk_or_water");}
        else if(k=="artillery_battery"){J t=task("damage",1-p,id);t["kind"]="card";t["owner"]=1-p;t["any"]=true;aTasks.push_back(t);}
        else if(k=="general_store"){add("draw_discard");aTasks.back()["draw"]=2;aTasks.back()["discard"]=1;aTasks.back()["restricted"]=true;}
        else if(k=="bare_knuckle_ring"){add("sacrifice");add("sacrifice",1-p);}
        else if(k=="smuggler_s_landing")add("smuggler_s_landing");
        else if(k=="rockslide_ridge")add("rockslide_ridge");
        else if(k=="packer_s_cabin"){add("harm_healthy");add("restore");}
        else if(k=="vigilance_committee"){add("discard_payment");aTasks.back()["count"]=5;target("destroy","card",true);}
        else if(k=="post_office"){add("draw");add("draw");}
        else if(k=="wagon_fort")for(const auto& t:punkBatch(p,id,3))aTasks.push_back(t);
        else if(k=="pawn_shop"){add("incinerator_payment");target("damage","card");}
        else if(k=="nitro_works"){int c=locate(id).second;for(int x:board(p,false,true))if(locate(x).second==c)exact("destroy_id",x);target("damage","card");}
        else if(k=="crimp_house")add("lobotomize");
        else if(k=="boarding_house"){if(a==1)add("raid");else{add("remove_ruin");target("damage","card");}}
        else if(k=="rustlers_corral")add("punk_or_raid");
        else if(k=="quaker_settlement"){if(a==0)add("restore");else target("damage","card");}
        else if(k=="chuckwagon")add("ready_all");
        else if(k=="horse_trader"){add("discard_payment");aTasks.back()["count"]=3;add("draw");add("draw");}
        else if(k=="lookout_ridge")add("expose_all");
        else throw std::runtime_error("Unsupported ability: "+k+"/"+std::to_string(a));
        return aTasks;
    }
    void activation(int id,int a,int p,bool free=false,int copiedFrom=0) {
        (void)free;front(activationTasks(id,a,p,copiedFrom));
    }

    // Affordances are derived from the same printed activation tasks as normal
    // play. Never simulate draws or expose hidden faces to predict a drag.
    int raidDestination(int p,int delay=2) const {
        const int raiders=number(player(p),"stampede");int slot=-1;
        for(int i=0;i<3;++i)if(player(p)["queue"][i]==raiders)slot=i;
        return slot>=0?(slot==0?-1:player(p)["queue"][slot-1]==0?slot-1:-2):
            eventSlot(p,eventDelay(p,raiders,delay));
    }
    std::vector<int> attackTargets(const J& t) const {
        const int owner=number(t,"owner",1-number(t,"player"));
        const std::string kind=t.value("kind",std::string("card"));
        std::vector<int> targets;
        for(int x:board(owner,kind!="person",kind!="camp"))
            if(t.value("any",false)||!protectedCard(x))targets.push_back(x);
        return targets;
    }
    J activationGestures(int p,int source,int ability) const {
        J out=J::array();
        const J tasks=activationTasks(source,ability,p);
        if(tasks.empty())return out;
        const J& first=tasks[0];
        const std::string op=first.value("op",std::string());
        auto command=[&](const std::string& kind) {
            return J{{"type","activate_drop"},{"source",source},{"ability",ability},{"kind",kind}};
        };
        if(op=="damage"||op=="destroy"||op=="gallows")for(int target:attackTargets(first)) {
            J cmd=command(op);cmd["target"]=target;
            out.push_back(J{{"cards",J::array({source})},{"command",cmd},{"target",target},
                {"label",std::string(op=="damage"?"Damage ":"Destroy ")+name(target)},
                {"cost",cost(source,ability)}});
        }
        if(op=="punk"||op=="punk_or_raid")for(const auto& space:placements(p)) {
            J cmd=command("punk");cmd["placement"]=space;
            J placement=space;placement["player"]=p;placement["card"]=0;placement["punk"]=true;placement["moving"]=false;
            out.push_back(J{{"cards",J::array({source})},{"command",cmd},{"placement",placement},
                {"label","Gain punk · "+name(source)},{"cost",cost(source,ability)}});
        }
        if(op=="sacrifice")for(int victim:board(p,false,true)) {
            J cmd=command("sacrifice");cmd["target"]=victim;
            out.push_back(J{{"cards",J::array({victim})},{"command",cmd},{"target",source},
                {"label","Sacrifice at "+name(source)},{"cost",cost(source,ability)}});
        }
        if(op=="move")for(int side=0;side<2;++side)for(int person:board(side,false,true))
            for(const auto& space:placements(side,-1,person,false)) {
                J cmd=command("move");cmd["target"]=person;cmd["placement"]=space;cmd["player"]=side;
                J placement=space;placement["player"]=side;placement["card"]=person;placement["moving"]=true;placement["punk"]=false;
                out.push_back(J{{"cards",J::array({person})},{"command",cmd},{"placement",placement},
                    {"label","Move via "+name(source)},{"cost",cost(source,ability)}});
            }
        if(op=="raid"||op=="punk_or_raid") {
            const int raiders=number(player(p),"stampede");
            const int destination=raidDestination(p,number(first,"delay",2));
            if(destination!=-2) {
                // A direct raid needs no further choice; the branch variant
                // chooses Raid before the ordinary effect resolves.
                J cmd=op=="raid"?J{{"type","activate"},{"source",source},{"ability",ability}}:command("raid");
                out.push_back(J{{"cards",J::array({source,raiders})},{"command",cmd},{"event_slot",destination},
                    {"label","Raid · "+name(source)},{"cost",cost(source,ability)}});
            }
        }
        return out;
    }

    void process();
    void resolve(const J& t);
    J abilityOptions(int actor,int p,bool copying=false,bool free=false) const;
    J parachuteOptions(int source,int p) const;
    J view(int p) const;
    J validate() const;
    J apply(int p,const J& cmd);
};

J Engine::Impl::abilityOptions(int actor,int p,bool copying,bool free) const {
    J options=J::array();
    auto addSource=[&](int from) {
        for(int a:abilities(from,false,from==actor?p:number(ent(from),"owner"))) {
            // A Mimic-to-Mimic hop sees the same set from the acting player's
            // perspective. Flatten it instead of offering a non-terminating cycle.
            if(cid(from)=="con_man"&&a==0)continue;
            int price=cost(from,a);
            if(price<0||(!free&&price>number(player(p),"water"))||!condition(from,a,actor,p))continue;
            J t=task("invoke",p,actor);t["from"]=from;t["ability"]=a;t["copying"]=copying;t["waive_water"]=free;
            std::string effect=a>=100?"Damage":def(from)["abilities"][a].value("effect",std::string());
            options.push_back(J{{"label",name(from)+": "+effect+" ("+std::to_string(price)+" water)"},{"tasks",J::array({t})}});
        }
    };
    if(copying) {
        for(int q=0;q<2;++q)for(int id:board(q,false,true))if(id!=actor&&number(ent(id),"damage")==0&&(q!=p||ent(id)["ready"].get<bool>()))addSource(id);
    } else {
        addSource(actor);
        if(cid(actor)=="con_man"&&!ent(actor)["punk"].get<bool>()) {
            J copies=abilityOptions(actor,p,true,free);for(auto o:copies)options.push_back(o);
        }
    }
    return options;
}

J Engine::Impl::parachuteOptions(int source,int p) const {
    J options=J::array();
    for(int x:ints(player(p)["hand"]))if(def(x).value("type",std::string())=="person"&&!blockedPlay(p,x)) {
        for(auto placement:placements(p)) {
            const int column=number(placement,"column"),play=playCost(x,p,column);
            int least=100000;
            for(int a:abilities(x)) {
                if(cid(x)=="con_man"&&a==0)continue;
                // A Hellfire Preacher can sacrifice the person being deployed: itself.
                if(cid(x)!="hellfire_preacher"&&!condition(x,a))continue;
                if(a==100&&placement.contains("replace")&&cid(number(placement,"replace"))=="wyatt_earp")continue;
                least=std::min(least,cost(x,a));
            }
            if(cid(x)=="wyatt_earp")least=std::min(least,1);
            if(cid(x)=="con_man")for(const auto& option:abilityOptions(x,p,true)) {
                const J& invoke=option["tasks"][0];const int from=number(invoke,"from");
                if(from==number(placement,"replace"))continue;
                if(number(invoke,"ability")==100&&number(ent(from),"owner")==p&&placement.contains("replace")&&cid(number(placement,"replace"))=="wyatt_earp")continue;
                least=std::min(least,cost(from,number(invoke,"ability")));
            }
            if(number(player(p),"water")<play+least)continue;
            placement["op"]="parachute_play";placement["player"]=p;placement["source"]=source;placement["target"]=x;
            options.push_back(option("Deploy "+name(x)+" in lane "+std::to_string(column+1)+", position "+std::to_string(number(placement,"position")+1),J::array({placement})));
        }
    }
    return options;
}

void Engine::Impl::process() {
    for(int step=0;!finished()&&s["choice"].is_null()&&!s["tasks"].empty();++step) {
        if(step>10000)throw std::runtime_error("Effect sequence exceeded limit");
        J t=s["tasks"][0];s["tasks"].erase(s["tasks"].begin());resolve(t);
    }
}

void Engine::Impl::resolve(const J& t) {
    const std::string op=t.at("op");int p=number(t,"player"),src=number(t,"source"),id=number(t,"target");
    auto schedule=[&](const std::string& operation,int who) {front(J::array({task(operation,who,src)}));};
    auto hitList=[&](const std::vector<int>& targets,bool lethal) {
        J todo=J::array();for(int x:targets){J a=task(lethal?"destroy_id":"damage_id",p,src);a["target"]=x;todo.push_back(a);}front(todo);
    };
    if(op=="damage"||op=="destroy"||op=="gallows") {
        const std::string kind=t.value("kind",std::string("card"));
        const int owner=number(t,"owner",1-p);
        const auto targets=attackTargets(t);
        selectTargets(t,targets,op=="damage"?"Choose a damage target":"Choose a card to destroy",t.value("optional",false));
        if(!s["choice"].is_null()) {
            std::string help;
            if(t.value("any",false))help="This effect ignores protection. ";
            else help="Only unprotected targets are eligible. Damaged people still protect cards behind them. ";
            help+=kind=="person"?"People only.":kind=="camp"?"Camps only.":"People or camps.";
            if(!t.value("any",false))for(int x:board(owner,kind!="person",kind!="camp"))if(protectedCard(x)) {
                help+="\n"+name(x)+" (lane "+std::to_string(locate(x).second+1)+"): protected by ";
                bool first=true;
                for(int guard:ints(player(owner)["columns"][locate(x).second])) {
                    if(guard==x)break;
                    if(!alive(guard))continue;
                    if(!first)help+=", ";
                    first=false;
                    help+=name(guard)+(number(ent(guard),"damage")?" [damaged]":"");
                }
            }
            s["choice"]["help"]=help;
        }
    } else if(op=="damage_id") {
        bool camp=alive(id)&&isCamp(id);damage(id,src);
        if(!finished()&&camp&&t.value("claim_jumper",false))schedule("draw",p);
    } else if(op=="destroy_id")destroy(id);
    else if(op=="restore"||op=="restore_all") {
        std::vector<int> targets;for(int x:board(p,!t.value("people_only",false),true))if(restorable(x,src))targets.push_back(x);
        J next=t;next["op"]="restore";if(op=="restore_all")next["repeat"]=true;
        selectTargets(next,targets,"Choose a card to restore",true);
    } else if(op=="restore_id") {
        restore(id,src,t.value("ready",false));
        if(t.value("repeat",false)){J again=t;again["op"]="restore_all";front(J::array({again}));}
    } else if(op=="water") {player(p)["water"]=number(player(p),"water")+1;log("water",p,src);}
    else if(op=="draw")takeTop(p,true);
    else if(op=="sacrifice") {
        J a=t;a["op"]="destroy";selectTargets(a,board(p,false,true),"Choose one of your people to sacrifice");
    } else if(op=="punk") {
        J options=J::array();for(auto v:placements(p)){v["op"]="place_punk";v["player"]=p;v["source"]=src;
            v["defer_peek"]=t.value("defer_peek",false);
            options.push_back(option("Punk in lane "+std::to_string(number(v,"column")+1)+", position "+std::to_string(number(v,"position")+1)+(v.contains("replace")?"; replace "+name(number(v,"replace")):""),J::array({v})));}
        choose(p,"Place a punk",options,true);
    } else if(op=="place_punk") {
        if(t.contains("replace"))destroy(number(t,"replace"));
        int x=takeTop(p,false);if(!x||finished())return;ent(x)["punk"]=true;ent(x)["damage"]=0;
        ent(x)["peek_deferred"]=t.value("defer_peek",false);
        insertPerson(x,p,number(t,"column"),number(t,"position"));if(s["deck"].empty()&&!finished())ensureDeck();
    } else if(op=="reveal_punks") {
        for(int x:board(p,false,true))ent(x).erase("peek_deferred");
    } else if(op=="raid") {
        int raiders=player(p)["stampede"],slot=-1;for(int q=0;q<3;++q)if(player(p)["queue"][q]==raiders)slot=q;
        if(slot>=0) {
            if(slot==0){player(p)["queue"][0]=0;event(raiders,p);}
            else if(player(p)["queue"][slot-1]==0){player(p)["queue"][slot]=0;player(p)["queue"][slot-1]=raiders;logEventMove(p,raiders,slot,slot-1,src,"raid_ability");}
            else note("no_effect",p,"Raid blocked: the next queue space is occupied",src);
        } else {
            int delay=eventDelay(p,raiders,number(t,"delay",2)),dest=eventSlot(p,delay);if(dest==-2){note("no_effect",p,"Raid blocked: no available queue space",src);return;}
            player(p)["events_played"]=number(player(p),"events_played")+1;
            if(dest==-1)event(raiders,p);else{player(p)["queue"][dest]=raiders;ent(raiders)["zone"]="queue";log("raid_launch",p,src,raiders);}
        }
    } else if(op=="advance_phase") {
        for(int q=1;q<3;++q)if(player(p)["queue"][q]!=0&&player(p)["queue"][q-1]==0){int x=player(p)["queue"][q];player(p)["queue"][q-1]=x;player(p)["queue"][q]=0;logEventMove(p,x,q,q-1,src,"turn_start");}
    } else if(op=="replenish") {
        note("phase",p,"Replenish: draw one card, then collect water");
        takeTop(p,true);if(finished())return;
        const int refill=number(s,"turn")==1?1:3;
        player(p)["water"]=number(player(p),"water")+refill;
        log("water",p,0,0,std::to_string(refill));
        s["status"]="actions";
        note("phase",p,"Actions: play, draw, junk, store water or use abilities");
    } else if(op=="optional_push_queue") {
        bool canMove=false;for(int q=0;q<2;++q)canMove|=player(1-p)["queue"][q]!=0&&player(1-p)["queue"][q+1]==0;
        if(canMove)choose(p,"Delay the opponent's events with Pinkerton Agent?",J::array({option("Delay all movable enemy events",J::array({task("push_queue",1-p,src)}))}),true);
        else note("no_effect",p,"Pinkerton Agent: no enemy event can move back",src);
    } else if(op=="push_queue") {
        for(int q=1;q>=0;--q)if(player(p)["queue"][q]!=0&&player(p)["queue"][q+1]==0){int x=player(p)["queue"][q];player(p)["queue"][q+1]=x;player(p)["queue"][q]=0;logEventMove(p,x,q,q+1,src,"queue_delay");}
    } else if(op=="advance_event") {
        J options=J::array();for(int q=0;q<2;++q)for(int slot=0;slot<3;++slot)if(player(q)["queue"][slot]!=0&&(slot==0||player(q)["queue"][slot-1]==0)){
            int x=player(q)["queue"][slot];J a=task("advance_event_id",q,src);a["target"]=x;a["slot"]=slot;
            options.push_back(option(std::string(q==p?"Your ":"Enemy ")+name(x)+" at "+std::to_string(slot+1),J::array({a})));}
        choose(p,"Choose an event to advance",options);
    } else if(op=="advance_event_id") {
        int slot=number(t,"slot");player(p)["queue"][slot]=0;
        if(slot==0)event(id,p);else {player(p)["queue"][slot-1]=id;logEventMove(p,id,slot,slot-1,src,"chosen_advance");}
    } else if(op=="event_effect") {
        std::string k=cid(src);
        if(k=="stampede"){
            player(p)["raids_resolved"]=number(player(p),"raids_resolved")+1;
            J todo=J::array();J a=task("damage",1-p,src);a["owner"]=1-p;a["kind"]="camp";a["any"]=true;todo.push_back(a);
            if(trait(p,"robbers_roost"))todo.push_back(task("water",p,src));
            if(trait(p,"courthouse"))todo.push_back(task("push_queue",1-p,src));
            front(todo);
        } else if(k=="run_out_of_town") {J a=task("destroy",p,src);a["owner"]=1-p;a["kind"]="person";a["any"]=true;front(J::array({a}));}
        else if(k=="cannonade") {front(J::array({task("bombardment_draw",p,src)}));hitList(board(1-p,true,false),false);}
        else if(k=="hard_winter")front(J::array({task("famine_keep",p,src),task("famine_keep",1-p,src)}));
        else if(k=="box_canyon") {player(1-p)["exposed"]=true;note("expose",p,"Enemy cards are unprotected for the rest of this turn",src);schedule("rearrange",p);}
        else if(k=="poker_night") {J a=task("draw_discard",p,src);a["draw"]=4;a["discard"]=3;a["restricted"]=true;front(J::array({a}));}
        else if(k=="prairie_fire")schedule("prairie_fire",p);
        else if(k=="cholera"){auto targets=board(p,false,true);auto others=board(1-p,false,true);targets.insert(targets.end(),others.begin(),others.end());hitList(targets,false);}
        else if(k=="ambush")schedule("ambush",p);
        else if(k=="curfew"){auto mine=board(p,false,true),theirs=board(1-p,false,true);for(int x:mine)toHand(x,p);for(int x:theirs)toHand(x,1-p);}
        else if(k=="gold_rush")front(punkBatch(p,src,3));
        else throw std::runtime_error("Unsupported event: "+k);
    } else if(op=="bombardment_draw") {
        int n=ruins(1-p);for(int i=0;i<n&&!finished();++i)takeTop(p,true);
    } else if(op=="ambush"||op=="exterminate") {
        std::vector<int> targets;for(int x:board(1-p,false,true))if(op=="ambush"?!protectedCard(x):number(ent(x),"damage")>0)targets.push_back(x);hitList(targets,op=="exterminate");
    } else if(op=="magnus"||op=="prairie_fire") {
        J options=J::array();for(int c=0;c<3;++c){J todo=J::array();for(int x:ints(player(1-p)["columns"][c]))if(alive(x)&&(op=="magnus"||!isCamp(x))){J a=task(op=="magnus"?"damage_id":"destroy_id",p,src);a["target"]=x;todo.push_back(a);}if(!todo.empty())options.push_back(option("Enemy lane "+std::to_string(c+1),todo));}
        choose(p,"Choose an enemy lane",options);
    } else if(op=="destroy_all_people") {
        auto targets=board(p,false,true);auto other=board(1-p,false,true);targets.insert(targets.end(),other.begin(),other.end());hitList(targets,true);
    } else if(op=="famine_keep") {
        auto people=board(p,false,true);if(people.size()<2)return;J options=J::array();
        for(int keep:people){J todo=J::array();for(int x:people)if(x!=keep){J a=task("destroy_id",p,src);a["target"]=x;todo.push_back(a);}options.push_back(option("Keep "+name(keep)+" in lane "+std::to_string(locate(keep).second+1),todo));}
        choose(p,"Choose the one person you keep",options);
    } else if(op=="rescue")selectTargets(t,board(p,false,true),"Return a person to your hand");
    else if(op=="rescue_id")toHand(id,p);
    else if(op=="draw_discard") {
        J drawn=J::array();for(int n=0;n<number(t,"draw")&&!finished();++n){int x=takeTop(p,true);if(x)drawn.push_back(x);}
        if(finished())return;
        J a=task("discard_payment",p,src);a["count"]=number(t,"discard");if(t.value("restricted",false))a["eligible"]=drawn;front(J::array({a}));
    } else if(op=="discard_payment") {
        int count=number(t,"count",1);if(count<=0)return;J options=J::array();
        auto eligible=t.contains("eligible")?ints(t["eligible"]):ints(player(p)["hand"]);
        for(int x:eligible)if(ent(x)["zone"]=="hand"&&ent(x)["owner"]==p&&cid(x)!="hip_flask"){
            J a=task("discard_id",p,src);a["target"]=x;J again=t;again["count"]=count-1;
            options.push_back(option("Discard "+name(x),J::array({a,again})));}
        choose(p,"Discard "+std::to_string(count)+" card(s)",options);
    } else if(op=="discard_id") {log("discard",p,src,id,name(id));discard(id);}
    else if(op=="mill_junk") {
        const int analysis=number(t,"analysis_sequence");
        J options=J::array();
        for(int n=0;n<number(t,"count",1)&&!finished();++n){
            int x=takeTop(p,false);if(!x)break;
            const std::string effect=junk(x),label=name(x);
            log("reveal_discard",p,src,x,label);
            if(analysis>0){
                J& entry=s["log"].back();entry["analysis_sequence"]=analysis;
                entry["reveal_index"]=n;entry["junk_effect"]=effect;
            }
            discard(x);
            J a=task("junk_effect",p,src);a["effect"]=effect;
            J selected=option(label+": "+effect,J::array({a}));
            // Keep the original reveal ordinal even if this effect currently
            // has no target. Selection must not prune or reorder legal options.
            if(analysis>0)selected["analysis"]={{"source",src},{"analysis_sequence",analysis},
                {"target",x},{"reveal_index",n},{"junk_effect",effect},{"selection","selected"}};
            options.push_back(std::move(selected));
            if(s["deck"].empty())ensureDeck();
        }
        if(!finished()){
            choose(p,"Use one revealed junk effect",options,true);
            // The ordinary optional choice adds Skip last; retain its exact
            // command/label and empty effect list. This metadata stays private
            // until that option is actually accepted.
            if(analysis>0)s["choice"]["options"].back()["analysis"]={{"source",src},{"analysis_sequence",analysis},
                {"target",0},{"reveal_index",-1},{"junk_effect",""},{"selection","skip"}};
        }
    } else if(op=="junk_effect") {
        std::string effect=t.at("effect");J a=task(effect=="injure"?"damage":effect,p,src);
        if(effect=="injure"){a["kind"]="person";a["owner"]=1-p;}
        front(J::array({a}));
    } else if(op=="punk_or_water")choose(p,"Choose a resource",J::array({option("Gain a punk",J::array({task("punk",p,src)})),option("Gain 1 water",J::array({task("water",p,src)}))}));
    else if(op=="move") {
        J options=J::array();for(int q=0;q<2;++q)for(int x:board(q,false,true))for(auto v:placements(q,-1,x,false)) {
            v["op"]="move_id";v["player"]=q;v["source"]=src;v["target"]=x;
            options.push_back(option(std::string(q==p?"Your ":"Enemy ")+name(x)+" to lane "+std::to_string(number(v,"column")+1)+", position "+std::to_string(number(v,"position")+1),J::array({v})));}
        choose(p,"Choose a person and destination",options);
    } else if(op=="move_id") {insertPerson(id,p,number(t,"column"),number(t,"position"),false,false);log("move",p,src,id);}
    else if(op=="riverboat") {
        auto where=locate(src);if(where.first<0)return;int advance=(number(ent(src),"advance")+1)%3;ent(src)["advance"]=advance;
        auto col=ints(player(p)["columns"][where.second]);col.erase(std::remove(col.begin(),col.end(),src),col.end());col.insert(col.begin()+std::min(int(col.size()),2-advance),src);player(p)["columns"][where.second]=col;
        if(advance==0){J a=task("destroy",1-p,src);a["owner"]=1-p;a["kind"]="camp";a["any"]=true;front(J::array({a}));}log("camp_advance",p,src);
    } else if(op=="copy") {
        J options=abilityOptions(src,p,true);for(auto& o:options)o["tasks"][0]["already_used"]=true;
        choose(p,"Choose an ability for Con Man",options);
    }
    else if(op=="invoke") {
        int from=number(t,"from",src),a=number(t,"ability"),price=t.value("waive_water",false)?0:cost(from,a);
        if(price<0||price>number(player(p),"water")||!condition(from,a,src,p))throw std::runtime_error("Chosen ability is no longer payable");
        pay(p,price,src);
        // Con Man's ordinary action has already used it; a helper activates its
        // subject here. Copying does not exhaust the copied person.
        if(!t.value("already_used",false))use(src,p);
        logAbility(p,src,a,from);activation(src,a,p,false,from);
    } else if(op=="adrenaline") {
        J options=J::array();for(int x:board(p,false,true))if(number(ent(x),"damage")>0)for(auto o:abilityOptions(x,p)) {
            J death=task("destroy_id",p,src);death["target"]=x;o["tasks"].push_back(death);options.push_back(o);}
        choose(p,"Activate a damaged person, then destroy it",options);
    } else if(op=="parachute") {
        choose(p,"Choose a person for immediate activation",parachuteOptions(src,p));
    } else if(op=="parachute_play") {
        int price=playCost(id,p,number(t,"column"));pay(p,price,src);
        if(t.contains("replace"))destroy(number(t,"replace"));
        J invoke=task("helper_ability",p,id),hurt=task("damage_id",p,src);hurt["target"]=id;front(J::array({invoke,hurt}));
        ent(id)["damage"]=0;insertPerson(id,p,number(t,"column"),number(t,"position"));
    } else if(op=="helper_ability") {
        if(alive(src))choose(p,"Choose the deployed person's ability",abilityOptions(src,p));
    } else if(op=="ready_all") {for(int x:board(p))if(x!=src&&(isCamp(x)||number(ent(x),"damage")==0)){ent(x)["ready"]=true;note("ready",p,"Ready",src,x);}}
    else if(op=="punk_or_raid")choose(p,"Choose a punk or a raid",J::array({option("Gain a punk",J::array({task("punk",p,src)})),option("Raid",J::array({task("raid",p,src)}))}));
    else if(op=="expose_all") {player(0)["exposed"]=true;player(1)["exposed"]=true;log("expose_all",p,src);}
    else if(op=="harm_healthy") {
        std::vector<int> targets;for(int x:board(p))if(number(ent(x),"damage")==0)targets.push_back(x);
        J a=t;a["op"]="damage";selectTargets(a,targets,"Choose your undamaged card to damage");
    } else if(op=="smuggler_s_landing") {
        J options=J::array();for(int q=0;q<2;++q)for(int x:board(q,false,true))if(!ent(x)["punk"].get<bool>()&&number(ent(x),"entered_turn")==number(s,"turn")) {
            J a=task("junk_effect",p,src);a["effect"]=junk(x);
            options.push_back(option(name(x)+": "+junk(x),J::array({a})));
        }
        choose(p,"Use an entered person's junk effect",options);
    } else if(op=="recruit"||op=="hospital") {
        J options=J::array();int owner=op=="recruit"?1-p:p,column=op=="hospital"?locate(src).second:-1;
        for(int x:board(owner,false,true))if(number(ent(x),"damage")==1&&(op!="hospital"||locate(x).second!=column)) {
            for(auto v:placements(p,column,0,false)) {
                v["op"]=op+"_id";v["player"]=p;v["source"]=src;v["target"]=x;
                options.push_back(option(name(x)+" to lane "+std::to_string(number(v,"column")+1)+", position "+std::to_string(number(v,"position")+1),J::array({v})));
            }
        }
        choose(p,op=="recruit"?"Recruit a damaged enemy":"Move and restore a damaged person",options);
    } else if(op=="recruit_id"||op=="hospital_id") {
        if(t.contains("replace"))destroy(number(t,"replace"));
        insertPerson(id,p,number(t,"column"),number(t,"position"),false,false);
        if(op=="hospital_id")restore(id,src);
        log(op,p,src,id);
    } else if(op=="rockslide_ridge") {
        J options=J::array();for(int c=0;c<3;++c) {
            J todo=J::array();for(int x:ints(player(1-p)["columns"][c]))if(alive(x)&&!isCamp(x)){J a=task("destroy_id",p,src);a["target"]=x;todo.push_back(a);}
            for(int x:ints(player(1-p)["columns"][c]))if(alive(x)&&isCamp(x)){J a=task("damage_id",p,src);a["target"]=x;todo.push_back(a);}
            J death=task("destroy_id",p,src);death["target"]=src;todo.push_back(death);
            options.push_back(option("Strike enemy lane "+std::to_string(c+1),todo));
        }
        choose(p,"Choose Rockslide Ridge's target lane",options);
    } else if(op=="remove_ruin") {
        std::vector<int> targets;for(int q=0;q<2;++q)for(const auto& col:player(q)["columns"])for(int x:ints(col))if(isCamp(x)&&ent(x)["destroyed"].get<bool>())targets.push_back(x);
        selectTargets(t,targets,"Remove a ruined camp to open its space");
    } else if(op=="remove_ruin_id") {detach(id);ent(id)["zone"]="removed";log("remove_ruin",p,src,id);}
    else if(op=="pony_express_station") {
        std::vector<int> targets;for(int x:board(p,false,true))if(number(ent(x),"entered_turn")!=number(s,"turn"))targets.push_back(x);
        selectTargets(t,targets,"Recover a person for a later turn");
    } else if(op=="pony_express_station_id") {
        // Confirmed ruling: returning a punk imposes no restriction on its hidden
        // face or on other punks. Capture its public identity before toHand.
        if(!ent(id)["punk"].get<bool>())player(p)["blocked_plays"].push_back(cid(id));
        toHand(id,p);
    }
    else if(op=="incinerator_payment") {
        int remaining=number(t,"remaining",2);J picked=t.value("picked",J::array());
        if(remaining==0){J a=task("junk_sequence",p,src);a["effects"]=picked;front(J::array({a}));return;}
        J options=J::array();for(int x:ints(player(p)["hand"]))if(cid(x)!="hip_flask") {
            J discardTask=task("discard_id",p,src);discardTask["target"]=x;
            J again=t;again["remaining"]=remaining-1;again["picked"]=picked;again["picked"].push_back(J{{"name",name(x)},{"effect",junk(x)}});
            options.push_back(option("Discard "+name(x),J::array({discardTask,again})));
        }
        choose(p,"Discard "+std::to_string(remaining)+" card(s) for Pawn Shop",options);
    } else if(op=="junk_sequence") {
        J options=J::array();const J& effects=t["effects"];
        for(std::size_t index=0;index<effects.size();++index) {
            J effect=task("junk_effect",p,src);effect["effect"]=effects[index]["effect"];
            J again=t;again["effects"].erase(again["effects"].begin()+index);
            options.push_back(option(effects[index]["name"].get<std::string>()+": "+effects[index]["effect"].get<std::string>(),J::array({effect,again})));
        }
        if(!options.empty())choose(p,"Use a discarded junk effect",options,true);
    } else if(op=="lobotomize") {
        std::vector<int> targets;for(int x:board(p,false,true))if(restorable(x,src))targets.push_back(x);
        selectTargets(t,targets,"Restore a person and test Crimp House");
    } else if(op=="lobotomize_id") {
        auto location=locate(id);auto column=ints(player(p)["columns"][location.second]);
        int position=int(std::find(column.begin(),column.end(),id)-column.begin());restore(id,src);bool injure=false;
        for(int n=0;n<3&&!finished();++n) {
            int x=takeTop(p,false);if(!x)break;injure=injure||junk(x)=="injure";log("reveal_discard",p,src,x,name(x));discard(x);
            if(s["deck"].empty())ensureDeck();
        }
        if(injure&&!finished()) {
            destroy(id);int x=takeTop(p,false);if(!x||finished())return;ent(x)["punk"]=true;ent(x)["damage"]=0;
            insertPerson(x,p,location.second,position);if(s["deck"].empty())ensureDeck();
            if(!finished())front(J::array({task("water",p,src)}));
        }
    } else if(op=="gallows_id") {
        const int owner=number(ent(id),"owner");const bool wasPunk=ent(id)["punk"].get<bool>();auto original=abilities(id);
        destroy(id);if(finished())return;J options=J::array();
        if(wasPunk) {
            for(int a:original)if(a>=100){J invoke=task("invoke",owner,id);invoke["from"]=id;invoke["ability"]=a;invoke["waive_water"]=true;invoke["already_used"]=true;options.push_back(option("Punk: Damage (free)",J::array({invoke})));}
        } else {
            options=abilityOptions(id,owner,false,true);
            for(auto& choice:options)choice["tasks"][0]["already_used"]=true;
        }
        choose(owner,"Use the destroyed person's ability for free?",options,true);
    }
    else if(op=="rearrange") {
        J start=task("rearrange_next",p,src);start["remaining"]=board(p,false,true);start["columns"]=J::array();
        for(int c=0;c<3;++c){J col=J::array();for(int x:ints(player(p)["columns"][c]))if(isCamp(x))col.push_back(x);start["columns"].push_back(col);}
        if(!start["remaining"].empty())choose(p,"Rearrange your people?",J::array({option("Rearrange",J::array({start}))}),true);
    } else if(op=="rearrange_next") {
        if(t["remaining"].empty()){player(p)["columns"]=t["columns"];log("rearrange",p,src);return;}
        J options=J::array();int x=t["remaining"][0];
        for(int c=0;c<3;++c){auto col=ints(t["columns"][c]);int people=0;for(int v:col)if(!isCamp(v))++people;if(people>=capacity(p,c))continue;
            int last=int(col.size());if(!col.empty()&&isCamp(col.back())&&(ent(col.back())["destroyed"].get<bool>()||number(ent(col.back()),"advance")==0))--last;
            for(int pos=0;pos<=last;++pos){
                J a=t;a["remaining"].erase(a["remaining"].begin());auto dest=col;
                dest.insert(dest.begin()+pos,x);normalizeMobileCamp(dest);a["columns"][c]=dest;
                J o=option(name(x)+" to lane "+std::to_string(c+1)+", position "+std::to_string(pos+1),J::array({a}));
                int campIndex=-1,campRow=2,subject=0;
                for(int i=0;i<int(dest.size());++i){if(dest[i]==x)subject=i;if(isCamp(dest[i])){campIndex=i;campRow=2-number(ent(dest[i]),"advance");}}
                const int row=campIndex<0?3-int(dest.size())+subject:campRow+subject-campIndex;
                // A scalar preview of this public person's planned position.
                // The private resolution task and partial formation stay server-side.
                o["placement"]={{"player",p},{"column",c},{"position",pos},{"card",x},{"moving",true},{"punk",false},{"row",row}};
                options.push_back(std::move(o));
            }}
        choose(p,"Rearrange: place "+name(x),options);
    } else throw std::runtime_error("Unsupported effect: "+op);
}

J Engine::Impl::apply(int p,const J& command) {
    if(p<0||p>1||!command.is_object())throw std::runtime_error("Invalid player or command");
    J cmd=command;
    if(cmd.contains("revision")) {
        if(!cmd["revision"].is_number_integer()||cmd["revision"]!=s["revision"])throw std::runtime_error("State changed; refresh before acting");
        cmd.erase("revision");
    }
    // Compare objects without imposing the serializer's member order.
    bool permitted=false;J action;
    const nlohmann::json canonical=nlohmann::json::parse(cmd.dump());
    for(const auto& a:legal(p)) {
        if(nlohmann::json::parse(a["command"].dump())==canonical){permitted=true;action=a;break;}
        for(const auto& gesture:a.value("gestures",J::array()))
            if(nlohmann::json::parse(gesture["command"].dump())==canonical){permitted=true;action=a;break;}
        if(permitted)break;
    }
    if(!permitted)throw std::runtime_error("That action is not legal in this state");
    s["revision"]=number(s,"revision")+1;
    std::string type=cmd.at("type");
    if(type!="select_camps"&&type!="choose")note("action",p,action.value("label",std::string()));
    if(type=="select_camps") {
        player(p)["selected"]=true;
        for(int c=0;c<3;++c){int id=create(cmd["camps"][c],p,"board");ent(id)["ready"]=true;ent(id)["damage"]=cid(id)=="army_fort"?1:0;ent(id)["advance"]=cid(id)=="wagon_fort"?1:0;player(p)["columns"][c].push_back(id);}
        if(player(0)["selected"].get<bool>()&&player(1)["selected"].get<bool>()) {
            s["status"]="setup";
            for(int q=0;q<2&&!finished();++q){int opening=0;for(int id:board(q,true,false))opening+=number(def(id),"starting_cards");for(int n=0;n<opening&&!finished();++n)takeTop(q,true);}
            if(!finished()){int first=number(s,"first_player",-1);if(first<0)first=int(random()%2);s["first_player"]=first;beginTurn(first);}
        }
    } else if(type=="choose") {
        J tasks,analysis;bool found=false;
        for(const auto& o:s["choice"]["options"])if(o["id"]==cmd["option"]){
            tasks=o["tasks"];analysis=o.value("analysis",J());found=true;break;
        }
        if(!found)throw std::runtime_error("Choice expired");
        // All accepted choices in this catalog choose public targets, reveal a
        // paid/discarded card, or select a public effect. Do not expose options.
        note("choice",p,s["choice"].value("prompt",std::string())+": "+action.value("label",std::string()));
        if(!analysis.is_null()){
            // Only revealed-junk alternatives carry this internal annotation.
            // Publish the accepted decision before its effects run, including
            // Skip/no-target outcomes, without serializing private task data.
            log("analysis_choice",p,number(analysis,"source"),number(analysis,"target"));
            J& entry=s["log"].back();entry["analysis_sequence"]=analysis["analysis_sequence"];
            entry["reveal_index"]=analysis["reveal_index"];entry["junk_effect"]=analysis["junk_effect"];
            entry["selection"]=analysis["selection"];
        }
        s["choice"]=nullptr;front(tasks);
    } else if(type=="end_turn") {
        const int unspent=number(player(p),"water");player(p)["water"]=0;
        note("cleanup",p,"Return "+std::to_string(unspent)+" unspent water; ready camps and undamaged people");
        for(int x:board(p)){ent(x)["uses"]=0;ent(x)["ready"]=isCamp(x)||number(ent(x),"damage")==0;}
        log("turn_end",p);beginTurn(1-p);
    } else if(type=="draw") {pay(p,2);takeTop(p,true);}
    else if(type=="silo") {
        int id=player(p)["silo"];pay(p,1);ent(id)["zone"]="hand";player(p)["hand"].push_back(id);log("store_water",p);
    } else if(type=="junk") {
        int id=cmd.at("card");std::string effect=junk(id);log("junk",p,0,id,name(id));
        if(cid(id)=="hip_flask"){detach(id);ent(id)["zone"]="special";}else discard(id);
        J a=task("junk_effect",p);a["effect"]=effect;push(a);
    } else if(type=="play") {
        int id=cmd.at("card"),c=number(cmd,"column",-1);pay(p,playCost(id,p,c));
        if(def(id).value("type",std::string())=="event") {
            int slot=eventSlot(p,eventDelay(p,id));detach(id);player(p)["events_played"]=number(player(p),"events_played")+1;
            if(slot==-1)event(id,p);else{player(p)["queue"][slot]=id;ent(id)["zone"]="queue";log("event_play",p,id);}
        } else {
            if(cmd.contains("replace"))destroy(number(cmd,"replace"));
            ent(id)["damage"]=0;ent(id)["destroyed"]=false;insertPerson(id,p,c,number(cmd,"position"));
        }
    } else if(type=="activate"||type=="activate_drop") {
        int id=cmd.at("source"),a=number(cmd,"ability");pay(p,cost(id,a),id);use(id,p);logAbility(p,id,a);activation(id,a,p);
        if(type=="activate_drop") {
            const std::string kind=cmd.at("kind");
            auto accept=[&](const std::function<bool(const J&)>& matches) {
                process();
                if(finished())return;
                if(s["choice"].is_null()||s["choice"]["player"]!=p)throw std::runtime_error("Drop choice is no longer available");
                J selected;
                for(const auto& o:s["choice"]["options"])if(!o["tasks"].empty()&&matches(o["tasks"][0])) {
                    if(!selected.is_null())throw std::runtime_error("Ambiguous drop destination");
                    selected=o;
                }
                if(selected.is_null())throw std::runtime_error("Drop destination is no longer legal");
                note("choice",p,s["choice"].value("prompt",std::string())+": "+selected.value("label",std::string()));
                s["choice"]=nullptr;front(selected["tasks"]);
            };
            if(activationTasks(id,a,p)[0].value("op",std::string())=="punk_or_raid")
                accept([&](const J& t){return t.value("op",std::string())==kind;});
            if(kind!="raid")accept([&](const J& t){
                if(kind=="damage"||kind=="destroy"||kind=="gallows")return t.value("op",std::string())==kind+"_id"&&number(t,"target")==number(cmd,"target");
                if(kind=="sacrifice")return t.value("op",std::string())=="destroy_id"&&number(t,"target")==number(cmd,"target");
                if(t.value("op",std::string())!=(kind=="punk"?"place_punk":"move_id"))return false;
                if(kind=="move"&&(number(t,"target")!=number(cmd,"target")||number(t,"player")!=number(cmd,"player")))return false;
                const J& space=cmd["placement"];
                return number(t,"column",-1)==number(space,"column",-1)&&number(t,"position",-1)==number(space,"position",-1)&&
                    number(t,"replace")==number(space,"replace");
            });
        }
    } else if(type=="flip") {
        int id=cmd.at("card");pay(p,playCost(id,p,locate(id).second));
        ent(id)["punk"]=false;ent(id)["ready"]=true;ent(id)["uses"]=0;ent(id)["entered_turn"]=s["turn"];player(p)["entered"]=number(player(p),"entered")+1;entryEffects(id,p);log("reveal_person",p,0,id,name(id));
    }
    process();return J{{"ok",true},{"revision",s["revision"]}};
}

J Engine::Impl::view(int p) const {
    if(p<0||p>1)throw std::runtime_error("Invalid viewer");
    auto visible=[&](int id,bool reveal) {
        const J& e=ent(id);bool punk=e.value("punk",false);
        J v={{"id",id},{"owner",e["owner"]},{"zone",e["zone"]},{"punk",punk},{"damage",e["damage"]},{"destroyed",e["destroyed"]},{"ready",e["ready"]},{"uses",e["uses"]},{"protected",alive(id)&&protectedCard(id)}};
        if(!punk){v["card_id"]=cid(id);v["name"]=def(id).value("name",cid(id));v["type"]=def(id).value("type",std::string());}
        else {
            // Inspection does not flip the card or change its battlefield type.
            // Keep the renderer-facing identity independent of the hidden face.
            v["name"]="Punk";v["type"]="person";
            if(reveal&&!e.value("peek_deferred",false)) {
                J peek={{"card_id",cid(id)},{"name",def(id).value("name",cid(id))},{"type",def(id).value("type",std::string())}};
                std::string reason;
                if(def(id).value("type",std::string())!="person")reason="This event stays a punk. Wanted Poster Board cannot flip events into play.";
                else {
                    const int price=playCost(id,p,locate(id).second);
                    peek["flip_cost"]=price;
                    if(s["status"]!="actions")reason="Flips are available during Actions.";
                    else if(!s["choice"].is_null())reason="Finish the current choice first.";
                    else if(number(s,"active_player")!=p)reason="Flip this punk on your turn.";
                    else if(blockedPlay(p,id))reason="Pony Express Station prevents playing this person again this turn.";
                    else if(number(player(p),"water")<price)reason="Needs "+std::to_string(price)+" water; you have "+std::to_string(number(player(p),"water"))+".";
                }
                peek["flip_available"]=reason.empty();peek["flip_reason"]=reason;
                v["private_peek"]=peek;
            }
        }
        if(isCamp(id))v["advance"]=number(e,"advance");
        // Effective event cost and play blockers belong only to the owner's
        // hand. The UI must not infer payment from the printed catalog cost.
        if(e["zone"]=="hand"&&number(e,"owner")==p&&def(id).value("type",std::string())=="event")
            v["play_availability"]=eventPlayAvailability(id,p);
        if(e["zone"]=="board") {
            v["protected_by"]=J::array();
            if(alive(id)&&protectedCard(id))for(int guard:ints(player(locate(id).first)["columns"][locate(id).second])) {
                if(guard==id)break;
                if(alive(guard))v["protected_by"].push_back(J{{"id",guard},{"name",name(guard)},{"damage",ent(guard)["damage"]}});
            }
            // The battle overview shows every printed/granted public ability,
            // even while exhausted. Availability still comes from legal().
            // Never expose condition() here: some conditions inspect a hand.
            v["public_abilities"]=J::array();
            if(number(e,"owner")==p)v["ability_availability"]=J::array();
            for(int a:abilities(id)) {
                J ability={{"index",a},{"cost",cost(id,a)},
                    {"effect",a>=100?std::string("Damage"):def(id)["abilities"][a].value("effect",std::string())}};
                if(cid(id)=="pawn_shop"&&a==0)ability["activation_label"]="Activate: "+std::to_string(cost(id,a))+" water + discard 2 hand cards (not Hip Flask)";
                if(a>=100)ability["granted_by"]=a==100?"Wyatt Earp":"Gunsmith";
                // Availability explanations belong only to the owning viewer:
                // prerequisites can inspect their private hand. Opponents get
                // printed public information without a hidden-condition oracle.
                if(number(e,"owner")==p) {
                    std::string reason;
                    if(!alive(id))reason="This camp is destroyed";
                    else if(number(s,"active_player")!=p)reason="Available on your turn";
                    else if(!s["choice"].is_null()||s["status"]!="actions")reason="Finish the current choice first";
                    else if(!isCamp(id)&&number(e,"damage")>0)reason="Damaged people cannot use abilities";
                    else if(!e["ready"].get<bool>())reason=isCamp(id)?"Already used this turn":"Not ready this turn";
                    else if(player(p)["resonator_lock"].get<bool>())reason="Church Bell Tower prevents further abilities this turn";
                    else if(cost(id,a)<0)reason="No payable cost is available";
                    else if(cid(id)=="pawn_shop"&&a==0&&(cost(id,a)>number(player(p),"water")||handCount(p)<2))
                        reason="Needs "+std::to_string(cost(id,a))+" water and 2 non-Silo hand cards; you have "+std::to_string(number(player(p),"water"))+" water and "+std::to_string(handCount(p))+" eligible card(s). Earlier junk actions do not pay this cost.";
                    else if(cost(id,a)>number(player(p),"water"))reason="Not enough water\nCost: "+std::to_string(cost(id,a))+" water · Available: "+std::to_string(number(player(p),"water"))+"\nNeed "+std::to_string(cost(id,a)-number(player(p),"water"))+" more water";
                    else if(!condition(id,a)) {
                        reason="The requirement in this ability is not met";
                        const std::string key=cid(id);
                        if(key=="army_fort")reason="Army Fort must be undamaged to fire";
                        else if(key=="army_surgeon_s_tent")reason="Needs a damaged person in another column and room here";
                        else if(key=="livery_barn")reason="Requires at most one person on your side";
                        else if(key=="toll_bridge")reason="Requires at least four of your people";
                        else if(key=="breaking_pen")reason="Requires two people in this column";
                        else if(key=="bordello"||key=="barn_raising")reason="Two of your people must enter play this turn";
                        else if(key=="mountain_hideout")reason="An event must resolve this turn";
                        else if(key=="freight_warehouse"||key=="free_homestead")reason="Opponent needs an unprotected camp";
                        else if(key=="vigilance_committee")reason="Requires five cards in your hand";
                        else if(key=="horse_trader")reason="Requires three cards to discard";
                        else if(key=="pawn_shop")reason="Requires two cards to discard";
                        else if(key=="bounty_office")reason="Opponent must have no punks";
                        else if(key=="quaker_settlement")reason=a==0?"This ability requires the village to be undamaged":"This ability requires the village to be damaged";
                    }
                    v["ability_availability"].push_back(J{{"index",a},{"available",reason.empty()},{"reason",reason}});
                }
                v["public_abilities"].push_back(ability);
            }
        }
        return v;
    };
    J out={{"schema_version",1},{"revision",s["revision"]},{"viewer",p},{"status",s["status"]},{"winner",s["winner"]},{"active_player",s["active_player"]},{"turn",s["turn"]},{"ruleset",s["ruleset"]},{"deck_count",s["deck"].size()},{"discard_count",s["discard"].size()},{"reshuffles",s["reshuffles"]},{"players",J::array()},{"choice",nullptr},{"log",J::array()}};
    for(int q=0;q<2;++q) {
        bool setupHidden=s["status"]=="selection"&&q!=p;
        J pl={{"seat",q},{"selected",player(q)["selected"]},{"water",player(q)["water"]},{"hand_count",player(q)["hand"].size()},{"columns",J::array()},{"queue",J::array()},{"silo_in_hand",ent(number(player(q),"silo"))["zone"]=="hand"}};
        for(int c=0;c<3;++c){J col=J::array();if(!setupHidden)for(int id:ints(player(q)["columns"][c]))col.push_back(visible(id,q==p&&trait(p,"wanted_poster_board")));pl["columns"].push_back(col);}
        for(int id:ints(player(q)["queue"]))pl["queue"].push_back(id?visible(id,true):J(nullptr));
        if(q==p) {
            pl["hand"]=J::array();for(int id:ints(player(q)["hand"]))pl["hand"].push_back(visible(id,true));
            if(s["status"]=="selection"){pl["offers"]=J::array();for(const auto& id:player(q)["offers"])pl["offers"].push_back(defs.at(id.get<std::string>()));}
        }
        out["players"].push_back(pl);
    }
    if(!s["choice"].is_null()) {
        out["choice"]={{"player",s["choice"]["player"]},{"prompt",s["choice"]["player"]==p?s["choice"]["prompt"]:J("Waiting for opponent's choice")}};
        if(s["choice"]["player"]==p&&s["choice"].contains("help"))out["choice"]["help"]=s["choice"]["help"];
        if(s["choice"]["player"]==p){out["choice"]["options"]=J::array();for(const auto& o:s["choice"]["options"])out["choice"]["options"].push_back(J{{"id",o["id"]},{"label",o["label"]}});}
    }
    // Current-turn visible actions only: no discard-pile history or private
    // task payloads. Draw events intentionally contain no card identity.
    for(const auto& e:s["log"])if(e["turn"]==s["turn"])out["log"].push_back(e);
    out["history"]=J::array();
    if(s.contains("history"))for(const auto& e:s["history"])
        if(number(e,"turn")>=number(s,"turn")-3&&number(e,"turn")<=number(s,"turn"))out["history"].push_back(e);
    return out;
}

J Engine::Impl::validate() const {
    J errors=J::array();auto require=[&](bool ok,const std::string& why){if(!ok)errors.push_back(why);};
    try {
        require(number(s,"version")==1,"Unsupported save version");
        require(s["players"].is_array()&&s["players"].size()==2,"Expected two players");
        require(number(s,"revision")>=0&&number(s,"turn")>=0,"Invalid revision or turn");
        require(catalog["rulesets"].contains(s["ruleset"].get<std::string>()),"Unknown ruleset");
        const std::set<std::string> statuses={"selection","events","actions","won","draw"};
        require(statuses.count(s["status"].get<std::string>())!=0,"Unknown phase");
        require(number(s,"winner",-1)>=-1&&number(s,"winner",-1)<=1,"Invalid winner");
        require(s["status"]!="won"||number(s,"winner",-1)>=0,"Won state needs winner");
        require(number(s,"reshuffles")>=0&&number(s,"reshuffles")<=1,"Invalid reshuffle count");
        std::map<int,int> counts;
        auto reference=[&](int x,const std::string& zone,int owner){
            ++counts[x];const auto& e=ent(x);require(number(e,"id")==x,"Entity ID mismatch");
            require(e["zone"]==zone,"Entity in wrong zone: "+std::to_string(x));require(number(e,"owner",-9)==owner,"Entity owner mismatch");
        };
        for(int x:ints(s["deck"]))reference(x,"deck",-1);
        for(int x:ints(s["discard"]))reference(x,"discard",-1);
        for(const auto& e:s["cards"])if(e["zone"]=="removed"){int x=number(e,"id");reference(x,"removed",number(e,"owner"));require(isCamp(x)&&e["destroyed"].get<bool>(),"Only ruined camps may be removed");}
        std::set<std::string> offered;
        for(int p=0;p<2;++p){const auto& pl=player(p);
            require(number(pl,"water")>=0,"Negative water");
            require(pl["columns"].size()==3&&pl["queue"].size()==3,"Invalid battlefield dimensions");
            require(pl["offers"].size()==6,"Expected six offered camps");
            for(const auto& offer:pl["offers"]){std::string key=offer;require(defs.at(key)["type"]=="camp","Offer is not camp");require(offered.insert(key).second,"Duplicate offered camp");}
            for(int x:ints(pl["hand"])){reference(x,"hand",p);require(!isCamp(x),"Camp in hand");}
            for(int c=0;c<3;++c){int camps=0;for(int x:ints(pl["columns"][c])){reference(x,"board",p);if(isCamp(x))++camps;else require(def(x)["type"]=="person"||ent(x)["punk"].get<bool>(),"Event faceup on battlefield");}
                require(camps<=1,"Multiple camps in column");require(population(p,c)<=capacity(p,c),"Column over capacity");}
            for(int x:ints(pl["queue"]))if(x){reference(x,"queue",p);require(def(x)["type"]=="event","Non-event queued");}
            for(const auto& pair:std::array<std::pair<const char*,const char*>,2>{{{"silo","hip_flask"},{"stampede","stampede"}}}){
                int x=number(pl,pair.first);require(cid(x)==pair.second,"Wrong special card");require(number(ent(x),"owner",-1)==p,"Special card changed owner");if(ent(x)["zone"]=="special")reference(x,"special",p);}
        }
        int maxId=0;for(auto it=s["cards"].begin();it!=s["cards"].end();++it){const auto& e=it.value();int x=number(e,"id");maxId=std::max(maxId,x);
            require(counts[x]==1,"Card missing or duplicated: "+std::to_string(x));require(defs.count(e["card_id"].get<std::string>())!=0,"Unknown card definition");
            int damageValue=number(e,"damage");require(damageValue>=0&&damageValue<=2,"Invalid damage");
            if(e["zone"]=="board"&&!isCamp(x)){require(damageValue<=1&&!e["destroyed"].get<bool>(),"Destroyed person remains on board");require(!e["punk"].get<bool>()||damageValue==0,"Damaged punk survives");require(damageValue==0||!e["ready"].get<bool>(),"Damaged person ready");}
            if(e["destroyed"].get<bool>())require(isCamp(x)&&damageValue==2&&!e["ready"].get<bool>(),"Invalid ruin");
        }
        require(number(s,"next_id")>maxId,"Entity ID counter overlaps");
        if(s["status"]!="selection")require(number(s,"active_player",-1)>=0&&number(s,"active_player",-1)<2,"Invalid active player");
        if(!s["choice"].is_null()){require(number(s["choice"],"player",-1)>=0&&number(s["choice"],"player",-1)<2,"Invalid choice owner");require(!s["choice"]["options"].empty(),"Empty pending choice");}
        if(finished())require(s["choice"].is_null()&&s["tasks"].empty(),"Finished game still has effects");
        if(!finished()&&s["status"]!="selection")for(int p=0;p<2;++p)require(!board(p,true,false).empty(),"Game continued after final camp destroyed");
    } catch(const std::exception& e){errors.push_back(std::string("Malformed state: ")+e.what());}
    return J{{"ok",errors.empty()},{"errors",errors}};
}

Engine::Engine(const std::string& catalog,std::uint64_t seed,const std::string& options):impl_(std::make_unique<Impl>(catalog,seed,options)) {
    J result=impl_->validate();if(!result["ok"].get<bool>())throw std::runtime_error(result.dump());
}
Engine::~Engine()=default;
Engine::Engine(Engine&&) noexcept=default;
Engine& Engine::operator=(Engine&&) noexcept=default;
std::string Engine::Apply(int p,const std::string& command) {
    J previous=impl_->s; const auto previousCosmetic=impl_->cosmetic;
    try {
        if(command.size()>65536)throw std::runtime_error("Command too large");
        J result=impl_->apply(p,J::parse(command));J validation=impl_->validate();
        if(!validation["ok"].get<bool>())throw std::runtime_error(validation.dump());
        return result.dump();
    } catch(const std::exception& e){impl_->s=previous;impl_->cosmetic=previousCosmetic;return J{{"ok",false},{"error",e.what()},{"revision",impl_->s["revision"]}}.dump();}
}
std::string Engine::ViewJson(int p)const{return impl_->view(p).dump();}
std::string Engine::LegalActionsJson(int p)const{return impl_->legal(p).dump();}
std::string Engine::CatalogJson()const{return impl_->catalog.dump();}
std::string Engine::SaveJson()const{return impl_->s.dump();}
std::string Engine::CosmeticSaveJson() const {
    J result=J::object();for(const auto& [id,visual]:impl_->cosmetic)result[std::to_string(id)]=visual;
    return result.dump();
}
bool Engine::RestoreCosmeticJson(const std::string& text) {
    try {
        const J value=J::parse(text);if(!value.is_object())return false;
        std::map<int,std::string> restored;std::set<std::string> seen;
        for(auto it=value.begin();it!=value.end();++it) {
            const int id=std::stoi(it.key());const auto visual=it.value().get<std::string>();
            if(std::to_string(id)!=it.key())return false;
            if(!impl_->s["cards"].contains(std::to_string(id)) || !seen.insert(visual).second)return false;
            const auto canonical=impl_->cid(id);
            if(!OldWestCrew::Resolve(canonical,visual))return false;
            restored[id]=visual;
        }
        // Upgrade the previously supported two-entry Native sidecar without
        // changing saved rule state or losing those physical-copy identities.
        if(restored.size()==2 && seen.count("lozen") && seen.count("sarah-winnemucca")) {
            for(const auto& [id,unused]:impl_->cosmetic) {
                if(restored.count(id))continue;
                for(const auto& entry:OldWestCrew::Entries)
                    if(impl_->cid(id)==entry.Canonical && !seen.count(entry.Visual)) {
                        restored[id]=entry.Visual;seen.insert(entry.Visual);break;
                    }
            }
        }
        if(restored.size()!=impl_->cosmetic.size())return false;
        impl_->cosmetic=std::move(restored);return true;
    } catch(...) {return false;}
}
std::string Engine::CosmeticViewJson(int player) const {
    const J view=impl_->view(player);J result=J::object();
    auto add=[&](const J& card) {
        if(!card.is_object()||card.value("punk",false)||!card.contains("card_id"))return;
        const int id=number(card,"id");const auto found=impl_->cosmetic.find(id);
        if(found!=impl_->cosmetic.end())result[std::to_string(id)]=found->second;
    };
    for(const auto& pl:view["players"]) {
        for(const auto& c:pl.value("hand",J::array()))add(c);
        for(const auto& col:pl["columns"])for(const auto& c:col)add(c);
    }
    return result.dump();
}
bool Engine::RestoreJson(const std::string& saved,std::string* error) {
    J old=impl_->s;
    try{impl_->s=J::parse(saved);J valid=impl_->validate();if(!valid["ok"].get<bool>())throw std::runtime_error(valid.dump());impl_->rebuildCosmetics();return true;}
    catch(const std::exception& e){impl_->s=old;if(error)*error=e.what();return false;}
}
std::string Engine::ValidateJson()const{return impl_->validate().dump();}
bool Engine::Forfeit(int player) {
    if(player<0||player>1||impl_->finished())return false;
    impl_->s["revision"]=number(impl_->s,"revision")+1;
    impl_->win(1-player,"Opponent forfeited the game");
    return true;
}
bool Engine::IsFinished()const{return impl_->finished();}
int Engine::Winner()const{return number(impl_->s,"winner",-1);}
} // namespace oldwest
