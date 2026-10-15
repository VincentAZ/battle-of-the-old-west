#include "OldWestHUD.h"
#include "OldWestDockPanel.h"
#include "OldWestSectionBody.h"
#include "OldWestSession.h"
#include "Misc/ConfigCacheIni.h"
#include "Widgets/Layout/SConstraintCanvas.h"

bool SOldWestHUD::PanelGestureActive() const
{
    for(const auto& Panel:DockPanels) if(Panel.IsValid()&&Panel->IsInteracting()) return true;
    for(const auto& Section:SectionBodies)if(Section.IsValid()&&Section->IsResizing())return true;
    return false;
}

void SOldWestHUD::SavePanelLayout()
{
    if(!GConfig||!Preferences()||!Preferences()->CanPersist()) return;
    for(const auto& Pair:PanelStates)
    {
        const FString Section=TEXT("OldWest.Panel.")+Pair.Key;
        const auto& State=*Pair.Value;
        GConfig->SetFloat(*Section,TEXT("X"),State.Position.X,GGameUserSettingsIni);
        GConfig->SetFloat(*Section,TEXT("Y"),State.Position.Y,GGameUserSettingsIni);
        GConfig->SetFloat(*Section,TEXT("Width"),State.Size.X,GGameUserSettingsIni);
        GConfig->SetFloat(*Section,TEXT("Height"),State.Size.Y,GGameUserSettingsIni);
        GConfig->SetBool(*Section,TEXT("Collapsed"),State.bCollapsed,GGameUserSettingsIni);
    }
    GConfig->Flush(false,GGameUserSettingsIni);
}

void SOldWestHUD::ResetPanelLayout()
{
    if(GConfig&&Preferences()&&Preferences()->CanPersist())
    {
        for(const auto& Pair:PanelStates) GConfig->EmptySection(*(TEXT("OldWest.Panel.")+Pair.Key),GGameUserSettingsIni);
        GConfig->EmptySection(TEXT("OldWest.BattleSections"),GGameUserSettingsIni);
        GConfig->EmptySection(TEXT("OldWest.SectionHeights"),GGameUserSettingsIni);
        GConfig->Flush(false,GGameUserSettingsIni);
    }
    BattleSections.Reset();BattleScrollOffsets.Reset();SectionStates.Reset();
    PanelStates.Reset();PanelLayers.Reset();FrontPanelLayer=20.f;Dirty=true;
}

void SOldWestHUD::AddDockPanel(TSharedRef<SConstraintCanvas> Canvas,const FString& Id,const FText& Title,
    FVector2D Position,FVector2D Size,FVector2D MinimumSize,TSharedRef<SWidget> Content,bool IsOverview,bool IsActions)
{
    TSharedPtr<FOldWestDockPanelState>& Saved=PanelStates.FindOrAdd(Id);
    if(!Saved.IsValid())
    {
        Saved=MakeShared<FOldWestDockPanelState>();Saved->Position=Position;Saved->Size=Size;
        if(GConfig&&Preferences()&&Preferences()->CanPersist())
        {
            const FString Section=TEXT("OldWest.Panel.")+Id;
            float X=Position.X,Y=Position.Y,W=Size.X,H=Size.Y;
            GConfig->GetFloat(*Section,TEXT("X"),X,GGameUserSettingsIni);
            GConfig->GetFloat(*Section,TEXT("Y"),Y,GGameUserSettingsIni);
            GConfig->GetFloat(*Section,TEXT("Width"),W,GGameUserSettingsIni);
            GConfig->GetFloat(*Section,TEXT("Height"),H,GGameUserSettingsIni);
            GConfig->GetBool(*Section,TEXT("Collapsed"),Saved->bCollapsed,GGameUserSettingsIni);
            Saved->Position=FVector2D(X,Y);Saved->Size=FVector2D(W,H);
        }
    }
    // Migrate the former stock full-width history footprint; custom layouts
    // continue to use their saved coordinates and ordinary bounds clamping.
    if(Id==TEXT("field_enemy")&&Saved->Size.Equals(FVector2D(900,850))&&Saved->Position.Equals(FVector2D(964,0))) {
        Saved->Size=Size;Saved->Position=Position;
    }
    // A required answer must surface even if the player had folded Actions.
    if(IsActions&&PendingChoice) Saved->bCollapsed=false;
    const TWeakPtr<SOldWestHUD> Weak=SharedThis(this);
    const TWeakPtr<SConstraintCanvas> WeakCanvas=Canvas;
    const auto SlotAddress=MakeShared<SConstraintCanvas::FSlot*>(nullptr);
    const float Layer=IsActions&&(PendingChoice||(Owner.IsValid()&&Owner->HasAnalysisChoiceView()))?++FrontPanelLayer:PanelLayers.FindOrAdd(Id,IsOverview?10.f:float(DockPanels.Num()+1));
    TSharedRef<SOldWestDockPanel> Panel=SNew(SOldWestDockPanel).PanelId(Id).Title(Title).State(Saved).MinSize(MinimumSize)
        .Bounds_Lambda([Weak]() {
            const auto HUD=Weak.Pin();FVector2D Extent(1864,914);
            if(HUD.IsValid()&&HUD->Workspace.IsValid())
            {const FVector2D Actual=HUD->Workspace->GetCachedGeometry().GetLocalSize();if(Actual.X>100&&Actual.Y>100)Extent=Actual;}
            // Every floating panel may use the full workspace. The old bottom-hand
            // reserve prevented history and reference panels from extending downward.
            return FSlateRect(0,0,Extent.X,Extent.Y);
        })
        .Visibility_Lambda([Weak,Id,IsOverview,IsActions]() {
            const auto HUD=Weak.Pin();if(!HUD.IsValid()||(HUD->DraggedCard!=INDEX_NONE&&!HUD->DragKeepsPanels))return EVisibility::Hidden;
            if(Id==TEXT("master")&&!HUD->BattlePlanOpen)return EVisibility::Hidden;
            if(HUD->Owner.IsValid()&&HUD->Owner->IsCinematicBusy())return EVisibility::Hidden;
            if(IsOverview&&!HUD->OverviewOpen)return EVisibility::Hidden;
            if(!IsOverview&&HUD->OverviewOpen&&!(IsActions&&(HUD->PendingChoice||(HUD->Owner.IsValid()&&HUD->Owner->HasAnalysisChoiceView()))))return EVisibility::Hidden;
            return EVisibility::Visible;
        })
        .OnStateChanged_Lambda([Weak,Id](const FOldWestDockPanelState&,bool Finished) {if(const auto HUD=Weak.Pin())if(Finished){HUD->SavePanelLayout();if(Id.StartsWith(TEXT("field_")))HUD->Dirty=true;}})
        .OnActivated_Lambda([Weak,WeakCanvas,SlotAddress,Id]() {
            if(const auto HUD=Weak.Pin())if(WeakCanvas.IsValid()&&*SlotAddress)
            {const float Raised=++HUD->FrontPanelLayer;HUD->PanelLayers.Add(Id,Raised);(*SlotAddress)->SetZOrder(Raised);}
        })[Content];
    const TWeakPtr<SOldWestDockPanel> WeakPanel=Panel;
    Canvas->AddSlot().Expose(*SlotAddress).Anchors(FAnchors(0,0)).Alignment(FVector2D::ZeroVector).AutoSize(false).ZOrder(Layer)
        .Offset_Lambda([WeakPanel]() {const auto P=WeakPanel.Pin();return P.IsValid()?P->GetCanvasOffset():FMargin();})[Panel];
    DockPanels.Add(Panel);
}
