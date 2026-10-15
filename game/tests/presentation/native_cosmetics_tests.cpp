#include "OldWestRules.h"
#include "../../OldWest/Source/OldWestGame/Private/OldWestCosmetics.h"
#include "../../OldWest/Source/OldWestGame/Private/OldWestAssetHistory.h"
#include <fstream>
#include <iostream>
#include <sstream>
#include <stdexcept>
using J=nlohmann::ordered_json;
void check(bool v,const char* why){if(!v)throw std::runtime_error(why);}
J state(const oldwest::Engine& e){return J::parse(e.SaveJson());}
void apply(oldwest::Engine& e,int p,const J& c){check(J::parse(e.Apply(p,c.dump())).value("ok",false),"Legal action rejected");}
J actions(const oldwest::Engine& e,int p=0){return J::parse(e.LegalActionsJson(p));}
void act(oldwest::Engine& e,const char* type,int id=0){for(const auto& a:actions(e))if(a["command"].value("type",std::string())==type && (!id||a["command"].value("card",a["command"].value("source",0))==id)){apply(e,0,a["command"]);return;}throw std::runtime_error(std::string("Missing action ")+type);}
void settle(oldwest::Engine& e){for(int i=0;i<30&&!state(e)["choice"].is_null();++i){int p=state(e)["choice"]["player"];auto a=actions(e,p);auto c=a[0]["command"];for(const auto& v:a)if(v.value("label",std::string()).find("Skip")!=std::string::npos)c=v["command"];apply(e,p,c);}}
void erase(J& a,int id){for(auto i=a.begin();i!=a.end();)if(*i==id)i=a.erase(i);else ++i;}
void move(J& s,int id,int player,int column=-1,bool punk=false){erase(s["deck"],id);erase(s["discard"],id);for(auto& p:s["players"]){erase(p["hand"],id);for(auto& c:p["columns"])erase(c,id);}auto& c=s["cards"][std::to_string(id)];c["owner"]=player;c["zone"]=column<0?"hand":"board";c["punk"]=punk;c["damage"]=0;c["destroyed"]=false;c["ready"]=true;c["uses"]=0;if(column<0)s["players"][player]["hand"].push_back(id);else s["players"][player]["columns"][column].insert(s["players"][player]["columns"][column].begin(),id);}
void load(oldwest::Engine& e,const J& s,const std::string& tags){std::string error;check(e.RestoreJson(s.dump(),&error),error.c_str());check(e.RestoreCosmeticJson(tags),"Cosmetic persistence rejected");}
J payload(const oldwest::Engine& e,int p){return {{"view",J::parse(e.ViewJson(p))},{"cosmetics",J::parse(e.CosmeticViewJson(p))},{"actions",actions(e,p)}};}
int main(int argc,char**argv){try{
 std::ifstream f(argv[1]);std::stringstream buffer;buffer<<f.rdbuf();const auto catalog=buffer.str();
 const auto definitions=J::parse(catalog);
 for(const auto& definition:definitions["cards"])
     check(OldWestCosmetics::Visual(definition)==(OldWestCrew::ForCopy(definition["id"].get<std::string>()) ? OldWestCrew::ForCopy(definition["id"].get<std::string>())->Visual : definition["id"].get<std::string>()),"Catalog preview mapping failed");
 check(OldWestCosmetics::Visual(J{{"id",42}}).empty(),"Numeric instance ID became an asset ID");
 std::set<std::string> identities,meshPaths;
 for(const auto& entry:OldWestCrew::Entries) {
     check(identities.insert(entry.Visual).second,"Duplicate Crew visual identity");
     check(meshPaths.insert(entry.Mesh).second,"Reused Crew skeletal mesh");
     check(OldWestCrew::ForCopy(entry.Canonical,entry.Copy)==&entry,"Physical copy mapping mismatch");
     J card={{"id",1},{"card_id",entry.Canonical},{"visual_id",entry.Visual},{"punk",false}};
     check(OldWestCosmetics::Visual(card)==entry.Visual,"46-copy visual resolution failed");
     const auto* note=OldWestAssetHistory::ForVisibleCard(card);
     check(note&&note->Key==std::string(entry.Visual)&&note->Body[0]&&note->Url[0]&&note->Attribution,"Every copy needs sourced visible history");
     card["punk"]=true;card["private_peek"]={{"card_id",entry.Canonical},{"visual_id",entry.Visual}};
     check(OldWestCosmetics::Visual(card)=="punk"&&OldWestAssetHistory::ForVisibleCard(card)->Key==std::string("drifter"),"Hidden or private-peek identity leaked");
 }
 check(identities.size()==46&&meshPaths.size()==46,"Crew coverage is not 46 distinct copies");
 // Exercise real public-handle replacement for every physical copy, then
 // persist/reconnect using the server-private sidecar. Canonical state stays
 // independent from the arbitrary naming and display data.
 for(const auto& entry:OldWestCrew::Entries) {
     oldwest::Engine e(catalog,123);for(int p=0;p<2;++p)apply(e,p,actions(e,p)[0]["command"]);settle(e);
     auto tags=J::parse(e.CosmeticSaveJson());auto s=state(e);int id=0;
     for(auto it=tags.begin();it!=tags.end();++it)if(it.value()==entry.Visual)id=std::stoi(it.key());
     check(id!=0,"Physical Crew copy missing");
     s["status"]="actions";s["choice"]=nullptr;s["tasks"]=J::array();s["active_player"]=0;s["turn"]=5;
     move(s,id,0);erase(s["players"][0]["hand"],id);s["cards"][std::to_string(id)]["zone"]="deck";s["cards"][std::to_string(id)]["owner"]=-1;s["deck"].insert(s["deck"].begin(),id);s["players"][0]["water"]=20;
     load(e,s,tags.dump());check(!J::parse(e.CosmeticViewJson(0)).contains(std::to_string(id)),"Deck identity leaked");act(e,"draw");
     int publicId=0;auto after=J::parse(e.CosmeticSaveJson());for(auto it=after.begin();it!=after.end();++it)if(it.value()==entry.Visual)publicId=std::stoi(it.key());
     check(publicId&&publicId!=id&&!after.contains(std::to_string(id)),"Every Crew copy must survive rekey");
     check(J::parse(e.CosmeticViewJson(0))[std::to_string(publicId)]==entry.Visual,"Drawn copy lost identity");
     check(!J::parse(e.CosmeticViewJson(1)).contains(std::to_string(publicId)),"Network sidecar leaked opponent hand");
     const auto canonical=e.SaveJson();oldwest::Engine restored(catalog,7);load(restored,state(e),e.CosmeticSaveJson());check(restored.SaveJson()==canonical&&restored.CosmeticSaveJson()==e.CosmeticSaveJson(),"Restore changed rules state or appearance");
     auto invalid=after;invalid[std::to_string(publicId)]="not-a-crew-character";check(!e.RestoreCosmeticJson(invalid.dump())&&e.CosmeticSaveJson()==after.dump()&&e.SaveJson()==canonical,"Invalid cosmetics changed engine or sidecar");
 }
 // Legacy Native sidecars still pin Lozen/Sarah while the other appearances
 // are filled deterministically; full modern sidecars reject missing entries.
 {
     oldwest::Engine e(catalog,5);const auto all=J::parse(e.CosmeticSaveJson());J legacy=J::object();
     for(auto it=all.begin();it!=all.end();++it)if(it.value()=="lozen"||it.value()=="sarah-winnemucca")legacy[it.key()]=it.value();
     const auto canonical=e.SaveJson();check(e.RestoreCosmeticJson(legacy.dump()),"Legacy Native sidecar upgrade failed");check(e.CosmeticSaveJson()==all.dump()&&e.SaveJson()==canonical,"Legacy upgrade changed physical identities or rules");
     auto missing=all;missing.erase(missing.begin());check(!e.RestoreCosmeticJson(missing.dump()),"Incomplete full sidecar accepted");
 }

 for(int seed=1;seed<=12;++seed){
 oldwest::Engine e(catalog,seed);const auto initialTags=e.CosmeticSaveJson();check(J::parse(initialTags).size()==46,"Every physical person copy receives a distinct identity");
 const auto selection=OldWestCosmetics::Present(payload(e,0));
 for(const auto& offer:selection["view"]["players"][0]["offers"])
     check(OldWestCosmetics::Visual(offer)==offer["id"].get<std::string>(),"Camp-selection portrait lost its offered camp ID");
 // Legal opening draws must rekey the cosmetic sidecar without tagging hidden hands.
 for(int p=0;p<2;++p)apply(e,p,actions(e,p)[0]["command"]);settle(e);
 auto tags=e.CosmeticSaveJson();auto s=state(e);int lozen=0,sarah=0,twin=0;
 const J map=J::parse(tags);for(auto it=map.begin();it!=map.end();++it){if(it.value()=="lozen")lozen=std::stoi(it.key());else if(it.value()=="sarah-winnemucca")sarah=std::stoi(it.key());}
 for(const auto& c:s["cards"])if(c["card_id"]=="pinkerton_agent"&&c["id"]!=lozen)twin=c["id"];
 check(lozen&&sarah&&twin,"Named and generic physical copies exist");
 s["status"]="actions";s["choice"]=nullptr;s["tasks"]=J::array();s["active_player"]=0;s["turn"]=5;
 for(auto& p:s["players"]){p["water"]=20;for(const auto& col:p["columns"])for(int id:col)s["cards"][std::to_string(id)]["card_id"]="gatling_emplacement";}
 move(s,lozen,0);move(s,sarah,0);move(s,twin,0);load(e,s,tags);
 for(int id:{lozen,sarah,twin}){check(J::parse(e.CosmeticViewJson(0)).contains(std::to_string(id)),"Owner sees each distinct hand copy");check(!J::parse(e.CosmeticViewJson(1)).contains(std::to_string(id)),"Opponent cannot infer private named hands");}
 auto raw=payload(e,0);auto display=OldWestCosmetics::Present(raw);
 for(size_t i=0;i<raw["actions"].size();++i)check(raw["actions"][i]["command"]==display["actions"][i]["command"],"Presentation changed legal command");
 bool generic=false,named=false;for(const auto& c:display["view"]["players"][0]["hand"]){if(c["id"]==lozen){check(c["name"]=="Lozen"&&c["card_id"]=="pinkerton_agent","Lozen name/identity split");check(OldWestAssetHistory::ForVisibleCard(c)->Key==std::string("lozen"),"Lozen history");named=true;}if(c["id"]==twin){check(c["name"]=="Pinkerton Agent"&&OldWestAssetHistory::ForVisibleCard(c)->Key==std::string("pinkerton-agent"),"Distinct first-copy identity and history");generic=true;}}
 check(generic&&named,"Both duplicate presentations inspected");
 const auto before=e.SaveJson(),beforeTags=e.CosmeticSaveJson();check(!J::parse(e.Apply(1,R"({"type":"play","card":-1})")).value("ok",false),"Bad action rejected");check(before==e.SaveJson()&&beforeTags==e.CosmeticSaveJson(),"Rejected action atomicity");
 act(e,"play",lozen);settle(e);act(e,"play",sarah);settle(e);
 for(int id:{lozen,sarah})check(J::parse(e.CosmeticViewJson(0))[std::to_string(id)]==J::parse(e.CosmeticViewJson(1))[std::to_string(id)],"Both peers agree on named board copies");
 act(e,"activate",sarah);
 auto returnRaw=payload(e,0);auto returnDisplay=OldWestCosmetics::Present(returnRaw);bool namedOption=false;
 for(size_t i=0;i<returnRaw["actions"].size();++i){const auto& a=returnRaw["actions"][i];const auto& shown=returnDisplay["actions"][i];check(a["command"]==shown["command"],"Choice command changed");if(a.value("target",0)==lozen){check(shown["label"].get<std::string>().find("Lozen")!=std::string::npos,"Return target must display Lozen");for(const auto& o:returnDisplay["view"]["choice"]["options"])if(o["id"]==a["command"]["option"]){check(o["label"]==shown["label"],"Choice option and action disagree");namedOption=true;}}}
 check(namedOption,"Named return option inspected");bool returned=false;auto choice=state(e)["choice"];for(const auto& option:choice["options"]){for(const auto& task:option["tasks"])if(task.value("target",0)==lozen){apply(e,0,{{"type","choose"},{"option",option["id"]}});returned=true;break;}if(returned)break;}check(returned,"Sarah returns Lozen legally");settle(e);
 check(state(e)["cards"][std::to_string(lozen)]["zone"]=="hand","Return actually moved Lozen");check(J::parse(e.CosmeticViewJson(0))[std::to_string(lozen)]=="lozen","Return preserves appearance");act(e,"play",lozen);settle(e);
 check(J::parse(e.CosmeticViewJson(1))[std::to_string(lozen)]=="lozen","Replay visible to opponent");
 tags=e.CosmeticSaveJson();s=state(e);s["cards"][std::to_string(lozen)]["punk"]=true;load(e,s,tags);
 for(int p=0;p<2;++p)check(!J::parse(e.CosmeticViewJson(p)).contains(std::to_string(lozen)),"Face-down identity masked");
 auto masked=OldWestCosmetics::Present({{"view",J::parse(e.ViewJson(0))},{"cosmetics",map}});for(const auto& col:masked["view"]["players"][0]["columns"])for(const auto& c:col)if(c["id"]==lozen){check(OldWestCosmetics::Visual(c)=="punk","Spoofed hidden tag ignored");check(OldWestAssetHistory::ForVisibleCard(c)->Key==std::string("drifter"),"Hidden history stays generic");}
 oldwest::Engine restored(catalog,999);load(restored,state(e),e.CosmeticSaveJson());check(restored.CosmeticSaveJson()==e.CosmeticSaveJson(),"Save/reload retains physical copies");
 // Move the named copy back to the top of a deck fixture, then use a real draw.
 s=state(e);move(s,lozen,0);erase(s["players"][0]["hand"],lozen);auto& c=s["cards"][std::to_string(lozen)];c["zone"]="deck";c["owner"]=-1;c["punk"]=false;s["deck"].insert(s["deck"].begin(),lozen);s["players"][0]["water"]=20;load(e,s,tags);act(e,"draw");
 bool rekey=false;const auto current=J::parse(e.CosmeticSaveJson());for(auto it=current.begin();it!=current.end();++it)if(it.value()=="lozen"){check(std::stoi(it.key())!=lozen,"Draw replaces public handle");rekey=true;}
 check(rekey,"Named copy survived rekey");
 // A Lozen attack on the other Pinkerton Agent must name the target, not its source.
 tags=e.CosmeticSaveJson();s=state(e);for(auto it=current.begin();it!=current.end();++it)if(it.value()=="lozen")lozen=std::stoi(it.key());
 move(s,lozen,0,0);move(s,twin,1,0);int raid=s["players"][1]["stampede"];s["players"][1]["queue"][2]=raid;s["cards"][std::to_string(raid)]["zone"]="queue";s["cards"][std::to_string(raid)]["owner"]=1;load(e,s,tags);
 auto attacks=OldWestCosmetics::Present(payload(e,0));bool twinGesture=false;
 for(const auto& a:attacks["actions"])if(a["command"].value("source",0)==lozen&&a.contains("gestures"))for(const auto& g:a["gestures"])if(g.value("target",0)==twin){check(g["label"]=="Damage Pinkerton Agent","Named source overwrote distinct duplicate target");twinGesture=true;}
 check(twinGesture,"Real duplicate-target attack gesture inspected");

 }
 std::cout<<"Crew cosmetics: 46 identities and 12 seeds pass paired-copy, privacy, legal return/replay, draw rekey, rollback and persistence checks\n";
 return 0;}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
