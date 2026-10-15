#pragma once

#include "Core/json.hpp"
#include <algorithm>
#include <map>
#include <string>
#include <vector>

namespace oldwest::presentation {

// Public presentation metadata only. This owns no rule state, world actor,
// animation or attachment. Bespoke playback registers explicit ownership and
// retires only after real recovery/cancellation; fallback remains separately visible.
class AnalysisScenes {
    using Json = nlohmann::ordered_json;
    struct Reveal {
        int Sequence = 0, Index = -1, Handle = 0;
        std::string Name, Effect;
        bool Presented = false;
    };
    struct Scene {
        int Sequence = 0, Source = 0, Player = 0, CopiedSource = 0, Turn = 0;
        int DecisionSequence = 0, DecisionRevision = 0, SelectedIndex = -1, SelectedHandle = 0;
        std::string Selection, Effect, BoundaryReason;
        bool AbilityPresented = false, Started = false, Accepted = false, Bespoke = false;
        std::string FallbackReason;
        std::vector<Reveal> Reveals;
    };
    std::map<int, Scene> Scenes;
    Json History = Json::array();
    int RejectedMetadata = 0, UntrackedDecisions = 0;

    static bool Complete(const Scene& S) {
        return S.AbilityPresented && !S.Reveals.empty() &&
            std::all_of(S.Reveals.begin(), S.Reveals.end(), [](const Reveal& R) { return R.Presented; });
    }
    static Json Describe(const Scene& S) {
        const char* Phase = !Complete(S) ? (S.Started ? "presenting_reveals" : "queued") :
            S.Accepted ? "selection_accepted" : "awaiting_public_choice";
        Json Out = {{"analysis_sequence", S.Sequence}, {"source", S.Source}, {"player", S.Player},
            {"copied_source", S.CopiedSource}, {"turn", S.Turn}, {"boundary_reason", S.BoundaryReason},
            {"phase", Phase}, {"bespoke", S.Bespoke}, {"fallback_reason", S.FallbackReason},
            {"ability_presented", S.AbilityPresented},
            {"reveals_presented", Complete(S)}, {"accepted", S.Accepted},
            {"decision_sequence", S.DecisionSequence}, {"decision_revision", S.DecisionRevision},
            {"selection", S.Selection}, {"reveal_index", S.SelectedIndex}, {"target", S.SelectedHandle},
            {"junk_effect", S.Effect}, {"reveals", Json::array()}};
        for (const Reveal& R : S.Reveals) Out["reveals"].push_back({{"sequence", R.Sequence},
            {"reveal_index", R.Index}, {"target", R.Handle}, {"name", R.Name},
            {"junk_effect", R.Effect}, {"presented", R.Presented}});
        return Out;
    }
    void Archive(const Scene& S, const char* Reason) {
        Json Item = Describe(S); Item["completion_reason"] = Reason;
        History.push_back(std::move(Item));
        if (History.size() > 8) History.erase(History.begin());
    }

public:
    bool Contains(int Sequence) const { return Scenes.find(Sequence) != Scenes.end(); }

    Json Get(int Sequence) const {
        auto It = Scenes.find(Sequence); return It == Scenes.end() ? Json() : Describe(It->second);
    }
    bool SetBespoke(int Sequence) {
        auto It = Scenes.find(Sequence); if (It == Scenes.end()) return false;
        It->second.Bespoke = true; It->second.FallbackReason.clear(); return true;
    }
    void SetFallback(int Sequence, const char* Reason) {
        auto It = Scenes.find(Sequence); if (It == Scenes.end()) return;
        It->second.Bespoke = false; It->second.FallbackReason = Reason;
    }
    void FinishPresentation(int Sequence, const char* Reason, const Json& Playback) {
        auto It = Scenes.find(Sequence); if (It == Scenes.end()) return;
        Archive(It->second, Reason); History.back()["playback"] = Playback;
        Scenes.erase(It);
    }

    // Caller supplies the effective PUBLIC definition, before any private
    // inspection overlay. A copied Prospector acts through the actual source.
    bool Begin(int Sequence, int Source, int Player, int AbilityIndex,
               const std::string& EffectivePublicDefinition, bool PublicPerson, int CopiedSource, int Turn = 0) {
        if (Sequence <= 0 || Source <= 0 || !PublicPerson || AbilityIndex != 0 ||
            EffectivePublicDefinition != "prospector") return false;
        if (Contains(Sequence)) return true;
        Scene S; S.Sequence = Sequence; S.Source = Source; S.Player = Player; S.CopiedSource = CopiedSource; S.Turn = Turn;
        Scenes.emplace(Sequence, std::move(S));
        return true;
    }

    bool RevealEvent(const Json& Event) {
        const int Key = Event.value("analysis_sequence", 0);
        auto It = Scenes.find(Key); if (It == Scenes.end()) return false;
        Scene& S = It->second;
        const int Index = Event.value("reveal_index", -1), Handle = Event.value("target", 0);
        const int Sequence = Event.value("sequence", 0);
        if (Event.value("source", 0) != S.Source || Event.value("player", -1) != S.Player ||
            Index < 0 || Index > 2 || Handle <= 0 || Sequence <= Key || S.Accepted) {
            ++RejectedMetadata; return false;
        }
        const std::string Name = Event.value("detail", std::string()), Effect = Event.value("junk_effect", std::string());
        for (const Reveal& R : S.Reveals) if (R.Index == Index) {
            const bool Same = R.Sequence == Sequence && R.Handle == Handle && R.Name == Name && R.Effect == Effect;
            if (!Same) ++RejectedMetadata;
            return Same; // Repeated snapshots never duplicate a sample.
        }
        Reveal R; R.Sequence = Sequence; R.Index = Index; R.Handle = Handle; R.Name = Name; R.Effect = Effect;
        S.Reveals.push_back(std::move(R));
        std::sort(S.Reveals.begin(), S.Reveals.end(), [](const Reveal& A, const Reveal& B) { return A.Index < B.Index; });
        return true;
    }

