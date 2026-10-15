#include "OldWestAssetHistory.h"
#include <cassert>
#include <cstring>
#include <set>
#include <iostream>
using J=nlohmann::ordered_json;
int main() {
    using namespace OldWestAssetHistory;
    std::set<std::string> keys;
    for(const auto& note:Notes) {
        assert(keys.insert(note.Key).second);
        std::string body=note.Body;
        const auto lines=1+std::count(body.begin(),body.end(),'\n');
        assert(lines>=2 && lines<=3);
        size_t begin=0;
        for(size_t end=body.find('\n');;end=body.find('\n',begin)) {
            assert((end==std::string::npos?body.size():end)-begin<=52);
            if(end==std::string::npos)break;
            begin=end+1;
        }
        assert(std::string(note.Url).starts_with("https://"));
    }
    J hidden={{"card_id","quanah_parker"},{"punk",true},{"private_peek",{{"card_id","sarah_winnemucca"},{"name","Secret face"}}}};
    const auto before=hidden.dump();
    assert(std::string(ForVisibleCard(hidden)->Key)=="drifter");
    assert(hidden.dump()==before);
    hidden["damage"]=1;
    const auto woundedHidden=hidden.dump();
    assert(std::string(ForVisibleWound(hidden)->Key)=="wounded-bandage");
    assert(std::string(ForVisibleCard(hidden)->Key)=="drifter");
    assert(hidden.dump()==woundedHidden);
    assert(!ForVisibleWound(J{{"card_id","quanah_parker"},{"damage",0}}));
    assert(!ForVisibleWound(J{{"card_id","quanah_parker"},{"damage",1},{"destroyed",true}}));
    assert(!ForVisibleWound(J{{"card_id","saloon"},{"damage",1}}));
    assert(!ForVisibleWound(J{{"card_id","unknown"},{"damage",1}}));
    assert(std::string(ForVisibleCard(J{{"card_id","stampede"}})->Key)=="stampede");
    assert(std::string(ForVisibleCard(J{{"card_id","hip_flask"}})->Key)=="whiskey-supplies");
    assert(std::string(ForVisibleCard(J{{"card_id","hip_flask"},{"punk",true}})->Key)=="drifter");
    assert(std::string(ForVisibleCard(J{{"card_id","quanah_parker"}})->Key)=="quanah-parker");
    // Catalog previews have no physical-copy sidecar and show the first Crew
    // appearance. Live paired copies are checked by native_cosmetics_tests.
    assert(std::string(ForVisibleCard(J{{"card_id","pinkerton_agent"},{"punk",false}})->Key)=="pinkerton-agent");
    assert(std::string(ForVisibleCard(J{{"card_id","sarah_winnemucca"},{"punk",false}})->Key)=="sarah-winnemucca");
    // Every revised base camp shows its own Western holding note; expansion
    // camps without an approved skin stay without one.
    std::set<std::string> holdingKeys;
    for(const auto& entry:OldWestHoldings::Entries) {
        const auto* note=ForVisibleCard(J{{"card_id",entry.CampId},{"type","camp"}});
        assert(note && std::string(note->Key)==entry.Key);
        assert(holdingKeys.insert(entry.Key).second);
    }
    assert(holdingKeys.size()==34);
    assert(std::string(ForVisibleCard(J{{"card_id","gallows"},{"type","camp"}})->Key)=="holding-gallows");
    assert(std::string(ForVisibleCard(J{{"card_id","gallows"},{"punk",true}})->Key)=="drifter");
    const J notice={{"card_id","wanted_poster_board"},{"type","camp"}};
    assert(std::string(ForVisibleCard(notice)->Key)=="holding-wanted-poster-board");
    const J gunsmith={{"card_id","gunsmith"},{"type","camp"}};
    assert(std::string(ForVisibleCard(gunsmith)->Key)=="holding-gunsmith");
    const J ridge={{"card_id","rockslide_ridge"},{"type","camp"}};
    assert(std::string(ForVisibleCard(ridge)->Key)=="holding-rockslide-ridge");
    const J lookout={{"card_id","lookout_ridge"},{"type","camp"}};
    assert(std::string(ForVisibleCard(lookout)->Key)=="holding-lookout-ridge");
    assert(std::string(ForVisibleCard(J{{"card_id","lookout_ridge"},{"punk",true}})->Key)=="drifter");
    const J courthouse={{"card_id","courthouse"},{"type","camp"}};
    const J homestead={{"card_id","free_homestead"},{"type","camp"}};
    const J station={{"card_id","pony_express_station"},{"type","camp"}};
    assert(std::string(ForVisibleCard(station)->Key)=="holding-pony-express-station");
    assert(std::string(ForVisibleCard(J{{"card_id","pony_express_station"},{"punk",true}})->Key)=="drifter");
    const J chuckwagon={{"card_id","chuckwagon"},{"type","camp"}};
    assert(std::string(ForVisibleCard(chuckwagon)->Key)=="holding-chuckwagon");
    assert(std::string(ForVisibleCard(J{{"card_id","chuckwagon"},{"punk",true}})->Key)=="drifter");
    assert(std::string(ForVisibleCard(homestead)->Key)=="holding-free-homestead");
    assert(std::string(ForVisibleCard(J{{"card_id","free_homestead"},{"punk",true}})->Key)=="drifter");
    assert(std::string(ForVisibleCard(courthouse)->Key)=="holding-courthouse");
    assert(std::string(ForVisibleCard(J{{"card_id","courthouse"},{"punk",true}})->Key)=="drifter");
    assert(std::string(ForVisibleCard(J{{"card_id","rockslide_ridge"},{"punk",true}})->Key)=="drifter");
    // Owner-only inspection must never substitute a hidden Crew's named history.
    const J inspected={{"card_id","punk"},{"punk",true},{"private_peek",{{"card_id","wanted_poster_board"}}}};
    assert(std::string(ForVisibleCard(inspected)->Key)=="drifter");
    assert(std::string(ForVisibleCard(J{{"card_id","saloon"}})->Title)=="Saloon");
    assert(ForVisibleCard(J{{"card_id","dance_hall"},{"type","camp"}})==nullptr);
    assert(ForVisibleCard(J{{"card_id","coal_yard"},{"type","camp"}})==nullptr);
    for(const auto& trouble:OldWestTrouble::Entries) {
        const auto* note=ForVisibleCard(J{{"card_id",trouble.CardId},{"type","event"}});
        assert(note && std::string(note->Key)==trouble.Key);
        // Even malformed/private preview data cannot bypass the Drifter mask.
        assert(std::string(ForVisibleCard(J{{"card_id",trouble.CardId},{"punk",true}})->Key)=="drifter");
    }
    assert(ForVisibleCard(J{{"card_id","unknown"},{"punk",false}})==nullptr);
    assert(!ForVisibleCard(nullptr));
    std::cout<<"History privacy, source, line-budget and inactive-asset checks passed\n";
}
