#pragma once
#include <algorithm>
#include <cmath>

// The production component and portable tests use this exact clock. It owns
// presentation time only: a decision must already be accepted public metadata.
class FOldWestScientistClock
{
public:
    enum class EPhase { Inactive, EntryBlend, Holster, Inspect, WorkHold,
        SortLeft, SortMiddle, SortRight, Recover, SkipRecover, NoChoiceRecover, Unholster, Complete };
    EPhase Phase = EPhase::Inactive;
    double Seconds = 0.;
    double TotalSeconds = 0.;
    int Decision = -2; // -2 unknown, -1 accepted Skip, 0..2 actual reveal index.
    bool NoChoice = false;

    void Begin() { Phase = EPhase::EntryBlend; Seconds = TotalSeconds = 0.; Decision = -2; NoChoice=false; }
    void Cancel() { Phase = EPhase::Inactive; Seconds = 0.; Decision = -2; NoChoice=false; }
    bool SetDecision(int Index)
    {
        if (Decision != -2 || NoChoice || Index < -1 || Index > 2 || Phase != EPhase::WorkHold) return false;
        Decision = Index; return true;
    }
    bool FinishWithoutDecision() { if (!AwaitingChoice()) return false; NoChoice=true; return true; }
    bool AwaitingChoice() const { return Phase == EPhase::WorkHold && Decision == -2 && !NoChoice; }
    static double Duration(EPhase Value)
    {
        switch (Value)
        {
        case EPhase::EntryBlend: return .3;
        case EPhase::Holster: case EPhase::Unholster: return 3.;
        case EPhase::Inspect: return 134./30.;
        case EPhase::WorkHold: case EPhase::SortLeft: case EPhase::SortRight: return 2.;
        case EPhase::SortMiddle: return 50./30.;
        case EPhase::Recover: case EPhase::SkipRecover: case EPhase::NoChoiceRecover: return 86./30.;
        default: return 0.;
        }
    }
    EPhase SelectedPhase() const
    {
        return NoChoice ? EPhase::NoChoiceRecover : Decision == -1 ? EPhase::SkipRecover : Decision == 0 ? EPhase::SortLeft :
            Decision == 1 ? EPhase::SortMiddle : EPhase::SortRight;
    }
    EPhase Next() const
    {
        switch (Phase)
        {
        case EPhase::EntryBlend: return EPhase::Holster;
        case EPhase::Holster: return EPhase::Inspect;
        case EPhase::Inspect: return EPhase::WorkHold;
        case EPhase::WorkHold: return Decision == -2 && !NoChoice ? EPhase::WorkHold : SelectedPhase();
        case EPhase::SortLeft: case EPhase::SortMiddle: case EPhase::SortRight: return EPhase::Recover;
        case EPhase::Recover: case EPhase::SkipRecover: case EPhase::NoChoiceRecover: return EPhase::Unholster;
        case EPhase::Unholster: return EPhase::Complete;
        default: return Phase;
        }
    }
    // Sample endpoints before Boundary changes phase: this is what permits
    // retaining the actual selected sample transform before shared Recover.
    // An accepted decision waits for the small breathing loop's exact endpoint.
    template<class SampleFn, class BoundaryFn>
    bool Advance(double Delta, SampleFn Sample, BoundaryFn Boundary)
    {
        if (!std::isfinite(Delta) || Delta < 0. || Phase == EPhase::Inactive) return false;
        if (Phase == EPhase::Complete) return true;
        for (int Guard = 0; Guard < 16; ++Guard)
        {
            if (Phase == EPhase::WorkHold && Seconds <= 1e-9 && (Decision != -2 || NoChoice))
            {
                const EPhase Following = SelectedPhase();
                if (!Boundary(Phase, Following)) return false;
                Phase = Following;
            }
            if (Phase == EPhase::WorkHold && Decision == -2 && !NoChoice)
            {
                Seconds = std::fmod(Seconds + Delta, Duration(Phase));
                TotalSeconds += Delta;
                return Sample(Phase, Seconds);
            }
            const double Step = std::min(Delta, std::max(0., Duration(Phase) - Seconds));
            Seconds += Step; TotalSeconds += Step; Delta -= Step;
            if (!Sample(Phase, Seconds)) return false;
            if (Seconds + 1e-9 < Duration(Phase)) return true;
            const EPhase Previous = Phase, Following = Next();
            if (!Boundary(Previous, Following)) return false;
            Phase = Following; Seconds = 0.;
            if (Phase == EPhase::Complete) return true;
            if (Delta <= 1e-9) return Sample(Phase, 0.);
        }
        return false; // A malformed phase graph must never spin indefinitely.
    }
};