    // This event is metadata, never an extra generic shot. Missing context
    // after reconnect/cinematic Skip does not authorize replaying setup.
    bool AcceptEvent(const Json& Event) {
        const int Key = Event.value("analysis_sequence", 0);
        auto It = Scenes.find(Key); if (It == Scenes.end()) { ++UntrackedDecisions; return false; }
        Scene& S = It->second;
        const int Index = Event.value("reveal_index", -1), Handle = Event.value("target", 0);
        const int Sequence = Event.value("sequence", 0);
        const std::string Choice = Event.value("selection", std::string()), Effect = Event.value("junk_effect", std::string());
        bool Valid = Choice == "skip" && Index == -1 && Handle == 0 && Effect.empty();
        if (Choice == "selected") for (const Reveal& R : S.Reveals)
            Valid |= R.Index == Index && R.Handle == Handle && R.Effect == Effect;
        if (!Valid || S.Accepted || Sequence <= Key || Event.value("source", 0) != S.Source ||
            Event.value("player", -1) != S.Player ||
            std::any_of(S.Reveals.begin(), S.Reveals.end(), [Sequence](const Reveal& R) { return R.Sequence >= Sequence; })) {
            ++RejectedMetadata; return false;
        }
        S.Accepted = true; S.DecisionSequence = Sequence; S.DecisionRevision = Event.value("revision", 0);
        S.SelectedIndex = Index; S.SelectedHandle = Handle; S.Selection = Choice; S.Effect = Effect;
        return true;
    }

    void Started(int Key) { auto It = Scenes.find(Key); if (It != Scenes.end()) It->second.Started = true; }
    void Presented(int Key, int ThroughSequence) {
        auto It = Scenes.find(Key); if (It == Scenes.end()) return;
        Scene& S = It->second;
        if (ThroughSequence >= S.Sequence) S.AbilityPresented = true;
        for (Reveal& R : S.Reveals) if (R.Sequence <= ThroughSequence) R.Presented = true;
    }

    // Call only after ordinary pending beats finish. A nonbusy initial choice
    // wait retains the context. Accepted decisions are archived without claiming
    // that a nested target effect happened; those remain independent rule beats.
    void FinishFallbacks() {
        for (auto It = Scenes.begin(); It != Scenes.end();) {
            if (It->second.Bespoke) { ++It; continue; }
            if (It->second.Accepted && Complete(It->second)) {
                Archive(It->second, "public_decision_recorded_generic_fallback"); It = Scenes.erase(It);
            } else if (!It->second.BoundaryReason.empty() && It->second.AbilityPresented &&
                std::all_of(It->second.Reveals.begin(), It->second.Reveals.end(), [](const Reveal& R) { return R.Presented; })) {
                Archive(It->second, It->second.BoundaryReason.c_str()); It = Scenes.erase(It);
            } else ++It;
        }
    }
    // An authoritative turn/result can arrive while older finite shots still
    // await presentation. Retain every context referenced by those queued beats.
    // A current-turn context is not ended merely because its snapshot starts a
    // new turn. Match/seat baselines and explicit Skip use immediate Reset.
    void Boundary(const char* Reason, int CurrentTurn, bool MatchFinished, const std::vector<int>& QueuedKeys) {
        for (auto It = Scenes.begin(); It != Scenes.end();) {
            Scene& S = It->second;
            if (!MatchFinished && S.Turn >= CurrentTurn) { ++It; continue; }
            if (std::find(QueuedKeys.begin(), QueuedKeys.end(), S.Sequence) != QueuedKeys.end()) {
                S.BoundaryReason = Reason; ++It;
            } else { Archive(S, Reason); It = Scenes.erase(It); }
        }
    }
    void CancelSource(int Source, const char* Reason, int BeforeSequence = 0) {
        for (auto It = Scenes.begin(); It != Scenes.end();) {
            if (It->second.Source == Source && (BeforeSequence == 0 || It->second.Sequence < BeforeSequence)) {
                Archive(It->second, Reason); It = Scenes.erase(It);
            }
            else ++It;
        }
    }
    void Reset(const char* Reason, bool NewEpoch = false) {
        for (const auto& Pair : Scenes) Archive(Pair.second, Reason);
        Scenes.clear();
        if (NewEpoch) { History = Json::array(); RejectedMetadata = UntrackedDecisions = 0; }
    }
    Json Debug() const {
        Json Out = {{"mode", "generic_fallback"}, {"bespoke_assets_enabled", false},
            {"fallback_reason", "Complete Prospector branch assets and contact validation are pending"},
            {"blocks_choice_ui", false}, {"rejected_metadata", RejectedMetadata},
            {"untracked_decisions", UntrackedDecisions}, {"active", Json::array()}, {"history", History}};
        for (const auto& Pair : Scenes) Out["active"].push_back(Describe(Pair.second));
        return Out;
    }
};
}
