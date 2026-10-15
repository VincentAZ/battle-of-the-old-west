#include "OldWestAI.h"
#include "json.hpp"
#include <algorithm>
#include <array>
#include <cmath>
#include <limits>
#include <map>
#include <set>
#include <utility>
#include <vector>

namespace oldwest {
using J = nlohmann::ordered_json;
namespace {
int num(const J& j, const char* key, int fallback=0) {
    return j.contains(key) && j[key].is_number_integer() ? j[key].get<int>() : fallback;
}
bool has(const std::string& text, const std::string& needle) { return text.find(needle)!=std::string::npos; }
std::string lower(std::string text) { for(char& c:text) if(c>='A'&&c<='Z') c=char(c-'A'+'a'); return text; }
int after(const std::string& text, const std::string& marker) {
    const auto at=text.find(marker); if(at==std::string::npos)return -1;
    auto index=at+marker.size(); int value=0; bool read=false;
    while(index<text.size()&&text[index]>='0'&&text[index]<='9'){read=true;value=value*10+(text[index++]-'0');}
    return read?value-1:-1;
}
struct Card {
    int id=0, owner=0, column=-1, position=-1, damage=0, uses=0, advance=0;
    bool camp=false, punk=false, ready=false, protectedCard=false, destroyed=false;
    std::string key, name, zone;
};
struct Position {
    int me=0, turn=0, water=0, deck=0, reshuffles=0;
    std::vector<Card> cards;
    std::array<int,2> camps{}, people{}, damaged{}, handCount{};
    std::array<std::array<int,3>,2> population{};
    std::array<std::array<std::string,3>,2> queues{};
    const Card* find(int id) const {for(const auto& c:cards)if(c.id==id)return &c;return nullptr;}
};
}
struct AIPlayer::Impl {
    std::map<std::string,J> defs;
    AIDifficulty difficulty;
    std::uint64_t rng;
    std::string lastView,lastLegal,lastAnswer;
    int turn=-1, actionsThisTurn=0;
    bool storedThisTurn=false, withdrewThisTurn=false;
    explicit Impl(const std::string& catalog,AIDifficulty level,std::uint64_t seed):difficulty(level),rng(seed?seed:1) {
        const J parsed=J::parse(catalog);
        for(const auto& d:parsed.at("cards"))defs[d.at("id").get<std::string>()]=d;
    }
    std::uint64_t random(){std::uint64_t x=rng;x^=x>>12;x^=x<<25;x^=x>>27;rng=x;return x*2685821657736338717ULL;}
    const J& definition(const std::string& key) const {static const J empty=J::object();auto it=defs.find(key);return it==defs.end()?empty:it->second;}
    Position position(const J& view) const {
        Position p;p.me=view.at("viewer");p.turn=num(view,"turn");p.deck=num(view,"deck_count");p.reshuffles=num(view,"reshuffles");
        for(int side=0;side<2;++side){const auto& player=view.at("players").at(side);p.handCount[side]=num(player,"hand_count");if(side==p.me)p.water=num(player,"water");
            auto add=[&](const J& j,int lane,int index){Card c;c.id=num(j,"id");c.owner=side;c.column=lane;c.position=index;c.damage=num(j,"damage");c.uses=num(j,"uses");c.advance=num(j,"advance");
                c.key=j.value("card_id",std::string());c.name=j.value("name",std::string());c.zone=j.value("zone",std::string());c.punk=j.value("punk",false);c.camp=j.value("type",std::string())=="camp";c.ready=j.value("ready",false);c.protectedCard=j.value("protected",false);c.destroyed=j.value("destroyed",false);
                // Authorized Wanted Poster Board inspection is part of this player's own view.
                if(c.punk&&side==p.me&&j.contains("private_peek"))c.key=j["private_peek"].value("card_id",std::string());
                p.cards.push_back(c);if(lane>=0&&!c.destroyed){if(c.camp)++p.camps[side];else{++p.people[side];++p.population[side][lane];}if(c.damage)++p.damaged[side];}};
            for(int lane=0;lane<3;++lane){int index=0;for(const auto& c:player.at("columns").at(lane))add(c,lane,index++);const auto& q=player.at("queue").at(lane);if(!q.is_null())p.queues[side][lane]=q.value("card_id",std::string());}
            // Never inspect an opponent hand even if the caller accidentally supplied one.
            if(side==p.me&&player.contains("hand"))for(const auto& c:player["hand"])add(c,-1,-1);
        }return p;
    }
    bool trait(const Position& p,int side,const std::string& key) const {for(const auto& c:p.cards)if(c.owner==side&&c.column>=0&&!c.destroyed&&!c.punk&&c.key==key&&(c.camp||c.damage==0))return true;return false;}
    double personValue(const Card& c) const {
        if(c.punk)return 7;
        const auto& d=definition(c.key);double value=11+num(d,"play_cost")*2.5;
        static const std::map<std::string,double> bonuses={{"cornelius_ashby_railroad_baron",22},{"quanah_parker",11},{"charles_goodnight",15},{"wyatt_earp",10},{"bartender",7},{"annie_oakley",7},{"augustus_powder_pike",7},{"con_man",6},{"ringleader",3},{"sarah_winnemucca",-3},{"civil_war_veteran",-2}};
        auto it=bonuses.find(c.key);if(it!=bonuses.end())value+=it->second;
        return c.damage?value*.46:value;
    }
    double hit(const Position& p,const Card& c,bool destroy=false) const {
        if(c.destroyed||c.column<0)return 0;
        if(c.camp){const bool lethal=destroy||c.damage>0;if(lethal)return p.camps[c.owner]==1?10000:80+(3-p.camps[c.owner])*18;return 29+(3-p.camps[c.owner])*9;}
        double v=personValue(c);if(destroy||c.damage||c.punk)return v+5;
        return v*.60+(c.ready?4:0);
    }
    double bestHit(const Position& p,bool destroy=false,bool any=false,int kind=0,int owner=-1) const {
        if(owner<0)owner=1-p.me;
        double best=0;
        for(const auto& c:p.cards)if(c.owner==owner&&c.column>=0&&!c.destroyed&&(any||!c.protectedCard)&&(!kind||(kind==1&&!c.camp)||(kind==2&&c.camp)))best=std::max(best,hit(p,c,destroy));
        return best;
    }
    double leastLoss(const Position& p,bool destroy=false,int kind=0) const {
        double best=1e6;for(const auto& c:p.cards)if(c.owner==p.me&&c.column>=0&&!c.destroyed&&(!kind||(kind==1&&!c.camp)||(kind==2&&c.camp)))best=std::min(best,hit(p,c,destroy));return best==1e6?0:best;
    }
    double restoreValue(const Position& p,int except=0,bool peopleOnly=false) const {
        double value=0;for(const auto& c:p.cards)if(c.owner==p.me&&c.column>=0&&!c.destroyed&&c.damage&&c.id!=except&&c.key!="logging_camp"&&(!peopleOnly||!c.camp))value=std::max(value,c.camp?35+(3-p.camps[p.me])*18:personValue(c)*1.25+6);return value;
    }
    double placement(const Position& p,int lane,int index,double value=7,int replace=0) const {
        if(lane<0||lane>2)return 0;
        double score=0;const Card* camp=nullptr;
        for(const auto& c:p.cards)if(c.owner==p.me&&c.column==lane&&c.camp&&!c.destroyed)camp=&c;
        const int count=p.population[p.me][lane];
        if(camp){score+=(count==0?15:count==1?4:0)+(camp->damage&&count==0?12:0);if(p.camps[p.me]==1&&count<2)score+=13;}
        // Cheap bodies shield engines, while valuable people belong behind a guard.
        if(index==0){score+=std::max(-8.0,8-value*.35);for(const auto& c:p.cards)if(c.owner==p.me&&c.column==lane&&c.position==0&&!c.camp)score+=personValue(c)*.15;}
        else score+=std::min(9.0,value*.24);
        if(replace){const Card* old=p.find(replace);if(old)score-=personValue(*old)+5;}
        return score;
    }
    double punkValue(const Position& p) const {
        double best=-8;for(int lane=0;lane<3;++lane)if(p.population[p.me][lane]<2)best=std::max(best,7+placement(p,lane,0));return best;
    }
    double raidValue(const Position& p,int delay=2) const {
        for(int i=0;i<3;++i)if(p.queues[p.me][i]=="stampede"){
            if(i>0&&!p.queues[p.me][i-1].empty())return 0;
            if(i==0){double least=1e6;for(const auto& c:p.cards)if(c.owner!=p.me&&c.camp&&!c.destroyed)least=std::min(least,hit(p,c));return least==1e6?0:least;}
            return i==1?23:15;
        }
        for(int i=delay-1;i<3;++i)if(p.queues[p.me][i].empty())return trait(p,p.me,"poker_alice")?31:19-(i*3);
        return 0;
    }
    double drawValue(const Position& p) const {if(p.deck<=1){if(trait(p,p.me,"land_office"))return 10000;if(trait(p,1-p.me,"land_office"))return -10000;}return p.handCount[p.me]<3?14:p.handCount[p.me]<7?10:5;}
    double waterValue(const Position& p) const {
        double best=0;for(const auto& c:p.cards)if(c.owner==p.me&&!c.destroyed){const auto& d=definition(c.key);
            if(c.zone=="hand"&&num(d,"play_cost")==p.water+1&&c.key!="hip_flask")best=std::max(best,12.0);
            if(c.column>=0&&c.ready&&(!c.damage||c.camp)&&d.contains("abilities"))for(const auto& a:d["abilities"])if(num(a,"cost")==p.water+1)best=std::max(best,15.0);
        }
        return best+(p.water<2?3:0);
    }
    double junkValue(const Position& p,const std::string& effect) const {
        if(effect=="injure")return bestHit(p,false,false,1);
        if(effect=="restore")return restoreValue(p);
        if(effect=="punk")return punkValue(p);
        if(effect=="raid")return raidValue(p);
        if(effect=="draw")return drawValue(p);
        if(effect=="water")return waterValue(p);
        return 0;
    }
    double laneHit(const Position& p,int lane,bool destroyPeople=false,bool camps=true) const {
        double score=0;for(const auto& c:p.cards)if(c.owner!=p.me&&c.column==lane&&!c.destroyed&&(!c.camp||camps))score+=hit(p,c,destroyPeople&&!c.camp);return score;
    }
    double ability(const Position& p,const Card& source,int index,int depth=0) const {
        const std::string& k=source.key;if(index>=100)return bestHit(p);
        if(k=="con_man") {if(depth>0)return 0;double best=0;for(const auto& c:p.cards)if(c.column>=0&&!c.camp&&!c.punk&&!c.damage&&c.id!=source.id&&(c.owner!=p.me||c.ready)){const auto& d=definition(c.key);if(d.contains("abilities"))for(int i=0;i<int(d["abilities"].size());++i)if(num(d["abilities"][i],"cost")<=p.water)best=std::max(best,ability(p,c,i,depth+1)-num(d["abilities"][i],"cost")*5);}return best;}
        if(k=="cornelius_ashby_railroad_baron"||k=="timber_ram")return bestHit(p,true,true,2);
        if(k=="annie_oakley")return bestHit(p,false,true);
        if(k=="bounty_hunter"||k=="gallows")return bestHit(p,true,false,1)*(k=="gallows"?.85:1);
        if(k=="barn_burner"||k=="toll_bridge"||k=="bounty_office")return bestHit(p,false,k!="barn_burner",2)-(k=="bounty_office"?8:0);
        if(k=="hellfire_preacher"||k=="revival_tent"||k=="dynamite_shack")return bestHit(p,false,k=="dynamite_shack")-leastLoss(p,true,1);
        if(k=="bartender"||k=="silver_mine")return waterValue(p)+6-(k=="silver_mine"?leastLoss(p,true,1):0);
        if(k=="doc_holliday")return bestHit(p)+restoreValue(p,source.id)-hit(p,source);
        if(k=="duelist"||k=="dance_hall"){const double attackValue=bestHit(p);return attackValue>=10000?attackValue:attackValue-bestHit(p,false,false,k=="dance_hall"?1:0,p.me);}
        if(k=="charles_goodnight"||k=="vigilante")return bestHit(p,false,false,1);
        if(k=="regulator"||k=="gatling_gunner"){double v=0;for(const auto& c:p.cards)if(c.owner!=p.me&&c.column>=0&&!c.camp&&!c.destroyed&&(k=="regulator"?c.damage>0:!c.protectedCard))v+=hit(p,c,k=="regulator");return v;}
        if(k=="augustus_powder_pike"||k=="rockslide_ridge"){double v=0;for(int lane=0;lane<3;++lane)v=std::max(v,laneHit(p,lane,k=="rockslide_ridge"));return v>=10000?v:v-(k=="rockslide_ridge"?hit(p,source,true):0);}
        if(k=="ringleader"&&index==0)return punkValue(p);
        if(k=="blacksmith"||k=="freight_warehouse"||k=="boot_hill"||k=="barn_raising"||(k=="stagecoach_station"&&index==1)||(k=="jailhouse"&&index==1)||(k=="quaker_settlement"&&index==0))return restoreValue(p,source.id);
        if(k=="hot_springs"||k=="crimp_house"||(k=="army_surgeon_s_tent"&&index==0))return restoreValue(p,source.id,true)+(k=="hot_springs"?5:0);
        if(k=="logging_camp"){double v=-hit(p,source);for(const auto& c:p.cards)if(c.owner==p.me&&c.damage&&c.column>=0&&!c.destroyed&&c.id!=source.id)v+=c.camp?40:personValue(c)+6;return v;}
        if(k=="sarah_winnemucca"||k=="pony_express_station"){double v=-10;for(const auto& c:p.cards)if(c.owner==p.me&&c.column>=0&&!c.camp&&!c.destroyed)v=std::max(v,c.damage?10.0:c.punk?-5.0:-personValue(c)*.4);return v;}
        if(k=="prospector"||k=="apothecary")return (p.deck<=3&&trait(p,1-p.me,"land_office"))?0:12+(k=="prospector"?4:0);
        if(k=="rustler"||k=="cattle_ranch"||k=="courthouse"||k=="coal_yard"||k=="cattlemen_s_club"||(k=="roundup_corral"&&index==1)||(k=="stagecoach_station"&&index==0)||(k=="rodeo_grounds"&&index==1)||(k=="army_surgeon_s_tent"&&index==1)||(k=="boarding_house"&&index==1))return raidValue(p,k=="coal_yard"?3:2);
        if(k=="rodeo_grounds")return bestHit(p,false,false,1);
        if(k=="livery_barn"||k=="gunsmith"||k=="free_homestead"||k=="wanted_poster_board")return punkValue(p);
        if(k=="wagon_fort")return punkValue(p)*std::min(3,6-p.people[p.me]);
        if(k=="stockyards")return raidValue(p)+punkValue(p);
        if(k=="railroad_work_camp")return restoreValue(p,source.id)-leastLoss(p,true,1);
        if(k=="undertaker")return drawValue(p)-leastLoss(p,true,1);
        if(k=="salvage_yard")return std::max(punkValue(p),waterValue(p))-7;
        if(k=="bare_knuckle_ring")return bestHit(p,true,true,1)*.65-leastLoss(p,true,1);
        if(k=="artillery_battery")return bestHit(p)*.6;
        if(k=="riverboat"){if(source.advance==2){double loss=1e6;for(const auto& c:p.cards)if(c.owner!=p.me&&c.camp&&!c.destroyed)loss=std::min(loss,hit(p,c,true));return loss==1e6?0:loss;}return 18+source.advance*9;}
        if(k=="powder_magazine"){double v=-hit(p,source,true);for(const auto& c:p.cards)if(c.column>=0&&!c.camp&&!c.destroyed)v+=(c.owner==p.me?-1:1)*hit(p,c,true);return v;}
        if(k=="nitro_works"){double v=bestHit(p);for(const auto& c:p.cards)if(c.owner==p.me&&c.column==source.column&&!c.camp)v-=hit(p,c,true);return v;}
        if(k=="vigilance_committee")return bestHit(p,true,true)-40;
        if(k=="pawn_shop")return bestHit(p)+9-14;
        if(k=="packer_s_cabin")return restoreValue(p,source.id)-leastLoss(p);
        if(k=="rustlers_corral")return std::max(punkValue(p),raidValue(p));
        if(k=="post_office")return drawValue(p)*2;
        if(k=="general_store")return drawValue(p)+4;
        if(k=="poker_alice")return p.handCount[p.me]>4?3:8;
        if(k=="horse_trader")return p.handCount[p.me]>5?8:-3;
        if(k=="chuckwagon"){double v=0;for(const auto& c:p.cards)if(c.owner==p.me&&c.column>=0&&!c.destroyed&&!c.ready&&(!c.damage||c.camp)&&c.id!=source.id)v+=7;return v;}
        if(k=="jailhouse")return bestHit(p,true,true,1)*.8+placement(p,0,1);
        if(k=="telegraph_office"){double v=0;for(int slot=0;slot<3;++slot)if(!p.queues[p.me][slot].empty()&&(slot==0||p.queues[p.me][slot-1].empty()))v=std::max(v,slot==0?25.0:16.0);return v;}
        if(k=="lookout_ridge")return std::max(0.0,bestHit(p,false,true)-bestHit(p))*.7;
        if(k=="roundup_corral")return 8;
        if(k=="smuggler_s_landing")return 15;
        if(k=="saloon")return p.damaged[p.me]>0?18:0;
        if(k=="railroad_depot")return p.handCount[p.me]>0?15:0;
        return bestHit(p); // Remaining catalog abilities are ordinary damage.
    }
    double eventValue(const Position& p,const Card& c) const {
        const auto& k=c.key;double v=0;
        if(k=="run_out_of_town")v=bestHit(p,true,true,1);
        else if(k=="cannonade"){for(const auto& x:p.cards)if(x.owner!=p.me&&x.camp&&!x.destroyed)v+=hit(p,x);}
        else if(k=="prairie_fire"){for(int lane=0;lane<3;++lane)v=std::max(v,laneHit(p,lane,true,false));}
        else if(k=="gold_rush")v=punkValue(p)*std::min(3,6-p.people[p.me]);
        else if(k=="poker_night")v=drawValue(p)+7;
        else if(k=="ambush"||k=="cholera"){for(const auto& x:p.cards)if(x.column>=0&&!x.camp&&!x.destroyed&&(k=="cholera"||(x.owner!=p.me&&!x.protectedCard)))v+=(x.owner==p.me?-1:1)*hit(p,x);}
        else if(k=="hard_winter"){double own=0,enemy=0,ownBest=0,enemyBest=0;for(const auto& x:p.cards)if(x.column>=0&&!x.camp&&!x.destroyed){double val=personValue(x);if(x.owner==p.me){own+=val;ownBest=std::max(ownBest,val);}else{enemy+=val;enemyBest=std::max(enemyBest,val);}}v=enemy-enemyBest-own+ownBest;}
        else if(k=="curfew")v=(p.people[1-p.me]-p.people[p.me])*11+p.damaged[p.me]*5;
        else if(k=="box_canyon")v=std::max(0.0,bestHit(p,false,true)-bestHit(p))*.8;
        int delay=num(definition(k),"event_delay");if(trait(p,p.me,"poker_alice"))delay=0;
        return v/(1+delay*.18);
    }
    double campDraft(const J& command) const {
        double score=0;int cards=0,damage=0,punks=0,raid=0,restore=0;std::set<std::string> chosen;
        static const std::map<std::string,double> adjustments={{"cattle_ranch",12},{"gatling_emplacement",7},{"church_bell_tower",8},{"general_store",4},{"trading_post",8},{"army_fort",-9},{"powder_magazine",-9},{"rockslide_ridge",-7},{"vigilance_committee",-8},{"timber_ram",-8},{"toll_bridge",-5},{"chuckwagon",8},{"coal_yard",-4},{"breaking_pen",-3},{"artillery_battery",2}};
        for(const auto& id:command.at("camps")){std::string k=id;chosen.insert(k);const auto& d=definition(k);cards+=num(d,"starting_cards");auto adjustment=adjustments.find(k);if(adjustment!=adjustments.end())score+=adjustment->second;
            std::string text=lower(d.value("trait",std::string()));if(d.contains("abilities"))for(const auto& a:d["abilities"]){std::string effect=lower(a.value("effect",std::string()));text+=" "+effect;score+=std::max(0,3-num(a,"cost"))*1.5;}
            damage+=has(text,"damage")||has(text,"destroy any enemy camp");punks+=has(text,"gain a punk")||has(text,"gain up to three punks");raid+=has(text,"raid");restore+=has(text,"restore");
        }
        score+=cards*9+std::min(damage,1)*10+std::min(raid,1)*6+std::min(restore,1)*3;
        if(cards<2)score-=15;
        if(damage+raid==0)score-=18;
        if(difficulty==AIDifficulty::Hard){
            if(chosen.count("bunkhouse"))score+=punks*9;
            if(chosen.count("gunsmith"))score+=punks*5;
            if(chosen.count("robbers_roost"))score+=raid*7;
            if(chosen.count("cattlemen_s_club"))score+=raid*3;
            if(chosen.count("army_fort"))score+=restore*8;
            if(chosen.count("silver_mine")||chosen.count("revival_tent")||chosen.count("bare_knuckle_ring"))score+=punks*6;
            if(chosen.count("chuckwagon"))score+=damage*6;
            if(chosen.count("church_bell_tower")&&chosen.count("chuckwagon"))score-=15;
        }
        return score;
    }
    struct Attack {bool valid=false,destroy=false,any=false;int kind=0;};
    Attack attack(const Position& p,const J& action) const {
        const auto& cmd=action.at("command");const std::string type=cmd.value("type",std::string());
        if(type=="junk"){const Card* c=p.find(num(cmd,"card"));if(c){const auto& d=definition(c->key);if(d.contains("junk")&&d["junk"].is_string()&&d["junk"]=="injure")return {true,false,false,1};}return {};}
        if(type!="activate")return {};
        const Card* c=p.find(num(cmd,"source"));if(!c)return {};
        const std::string& k=c->key;int index=num(cmd,"ability");
        if(index>=100)return {true,false,false,0};
        if(k=="cornelius_ashby_railroad_baron"||k=="timber_ram")return {true,true,true,2};
        if(k=="annie_oakley")return {true,false,true,0};
        if(k=="bounty_hunter")return {true,true,false,1};
        if(k=="charles_goodnight"||k=="vigilante"||(k=="rodeo_grounds"&&index==0))return {true,false,false,1};
        if(k=="barn_burner")return {true,false,false,2};
        if(k=="toll_bridge")return {true,false,true,2};
        static const std::set<std::string> ordinary={"wyatt_earp","pinkerton_agent","widow_with_a_shotgun","quanah_parker","civil_war_veteran","gatling_emplacement","army_fort","bunkhouse","command_post_legacy","bordello","homestead_cabin","breaking_pen","mountain_hideout","church_bell_tower","claim_jumper"};
        if(ordinary.count(k)||(k=="ringleader"&&index==1)||(k=="quaker_settlement"&&index==1))return {true,false,false,0};
        return {};
    }
    static bool hittable(const Position& p,const Card& c,const Attack& a) {return c.owner!=p.me&&c.column>=0&&!c.destroyed&&(a.any||!c.protectedCard)&&(!a.kind||(a.kind==1&&!c.camp)||(a.kind==2&&c.camp));}
    void projectedHit(Position& p,int target,const Attack& a) const {
        for(auto& c:p.cards)if(c.id==target){if(a.destroy||c.damage||c.punk){c.destroyed=true;if(c.camp)--p.camps[c.owner];else --p.people[c.owner];}else{c.damage=1;if(!c.camp)c.ready=false;}break;}
        // Removing a front defender exposes the next surviving card. An already
        // exposed formation stays exposed (Box Canyon / Lookout Ridge).
        for(int side=0;side<2;++side)for(int lane=0;lane<3;++lane){bool first=true;for(auto& c:p.cards)if(c.owner==side&&c.column==lane&&!c.destroyed){if(first)c.protectedCard=false;first=false;}}
    }
    double nextAttack(const Position& p,const J& actions,int spentSource=0,bool sourceStillReady=false) const {
        double best=0;for(const auto& action:actions){const auto& cmd=action.at("command");if(cmd.value("type",std::string())!="activate"||num(action,"cost")>p.water)continue;
            if(num(cmd,"source")==spentSource&&!sourceStillReady)continue;
            const Card* source=p.find(num(cmd,"source"));if(!source||source->destroyed||(source->damage&&!source->camp))continue;
            const Attack a=attack(p,action);if(!a.valid)continue;for(const auto& target:p.cards)if(hittable(p,target,a))best=std::max(best,hit(p,target,a.destroy)-num(action,"cost")*5);
        }return best;
    }
    double tacticalPair(const Position& p,const J& first,const J& actions) const {
        const Attack a=attack(p,first);if(!a.valid)return 0;double best=0;
        const int sourceId=num(first.at("command"),"source");const Card* source=p.find(sourceId);
        const bool reusable=source&&source->uses==0&&trait(p,p.me,"charles_goodnight")&&source->key!="church_bell_tower";
        if(source&&source->key=="church_bell_tower")return 0;
        for(const auto& target:p.cards)if(hittable(p,target,a)){
            Position future=p;future.water-=num(first,"cost");projectedHit(future,target.id,a);
            double continuation=nextAttack(future,actions,sourceId,reusable);
            // This bounded two-attack projection uses visible targets only. It
            // does not guess draws or replace authoritative legality checks.
            best=std::max(best,hit(p,target,a.destroy)+continuation*.80);
        }
        double immediate=0;for(const auto& target:p.cards)if(hittable(p,target,a))immediate=std::max(immediate,hit(p,target,a.destroy));
        return std::max(0.0,best-immediate);
    }
    std::vector<const Card*> named(const Position& p,const std::string& label,int owner=-1) const {
        std::vector<const Card*> out;int lane=after(label,"lane ");
        for(const auto& c:p.cards)if((owner<0||c.owner==owner)&&!c.destroyed&&has(label,c.name)&&!c.name.empty()&&(lane<0||c.column==lane))out.push_back(&c);
        return out;
    }
    std::string lastEffectSource(const Position& p,const J& view) const {
        if(!view.contains("log"))return {};
        for(auto it=view["log"].rbegin();it!=view["log"].rend();++it){const auto type=it->value("type",std::string());if(type=="event_resolve"&&it->value("detail",std::string())=="Stampede")return "stampede";
            if(type=="ability"||type=="event_resolve"||type=="camp_advance"){const Card* card=p.find(num(*it,"target",num(*it,"source")));if(!card)card=p.find(num(*it,"source"));if(card)return card->key;}}
        return {};
    }
    double choiceScore(const Position& p,const J& view,const J& action,const J& actions) const {
        const std::string label=action.value("label",std::string()),text=lower(label),prompt=lower(view.at("choice").value("prompt",std::string()));
        if(text=="skip")return 0;
        int lane=after(text,"lane "),index=after(text,"position ");
        if(has(prompt,"place a punk")){double score=7+placement(p,lane,index);if(has(text,"replace ")){for(const auto& c:p.cards)if(c.owner==p.me&&c.column==lane&&has(label,"replace "+c.name))score-=personValue(c)+5;}return score;}
        if(has(prompt,"choose an enemy lane")||has(prompt,"rockslide ridge's target lane")){std::string source=lastEffectSource(p,view);return laneHit(p,lane,source=="prairie_fire"||source=="rockslide_ridge",source!="prairie_fire");}
        if(has(prompt,"event to advance"))return (has(text,"your ")?1:-1)*(has(text,"at 1")?30:16);
        if(has(prompt,"junk effect")||has(prompt,"junk effects")||has(prompt,"discarded junk")){auto colon=text.rfind(": ");if(colon!=std::string::npos)return junkValue(p,text.substr(colon+2));}
        if(has(prompt,"resource")||has(prompt,"punk or a raid")){if(has(text,"punk"))return punkValue(p);if(has(text,"water"))return waterValue(p);if(has(text,"raid"))return raidValue(p);}
        if(has(prompt,"discard ")){double score=-100;for(const auto& c:p.cards)if(c.owner==p.me&&c.zone=="hand"&&label=="Discard "+c.name)score=std::max(score,-personValue(c)*.5);return score;}
        if(has(prompt,"choose the one person you keep")){double score=0;for(const Card* c:named(p,label,p.me))score=std::max(score,personValue(*c)+(c->protectedCard?3:0));return score;}
        if(has(prompt,"ability")||has(prompt,"activate a damaged person")){
            double score=-20;
            for(const auto& c:p.cards)if(has(label,c.name+": ")&&!c.name.empty()){const auto& d=definition(c.key);if(d.contains("abilities"))for(int a=0;a<int(d["abilities"].size());++a)if(has(label,d["abilities"][a].value("effect",std::string("~~~"))))score=std::max(score,ability(p,c,a)-num(d["abilities"][a],"cost")*5-(has(prompt,"then destroy")?hit(p,c,true):0));}
            if(score==-20&&has(text,"damage"))return bestHit(p);
            return score;
        }
        if(has(prompt,"immediate activation")){double score=-10;for(const auto& c:p.cards)if(c.owner==p.me&&c.zone=="hand"&&has(label,"Deploy "+c.name+" in"))score=std::max(score,personValue(c)+placement(p,lane,index,personValue(c))-num(definition(c.key),"play_cost")*5);return score;}
        if(has(prompt,"recruit")||has(prompt,"move and restore")){double score=0;for(const auto& c:p.cards)if(c.column>=0&&has(label,c.name+" to "))score=std::max(score,personValue(c)+placement(p,lane,index,personValue(c)));return score;}
        if(has(prompt,"rearrange")||has(prompt,"person and destination")){
            if(text=="rearrange")return -1;
            double score=0;for(const auto& c:p.cards)if(c.column>=0&&!c.camp&&has(label,c.name+" to "))score=std::max(score,(c.owner==p.me?1:-1)*placement(p,lane,index,personValue(c)));return score;
        }
        if(has(prompt,"remove a ruined camp")){double score=-5;for(const auto& c:p.cards)if(c.camp&&c.destroyed&&has(label,c.name)&&c.column==lane)score=c.owner==p.me?8:-8;return score;}
        if(has(prompt,"restore")||has(prompt,"crimp_house")){double score=-2;for(const Card* c:named(p,label,p.me))if(c->damage)score=std::max(score,c->camp?35+(3-p.camps[p.me])*18:personValue(*c)*1.25+6);return score;}
        if(has(prompt,"sacrifice")||has(prompt,"your undamaged card")){double score=-1e6;for(const Card* c:named(p,label,p.me))score=std::max(score,-hit(p,*c,has(prompt,"sacrifice")));return score;}
        if(has(prompt,"return a person")||has(prompt,"recover a person")){double score=-100;for(const Card* c:named(p,label,p.me))score=std::max(score,c->damage?12.0:c->punk?-8.0:-personValue(*c)*.4);return score;}
        if(has(prompt,"damage target")||has(prompt,"card to destroy")){
            const std::string source=lastEffectSource(p,view);int owner=source=="stampede"||source=="artillery_battery"||source=="riverboat"?p.me:1-p.me;
            auto targets=named(p,label,owner);if(targets.empty()){owner=1-owner;targets=named(p,label,owner);}
            double score=-1e6;const bool destroy=has(prompt,"destroy");
            for(const Card* c:targets){double value=hit(p,*c,destroy);if(owner==p.me)value=-value;
                else if(difficulty==AIDifficulty::Hard){Position future=p;projectedHit(future,c->id,{true,destroy,true,0});
                    // During a choice only choice actions are supplied, so use
                    // visible ready abilities to value opening the next target.
                    J follow=J::array();for(const auto& own:p.cards)if(own.owner==p.me&&own.ready&&own.column>=0&&!own.destroyed&&(!own.damage||own.camp)&&!own.punk){const auto& d=definition(own.key);if(d.contains("abilities"))for(int a=0;a<int(d["abilities"].size());++a)follow.push_back(J{{"cost",num(d["abilities"][a],"cost")},{"command",{{"type","activate"},{"source",own.id},{"ability",a}}}});}
                    value+=nextAttack(future,follow)*.6;}
                score=std::max(score,value);
            }return score;
        }
        // Any new legal choice remains selectable, rather than stalling a match.
        (void)actions;return 1;
    }
    double actionScore(const Position& p,const J& view,const J& a,const J& actions) const {
        const auto& cmd=a.at("command");const std::string type=cmd.at("type");int cost=num(a,"cost");double score=0;
        if(type=="select_camps")return campDraft(cmd);
        if(type=="choose")return choiceScore(p,view,a,actions);
        if(type=="end_turn")return 0;
        if(type=="draw")return drawValue(p)-cost*5;
        if(type=="silo")return storedThisTurn||withdrewThisTurn?-50:3;
        const Card* card=p.find(num(cmd,"card",num(cmd,"source")));if(!card)return -100;
        if(type=="activate")score=ability(p,*card,num(cmd,"ability"))-cost*5;
        else if(type=="junk"){
            const auto& d=definition(card->key);std::string effect=d.value("junk",J("" )).is_string()?d.value("junk",std::string()):d.at("junk").value("effect",std::string());
            if(card->key=="hip_flask")return storedThisTurn||withdrewThisTurn?-50:waterValue(p)-3;
            double retain=card->zone=="hand"?(definition(card->key).value("type",std::string())=="event"?std::max(5.0,eventValue(p,*card)*.35):personValue(*card)*.45):8;
            if(p.handCount[p.me]>=8)retain*=.65;
            score=junkValue(p,effect)-retain;
        }else if(type=="play"||type=="flip"){
            if(definition(card->key).value("type",std::string())=="event")score=eventValue(p,*card)-cost*5-3;
            else{score=personValue(*card)*.65+placement(p,num(cmd,"column",card->column),num(cmd,"position",card->position),personValue(*card),num(cmd,"replace"))-cost*5;
                if(card->key=="wyatt_earp"||card->key=="duelist")score+=punkValue(p)*.7;
                if(card->key=="blacksmith")score+=restoreValue(p)*.7;
                if(card->key=="civil_war_veteran")score+=drawValue(p)-7;
                if(card->key=="quanah_parker"||trait(p,p.me,"quanah_parker")||type=="flip")score+=4;
            }
        }
        if(difficulty==AIDifficulty::Hard)score+=tacticalPair(p,a,actions);
        return score;
    }
    std::string choose(const std::string& viewJson,const std::string& legalJson){
        if(viewJson==lastView&&legalJson==lastLegal)return lastAnswer;
        J view=J::parse(viewJson),actions=J::parse(legalJson);
        if(!view.is_object()||!actions.is_array()||actions.empty())return {};
        if(num(view,"viewer",-1)<0||num(view,"viewer",-1)>1||actions.size()>4096)return {};
        for(const auto& a:actions)if(!a.is_object()||!a.contains("command")||!a["command"].is_object()||!a["command"].contains("type")||!a["command"]["type"].is_string())return {};
        Position p=position(view);
        if(turn!=p.turn){turn=p.turn;actionsThisTurn=0;storedThisTurn=false;withdrewThisTurn=false;}
        std::vector<double> scores; scores.reserve(actions.size());double best=-std::numeric_limits<double>::infinity();std::size_t bestIndex=0;
        const bool selection=actions[0]["command"]["type"]=="select_camps";
        const bool pending=actions[0]["command"]["type"]=="choose";
        for(std::size_t i=0;i<actions.size();++i){double s=actionScore(p,view,actions[i],actions);scores.push_back(s);if(s>best){best=s;bestIndex=i;}}
        if(difficulty==AIDifficulty::Easy){
            // Easy chooses among plausible actions with much less consistency;
            // it still drafts, protects camps, and finishes mandatory choices.
            if(selection)bestIndex=std::size_t(random()%actions.size());
            else if(random()%100<42){std::vector<std::size_t> candidates;for(std::size_t i=0;i<scores.size();++i)if(scores[i]>=-8&&actions[i]["command"]["type"]!="end_turn")candidates.push_back(i);if(!candidates.empty())bestIndex=candidates[random()%candidates.size()];}
            else{for(std::size_t i=0;i<scores.size();++i){double noisy=scores[i]+double(random()%1800)/100-9;if(noisy>best){best=noisy;bestIndex=i;}}}
        }else{
            // Seeded tie breaking avoids identical drafts while preserving
            // tactical priorities and reproducibility.
            std::vector<std::size_t> ties;for(std::size_t i=0;i<scores.size();++i)if(std::abs(scores[i]-best)<.000001)ties.push_back(i);
            if(!ties.empty())bestIndex=ties[random()%ties.size()];
        }
        if(!selection&&!pending&&actionsThisTurn>=128)for(std::size_t i=0;i<actions.size();++i)if(actions[i]["command"]["type"]=="end_turn"){bestIndex=i;break;}
        const auto& chosen=actions[bestIndex]["command"];
        if(chosen["type"]=="silo")storedThisTurn=true;
        if(chosen["type"]=="junk"){const Card* c=p.find(num(chosen,"card"));if(c&&c->key=="hip_flask")withdrewThisTurn=true;}
        ++actionsThisTurn;lastView=viewJson;lastLegal=legalJson;lastAnswer=chosen.dump();return lastAnswer;
    }
};
AIPlayer::AIPlayer(const std::string& catalog,AIDifficulty difficulty,std::uint64_t seed):impl_(std::make_unique<Impl>(catalog,difficulty,seed)){}
AIPlayer::~AIPlayer()=default;
AIPlayer::AIPlayer(AIPlayer&&) noexcept=default;
AIPlayer& AIPlayer::operator=(AIPlayer&&) noexcept=default;
std::string AIPlayer::Choose(const std::string& view,const std::string& legal){try{return impl_->choose(view,legal);}catch(const std::exception&){return {};}}
void AIPlayer::Reset(std::uint64_t seed){impl_->rng=seed?seed:1;impl_->lastView.clear();impl_->lastLegal.clear();impl_->lastAnswer.clear();impl_->turn=-1;impl_->actionsThisTurn=0;impl_->storedThisTurn=false;impl_->withdrewThisTurn=false;}
}
