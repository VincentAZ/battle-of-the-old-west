#include "OldWestAnalysisPresentation.h"
#include <cassert>
#include <iostream>

using J = nlohmann::ordered_json;
int main() {
    oldwest::presentation::AnalysisScenes scenes;
    assert(scenes.Begin(60, 94, 1, 0, "prospector", true, 0, 16));
    assert(scenes.Begin(72, 94, 1, 0, "prospector", true, 94, 16));
    // A coalesced network update contains death, then the free response.
    scenes.CancelSource(94, "source_death", 71);
    assert(!scenes.Contains(60) && scenes.Contains(72));
    assert(!scenes.Begin(80, 99, 1, 0, "prospector", false, 99, 16));
    assert(!scenes.Begin(81, 99, 1, 0, "", true, 99, 16));
    for (int i = 0; i != 3; ++i) {
        J event = {{"analysis_sequence",72},{"source",94},{"player",1},
            {"sequence",73+i},{"reveal_index",i},{"target",96+i},
            {"detail",i == 0 ? "Doc Holliday" : i == 1 ? "Barn Burner" : "Widow with a Shotgun"},
            {"junk_effect",i == 2 ? "raid" : "injure"}};
        assert(scenes.RevealEvent(event));
    }
    scenes.Started(72);
    scenes.SetFallback(72, "western_crew_generic_action");
    scenes.Presented(72, 75);
    scenes.FinishFallbacks();
    assert(scenes.Get(72)["phase"] == "awaiting_public_choice");
    J choice = {{"analysis_sequence",72},{"source",94},{"player",1},
        {"sequence",76},{"revision",24},{"reveal_index",0},{"target",96},
        {"selection","selected"},{"junk_effect","injure"}};
    assert(scenes.AcceptEvent(choice));
    scenes.FinishFallbacks();
    assert(!scenes.Contains(72));
    auto debug = scenes.Debug();
    assert(debug["untracked_decisions"] == 0 && debug["rejected_metadata"] == 0);
    assert(debug["history"].back()["completion_reason"] == "public_decision_recorded_generic_fallback");
    assert(debug["history"].back()["reveals_presented"] == true);
    assert(scenes.Begin(90, 94, 1, 0, "prospector", true, 94, 16));
    scenes.CancelSource(94, "source_removed");
    assert(!scenes.Contains(90));
    std::cout << "Final-response analysis ordering, public identity and choice lifecycle passed\n";
}
