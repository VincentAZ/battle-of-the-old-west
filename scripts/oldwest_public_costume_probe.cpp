// Portable CPU-only discovery. Reads only each acting player's own public view
// and current offered legal commands; never SaveJson, RestoreJson or deck state.
#include "OldWestRules.h"
#include "json.hpp"
#include <fstream>
#include <iostream>
#include <iterator>
#include <map>
#include <set>
using J=nlohmann::ordered_json;
int main(int argc,char**argv) {
 try {
  if(argc!=3)throw std::runtime_error("Usage: public_costume_probe cards.json maximum_seed");
  std::ifstream file(argv[1]);if(!file)throw std::runtime_error("Missing catalog");
  const std::string catalog((std::istreambuf_iterator<char>(file)),{});
  const J catalog_data=J::parse(catalog);
  J defs=J::object();for(const auto& c:catalog_data.at("cards"))defs[c["id"].get<std::string>()]=c;
  const std::set<std::string> wanted={"prospector","gatling_gunner","bounty_hunter"};
  const auto limit=std::stoull(argv[2]);
  for(std::uint64_t seed=1;seed<=limit;++seed) {
   oldwest::Engine engine(catalog,seed,J{{"ruleset","boomtown"}}.dump());
   J journal=J::array();
   for(int seat=0;seat<2;++seat) {
    auto options=J::parse(engine.LegalActionsJson(seat));
    int best=-1;J selected;
    for(const auto& a:options) {
     int score=0;for(const auto& id:a["command"]["camps"])score+=defs[id.get<std::string>()]["starting_cards"].get<int>();
     if(score>best){best=score;selected=a;}
    }
    auto before=J::parse(engine.ViewJson(seat));
    auto accepted=J::parse(engine.Apply(seat,selected["command"].dump()));if(!accepted["ok"].get<bool>())throw std::runtime_error("Rejected offered draft");
    journal.push_back({{"seat",seat},{"revision",before["revision"]},{"command",selected["command"]},{"public_offers",before["players"][seat]["offers"]},{"accepted",accepted}});
   }
   std::set<std::string> found;J hands=J::array(),targets=J::array();
   for(int seat=0;seat<2;++seat) {
    auto view=J::parse(engine.ViewJson(seat));J ids=J::array();
    for(const auto& card:view["players"][seat]["hand"]) {
     std::string id=card.value("card_id",std::string());ids.push_back({{"id",card["id"]},{"card_id",id}});
     if(wanted.count(id)){found.insert(id);targets.push_back({{"seat",seat},{"entity",card["id"]},{"card_id",id}});}
    }
    hands.push_back({{"seat",seat},{"own_authorized_hand",ids}});
   }
   if(found==wanted) {
    std::cout<<J{{"schema",1},{"scope","CPU public-view discovery only; no rendered or action coverage claim"},
     {"seed",seed},{"ruleset","boomtown"},{"selection_journal",journal},{"targets",targets},{"own_hand_evidence",hands},
     {"policy","Replay these offered draft commands, protect target cards, legally deploy and observe idle/walk; use offered attacks on public named targets for hit/fall."}}.dump(2)<<'\n';return 0;
   }
  }
  throw std::runtime_error("No complete public opening hand set within bound");
 } catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}
}
