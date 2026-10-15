#include "OldWestCosmetics.h"
#include "OldWestDisplayNames.h"
#include "Core/OldWestFieldActions.h"
#include "OldWestHUD.h"
#include "OldWestStaging.h"
#include "OldWestRegion.h"
#include "OldWestReadiness.h"
#include "OldWestSectionBody.h"
#include "OldWestTooltip.h"
#include "OldWestSession.h"
#include "OldWestNetworkAddresses.h"
#include "OldWestBattlefield.h"
#include "OldWestPunkShelter.h"
#include "OldWestCardDrag.h"
#include "OldWestCardPortrait.h"
#include "OldWestDockPanel.h"
#include "Brushes/SlateRoundedBoxBrush.h"
#include "Rendering/DrawElements.h"
#include "Engine/World.h"
#include "Engine/LocalPlayer.h"
#include "Engine/GameViewportClient.h"
#include "SceneView.h"
#include "EngineUtils.h"
#include "OldWestWorldInteraction.h"
#include "Framework/Application/SlateApplication.h"
#include "Framework/MultiBox/MultiBoxBuilder.h"
#include "Fonts/FontMeasure.h"
#include "Widgets/SWindow.h"
#include "HAL/PlatformApplicationMisc.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Misc/ConfigCacheIni.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Kismet/GameplayStatics.h"
#include "Sound/SoundBase.h"
#include "Styling/CoreStyle.h"
#include "Widgets/Input/SButton.h"
#include "Widgets/Input/SEditableTextBox.h"
#include "Widgets/Input/SComboButton.h"
#include "Widgets/Input/SSlider.h"
#include "Widgets/Layout/SBorder.h"
#include "Widgets/Layout/SBox.h"
#include "Widgets/Layout/SScrollBox.h"
#include "Widgets/Layout/SScaleBox.h"
#include "Widgets/Layout/SWrapBox.h"
#include "Widgets/Layout/SUniformGridPanel.h"
#include "Widgets/Layout/SConstraintCanvas.h"
#include "Widgets/SBoxPanel.h"
#include "Widgets/SOverlay.h"
#include "Widgets/SNullWidget.h"
#include "Widgets/Text/STextBlock.h"

using J = nlohmann::ordered_json;
namespace {
FString Text(const std::string& S) { return OldWestDisplay::Text(FString(UTF8_TO_TCHAR(S.c_str()))); }
// Rules prose keeps its source citations in the data file for provenance;
// the in-game panel shows the explanation without the bracketed references.
static FString StripCitations(const FString& Value)
{
    FString Out; Out.Reserve(Value.Len());
    int32 I = 0;
    while (I < Value.Len())
    {
        if (Value[I] == TEXT('['))
        {
            const int32 Close = Value.Find(TEXT("]"), ESearchCase::CaseSensitive, ESearchDir::FromStart, I);
            if (Close > I + 1 && (Value[I + 1] == TEXT('R') || Value[I + 1] == TEXT('C') || Value[I + 1] == TEXT('D'))
                && I + 2 < Value.Len() && FChar::IsDigit(Value[I + 2]))
            {
                while (Out.Len() && Out[Out.Len() - 1] == TEXT(' ')) Out.RemoveAt(Out.Len() - 1);
                I = Close + 1;
                continue;
            }
        }
        Out.AppendChar(Value[I++]);
    }
    return Out;
}
const FLinearColor Sand(0.90f, 0.89f, 0.83f, 1.f);
const FLinearColor Pink(1.f, 0.22f, 0.42f, 1.f);
const FLinearColor Panel(0.012f, 0.020f, 0.026f, 0.96f);
const FButtonStyle& ActionButtonStyle()
{
    static const FButtonStyle Style=[] {
        FButtonStyle Result;
        Result.SetNormal(FSlateRoundedBoxBrush(FLinearColor(.035f,.052f,.061f,1),5.f,FLinearColor(.10f,.16f,.18f,1),1.f));
        Result.SetHovered(FSlateRoundedBoxBrush(FLinearColor(.065f,.13f,.14f,1),5.f,FLinearColor(.20f,.60f,.55f,1),1.f));
        Result.SetPressed(FSlateRoundedBoxBrush(FLinearColor(.035f,.09f,.10f,1),5.f,FLinearColor(.25f,.78f,.69f,1),1.f));
        Result.SetDisabled(FSlateRoundedBoxBrush(FLinearColor(.025f,.032f,.036f,.8f),5.f));
        return Result;
    }();
    return Style;
}
}

void SOldWestHUD::Construct(const FArguments& Arguments)
{
    Owner = Arguments._Owner;
    if (Owner.IsValid()) if (const UOldWestGameInstance* GI = Cast<UOldWestGameInstance>(Owner->GetGameInstance()))
        if (!GI->LastAddress.IsEmpty()) Address = GI->LastAddress;
    FString Source;
    FFileHelper::LoadFileToString(Source, *(FPaths::ProjectContentDir() / TEXT("Data/cards.json")));
    try { Catalog = J::parse(TCHAR_TO_UTF8(*Source)); } catch (const std::exception&) { Catalog = {{"cards", J::array()}}; }
    FString HelpSource;
    FFileHelper::LoadFileToString(HelpSource,*(FPaths::ProjectContentDir()/TEXT("Data/rules-help.json")));
    try {RulesContent=J::parse(TCHAR_TO_UTF8(*HelpSource));}catch(const std::exception&){RulesContent=J::object();}

    static const FSlateRoundedBoxBrush HoverBackground(FLinearColor(.012f,.022f,.027f,1.f),5.f,FLinearColor(.20f,.44f,.43f,1.f),1.f);
    // One logical canvas keeps the whole HUD visible at both 720p and 1080p.
    // The open middle remains transparent over the actual 3D battlefield.
    ChildSlot[SNew(SScaleBox).Stretch(EStretch::ScaleToFit).StretchDirection(EStretchDirection::Both)
        [SNew(SBox).WidthOverride(1920.f).HeightOverride(1080.f).Padding(28.f)
            [SNew(SOverlay)
                + SOverlay::Slot()[SAssignNew(Root, SVerticalBox).Visibility_Lambda([this]() {
                    return Owner.IsValid()&&Owner->IsCinematicBusy()&&!SettingsOpen&&!HelpOpen?EVisibility::Hidden:EVisibility::Visible;
                })]
                + SOverlay::Slot()[SAssignNew(HoverCanvas,SConstraintCanvas).Visibility(EVisibility::HitTestInvisible)]
                // Keep Skip below the header so revealing it cannot put Leave under the cursor.
                + SOverlay::Slot().HAlign(HAlign_Right).VAlign(VAlign_Top).Padding(0,90,8,0)
                [SNew(SBox).Visibility_Lambda([this]() { return Owner.IsValid() && Owner->IsCinematicBusy() && !SettingsOpen && !HelpOpen
                    ? EVisibility::Visible : EVisibility::Collapsed; })
                    [Button(TEXT("SKIP"),[this](){if(Owner.IsValid())Owner->SkipCinematics();},TEXT("Return to the battle immediately"),true,true)]]
                + SOverlay::Slot().HAlign(HAlign_Center).VAlign(VAlign_Bottom).Padding(0, 0, 0, 28)
                [SNew(SBox).MinDesiredWidth(600.f).MaxDesiredWidth(1100.f).Visibility_Lambda([this]() {
                    return Owner.IsValid() && Owner->IsCinematicBusy() && !SettingsOpen && !HelpOpen ? EVisibility::Visible : EVisibility::Collapsed;
                })[SNew(SBorder).BorderImage(FCoreStyle::Get().GetBrush("WhiteBrush")).BorderBackgroundColor(Panel).Padding(FMargin(24, 14))
                    [SNew(STextBlock).Text_Lambda([this]() { return FText::FromString(Owner.IsValid() ? Owner->GetCinematicCaption() : FString()); })
                        .Font(FCoreStyle::GetDefaultFontStyle("Regular", 22)).ColorAndOpacity(Sand)
                        .Justification(ETextJustify::Center).WrapTextAt(1052.f).AutoWrapText(true)]]]]]];
    HoverCanvas->AddSlot().Anchors(FAnchors(0,0)).Alignment(FVector2D::ZeroVector).AutoSize(true).Offset_Lambda([this]() { return FMargin(WorldHoverPosition.X,WorldHoverPosition.Y,0,0); })
        [SAssignNew(WorldHoverBox,SBox).WidthOverride(304).Visibility_Lambda([this]() { return BattlefieldTextVisible && WorldHoverVisible && SceneControlsVisible() && !SettingsOpen && !HelpOpen ? EVisibility::HitTestInvisible : EVisibility::Collapsed; })
            [SNew(SBorder).BorderImage(&HoverBackground).Padding(10)
                [SNew(STextBlock).Text_Lambda([this]() { return FText::FromString(WorldHoverText); })
                    .Font(FCoreStyle::GetDefaultFontStyle("Regular",12)).ColorAndOpacity(Sand).WrapTextAt(284)]]];
    Rebuild();
}
void SOldWestHUD::Tick(const FGeometry& Geometry, const double CurrentTime, const float DeltaTime)
{
    SCompoundWidget::Tick(Geometry, CurrentTime, DeltaTime);
    UpdateWorldHover(CurrentTime);
    UpdatePunkShelter();
    if(Staging.IsValid())Staging->SetTextVisible(BattlefieldTextVisible&&SceneControlsVisible());
    if(FrameFieldPending&&Owner.IsValid()&&!Owner->IsCinematicBusy()) {
        FrameFieldPending=false;
        if(!BattlePlanOpen)Owner->ResetBattlefieldCamera();
    }
    if (FOldWestPreferences* Settings = Preferences()) if (SeenPreferencesGeneration != Settings->Generation())
    {
        SeenPreferencesGeneration = Settings->Generation();
        SettingsDraft = Settings->Read(Owner.IsValid() ? Owner->GetWorld() : nullptr);
        if (Settings->IsPending()) { SettingsOpen = true; HelpOpen = false; }
        Dirty = true;
    }
    if (DraggedCard != INDEX_NONE && Owner.IsValid())
    {
        try { const J Current = J::parse(TCHAR_TO_UTF8(*Owner->GetPresentationSnapshot()));
            if (Current["view"].value("revision", -1) != DragRevision || Text(Current.value("match_id", std::string())) != DragMatch) EndDeployment(); }
        catch (const std::exception&) { EndDeployment(); }
    }
    if(DraggedCard!=INDEX_NONE&&DragKeepsPanels&&FSlateApplication::Get().IsDragDropping()) {
        const FVector2D Pointer=GetCachedGeometry().LocalToAbsolute(DragPointer);
        if(auto Scroll=BattleDropScroll.Pin()) {
            // The edge can be over a clipped child or the scroll gutter, so
            // scrolling uses the visible viewport, not a descendant hit path.
            bool Visible=false;
            for(const auto& Dock:DockPanels)if(Dock.IsValid()&&Dock->GetPanelId()==TEXT("master")&&Dock->GetVisibility().IsVisible()) {
                const auto* State=PanelStates.Find(TEXT("master"));
                Visible=State&&State->IsValid()&&!(*State)->bCollapsed;
            }
            const auto& SG=Scroll->GetCachedGeometry();
            if(Visible&&SG.IsUnderLocation(Pointer)) {
                const float Y=SG.AbsoluteToLocal(Pointer).Y,Height=SG.GetLocalSize().Y;
                const float Direction=Y<24.f?-1.f:Y>Height-24.f?1.f:0.f;
                const float Before=Scroll->GetScrollOffset();
                const float After=FMath::Clamp(Before+Direction*360.f*DeltaTime,0.f,Scroll->GetScrollOffsetOfEnd());
                if(After!=Before) {
                    Scroll->SetScrollOffset(After);
                    // Let Slate rebuild its hit grid before refreshing the drop.
                    // Slate schedules synthetic cursor moves while the viewport is active.
                }
            }
        }
        // OnDragOver owns hit testing. Re-querying during widget Tick sees a
        // partially rebuilt hit grid and erases a stationary panel highlight.
    }
    if (Owner.IsValid() && (Dirty || SeenGeneration != Owner->GetViewGeneration()) && DraggedCard == INDEX_NONE && !PanelGestureActive())
    {
        Rebuild();
        // Tick runs after Slate's normal prepass. New widgets otherwise keep
        // their default visible attributes for their first paint, flashing the
        // dashboard over the opening action frame. Lay out this new subtree
        // now; unchanged frames retain the ordinary Slate update path.
        MarkPrepassAsDirty();
        SlatePrepass(GetPrepassLayoutScaleMultiplier());
    }
}
void SOldWestHUD::DismissChoiceView()
{
    if (!LeaveConfirmationMatch.IsEmpty()) { LeaveConfirmationMatch.Reset(); Dirty=true; return; }
    // Escape releases only this optional close view. It is not cinematic Skip
    // or an accepted rule choice, and must not steal a panel/drag cancellation.
    if (!Owner.IsValid() || SettingsOpen || HelpOpen || PanelGestureActive() || DraggedCard != INDEX_NONE) return;
    if (WarRoomOpen) { WarRoomOpen=false;Dirty=true; }
    else if (OverviewOpen) SetBattleOverview(false);
    else if (Owner->IsAnalysisChoiceFramed()) Owner->SetAnalysisChoiceFramed(false);
}

bool SOldWestHUD::SceneControlsVisible() const
{
    return !Owner.IsValid() || !Owner->IsCinematicBusy();
}
void SOldWestHUD::CardActions(int32 CardId, FVector2D Position)
{
    if (!Owner.IsValid() || !SceneControlsVisible() || SettingsOpen || HelpOpen) return;
    J Data;
    try { Data=J::parse(TCHAR_TO_UTF8(*Owner->GetPresentationSnapshot())); } catch (const std::exception&) { return; }
    if (!Data.contains("actions") || Data.value("connected",0)!=2) return;
    FMenuBuilder Menu(true, nullptr);
    const int32 Revision=Data["view"].value("revision",-1);
    const FString Match=Text(Data.value("match_id",std::string()));
    const TWeakPtr<SOldWestHUD> Weak=SharedThis(this);
    J SelectedCard=J::object();
    for(const auto& Player:Data["view"].value("players",J::array()))
        for(const auto& Column:Player.value("columns",J::array()))for(const auto& Card:Column)
            if(Card.value("id",0)==CardId)SelectedCard=Card;
    int32 Count=0;
#if !UE_BUILD_SHIPPING
    LastContextActions=J::array();
#endif
    for (const auto& Action:Data["actions"]) {
        const J Command=Action["command"];
        if(!oldwest::FieldActionMatches(Action,CardId))continue;
        FString Caption=Text(Action.value("label",std::string()));
        if (Action.value("cost",0)>0) Caption+=FString::Printf(TEXT(" · %d whiskey"),Action.value("cost",0));
        if(Command.value("type",std::string())=="activate"&&Command.value("source",0)==CardId)
            for(const auto& Ability:SelectedCard.value("public_abilities",J::array()))
                if(Ability.value("index",-1)==Command.value("ability",-2)&&Ability.contains("activation_label"))
                    Caption=Text(Ability["activation_label"]);
#if !UE_BUILD_SHIPPING
        LastContextActions.push_back(Action);
#endif
        Menu.AddMenuEntry(FText::FromString(Caption),FText(),FSlateIcon(),FUIAction(FExecuteAction::CreateLambda([Weak,Command,Revision,Match]() {
            if (auto HUD=Weak.Pin()) if (HUD->Owner.IsValid()) {
                HUD->Owner->ServerSubmit(Text(Command.dump()),Revision,Match);
                HUD->Dirty=true;
            }
        })));
        ++Count;
    }
    if (CardId>0) Menu.AddMenuEntry(FText::FromString(TEXT("Inspect card")),FText(),FSlateIcon(),FUIAction(FExecuteAction::CreateLambda([Weak,CardId]() {
        if (auto HUD=Weak.Pin()) HUD->InspectVisibleCard(CardId);
    })));
    for(const auto& Status:SelectedCard.value("ability_availability",J::array()))if(!Status.value("available",false)) {
        FString Caption=TEXT("Ability unavailable");
        for(const auto& Ability:SelectedCard.value("public_abilities",J::array()))if(Ability["index"]==Status["index"])
            Caption=Text(Ability.value("activation_label",Ability.value("effect",std::string("Ability unavailable"))));
        const FString Reason=Text(Status.value("reason",std::string("Unavailable")));
        Menu.AddWidget(SNew(SBox).MaxDesiredWidth(440)[SNew(STextBlock)
            .Text(FText::FromString(Caption+TEXT("\n")+Reason)).AutoWrapText(true)
            .ColorAndOpacity(Sand)],FText(),true);
        ++Count;
    }
    if (!Count) Menu.AddMenuEntry(FText::FromString(TEXT("No legal moves right now")),FText(),FSlateIcon(),FUIAction(FExecuteAction(),FCanExecuteAction::CreateLambda([](){return false;})));
    const auto MenuWidget=Menu.MakeWidget();
#if !UE_BUILD_SHIPPING
    LastContextWidget=MenuWidget;
#endif
    FSlateApplication::Get().PushMenu(SharedThis(this),FWidgetPath(),MenuWidget,Position,FPopupTransitionEffect(FPopupTransitionEffect::ContextMenu));
}
void SOldWestHUD::ClickCard(int32 CardId)
{
    if (!Owner.IsValid()) return;
    J Data;
    try { Data=J::parse(TCHAR_TO_UTF8(*Owner->GetPresentationSnapshot())); } catch (const std::exception&) { return; }
    J Choices=J::array();
    for (const auto& A:Data["actions"]) if(A.value("category",std::string())=="choice" && A.value("target",0)==CardId) Choices.push_back(A);
    if (Choices.size()==1) { Send(Choices[0]["command"]); return; }
    if (Choices.size()>1) { CardActions(CardId,FSlateApplication::Get().GetCursorPos()); return; }
    if(CardId==-3003){WarRoomOpen=true;InspectedCard=0;Dirty=true;return;}
    InspectVisibleCard(CardId);
}
FReply SOldWestHUD::OnDragDetected(const FGeometry&, const FPointerEvent&)
{
    const int32 Card=PressedWorldCard; PressedWorldCard=INDEX_NONE;
    if (Card!=INDEX_NONE) if (auto Drag=BeginDeployment(Card))
        return FReply::Handled().ReleaseMouseCapture().BeginDragDrop(Drag.ToSharedRef());
    return FReply::Handled().ReleaseMouseCapture();
}
FReply SOldWestHUD::OnPreviewMouseButtonDown(const FGeometry&,const FPointerEvent& Event)
{
    if(WarRoomOpen&&Event.GetEffectingButton()==EKeys::LeftMouseButton) {
        const auto Board=WarRoomSurface.Pin();
        if(!Board.IsValid()||!Board->GetCachedGeometry().IsUnderLocation(Event.GetScreenSpacePosition())) {
            WarRoomOpen=false;Dirty=true;
        }
    }
    return FReply::Unhandled();
}
FReply SOldWestHUD::OnMouseButtonDown(const FGeometry& Geometry, const FPointerEvent& MouseEvent)
{
    if (DraggedCard==INDEX_NONE && OverBattlefield(MouseEvent.GetScreenSpacePosition())) {
        WorldPressPosition=MouseEvent.GetScreenSpacePosition(); CameraMoved=false;
        int32 W=0,H=0;Owner->GetViewportSize(W,H);
        const FVector2D Size=Geometry.GetLocalSize(),Local=Geometry.AbsoluteToLocal(MouseEvent.GetScreenSpacePosition());
        PressedWorldCard=INDEX_NONE;
        for(const auto& Label:BattlefieldLabels()) {
            if(Label.value("decorative",false))continue;
            const auto& R=Label["rect"];
            if(Local.X>=R[0].get<double>()&&Local.X<=R[2].get<double>()&&Local.Y>=R[1].get<double>()&&Local.Y<=R[3].get<double>()) {
                PressedWorldCard=Label["id"];break;
            }
        }
        if(PressedWorldCard==INDEX_NONE&&PunkShelter.IsValid())PressedWorldCard=PunkShelter->Pick(Owner.Get(),Local*FVector2D(W/FMath::Max(1.,Size.X),H/FMath::Max(1.,Size.Y)));
        if(PressedWorldCard==INDEX_NONE)PressedWorldCard=OldWestWorldInteraction::PickVisibleUnitAtScreen(Owner.Get(),Local*FVector2D(W/FMath::Max(1.,Size.X),H/FMath::Max(1.,Size.Y)));
        if (MouseEvent.GetEffectingButton()==EKeys::RightMouseButton || MouseEvent.GetEffectingButton()==EKeys::MiddleMouseButton) {
            CameraDrag=MouseEvent.GetEffectingButton(); return FReply::Handled().CaptureMouse(SharedThis(this));
        }
        if (MouseEvent.GetEffectingButton()==EKeys::LeftMouseButton && PressedWorldCard!=INDEX_NONE)
            return FReply::Handled().CaptureMouse(SharedThis(this)).DetectDrag(SharedThis(this),EKeys::LeftMouseButton);
    }
    if(MouseEvent.GetEffectingButton()==EKeys::LeftMouseButton && OverBattlefield(MouseEvent.GetScreenSpacePosition())) {
        InspectedCard=0;SelectedSource=0;WarRoomOpen=false;Dirty=true;return FReply::Handled();
    }
    return SCompoundWidget::OnMouseButtonDown(Geometry, MouseEvent);
}
bool SOldWestHUD::OverBattlefield(const FVector2D& ScreenPosition) const
{
    if (!Owner.IsValid() || SettingsOpen || HelpOpen || !SceneControlsVisible() || !SceneHitArea.IsValid()) return false;
    const FGeometry& Scene = SceneHitArea->GetCachedGeometry();
    for(const auto& Surface:FieldSurfaces)if(auto Widget=Surface.Pin())
        if(Widget->GetVisibility().IsVisible()&&Widget->GetCachedGeometry().IsUnderLocation(ScreenPosition))return false;
    if (DraggedCard == INDEX_NONE || (DragKeepsPanels && BattlePlanOpen))
    {
        for(const auto& Dock:DockPanels) if(Dock.IsValid() && Dock->GetVisibility().IsVisible()
            && Dock->GetCachedGeometry().IsUnderLocation(ScreenPosition)) return false;
        return Scene.IsUnderLocation(ScreenPosition);
    }
    const FVector2D P = GetCachedGeometry().AbsoluteToLocal(ScreenPosition);
    const FVector2D Top = GetCachedGeometry().AbsoluteToLocal(Scene.LocalToAbsolute(FVector2D::ZeroVector));
    const FVector2D Size = GetCachedGeometry().GetLocalSize();
    // The hand and side panels clear during a drag. Near-side placements can
    // therefore be reached at their actual world position below the old hand.
    return P.X >= 0 && P.X < Size.X && P.Y >= Top.Y && P.Y < Size.Y;
}
FReply SOldWestHUD::OnMouseButtonUp(const FGeometry&, const FPointerEvent& Event)
{
    if (CameraDrag.IsValid() && Event.GetEffectingButton() == CameraDrag)
    {
        const bool Menu=CameraDrag==EKeys::RightMouseButton && !CameraMoved;
        CameraDrag=FKey();
        if(Menu) CardActions(PressedWorldCard,Event.GetScreenSpacePosition());
        PressedWorldCard=INDEX_NONE;
        return FReply::Handled().ReleaseMouseCapture();
    }
    if(Event.GetEffectingButton()==EKeys::LeftMouseButton && HasMouseCapture()) {
        const int32 Card=PressedWorldCard; PressedWorldCard=INDEX_NONE;
        if(Card!=INDEX_NONE) ClickCard(Card);
        return FReply::Handled().ReleaseMouseCapture();
    }
    return FReply::Unhandled();
}
FReply SOldWestHUD::OnMouseMove(const FGeometry&, const FPointerEvent& Event)
{
    if (!CameraDrag.IsValid() || !HasMouseCapture() || !Owner.IsValid()) return FReply::Unhandled();
    if(FVector2D::Distance(WorldPressPosition,Event.GetScreenSpacePosition())>5.f) CameraMoved=true;
    if(!CameraMoved) return FReply::Handled();
    const FVector2D D = Event.GetCursorDelta();
    const bool Elevate = Event.IsControlDown();
    const bool Pan = Elevate || CameraDrag == EKeys::MiddleMouseButton || Event.IsShiftDown();
    Owner->NavigateBattlefieldCamera(Pan ? 0.f : D.X, Pan ? 0.f : D.Y, Pan ? D.X : 0.f, Pan && !Elevate ? D.Y : 0.f, 0.f, Elevate ? -D.Y : 0.f);
    return FReply::Handled();
}
FReply SOldWestHUD::OnMouseWheel(const FGeometry&, const FPointerEvent& Event)
{
    if (!OverBattlefield(Event.GetScreenSpacePosition()) || DraggedCard != INDEX_NONE) return FReply::Unhandled();
    Owner->NavigateBattlefieldCamera(0, 0, 0, 0, Event.GetWheelDelta());
    return FReply::Handled();
}
TSharedPtr<FDragDropOperation> SOldWestHUD::BeginDeployment(int32 CardId)
{
    EndDeployment();
    if (!Owner.IsValid() || SettingsOpen || HelpOpen || !SceneControlsVisible()) return nullptr;
    J Data;
    try { Data = J::parse(TCHAR_TO_UTF8(*Owner->GetPresentationSnapshot())); } catch (const std::exception&) { return nullptr; }
    if (!Data.value("hosted", false) || Data.value("connected", 0) != 2) return nullptr;
    const J& View = Data["view"];
    const int32 Seat = Data["seat"];
    const int32 WaterCount=oldwest::WaterBundleCount(CardId);
    if(WaterCount>View["players"][Seat].value("water",0))return nullptr;
    const bool WaterSource=CardId==-3002||CardId==-4000||WaterCount>0;
    const bool Supply=AOldWestPunkShelter::IsToken(CardId);
    if(Supply&&(!PunkShelter.IsValid()||!PunkShelter->CanDrag(CardId)))return nullptr;
    DragName = (CardId == 0 || Supply) ? TEXT("DRIFTER") : TEXT("DEPLOY");
    for (const auto& Card : View["players"][Seat]["hand"])
        if (Card.value("id", -1) == CardId) DragName = Text(Card.value("name", std::string()));
    for (const auto& Player : View["players"]) for (const auto& Column : Player["columns"]) for (const auto& Card : Column)
        if (Card.value("id", -1) == CardId) DragName = Text(Card.value("name", std::string("Punk")));
    if(WaterSource){DragName=TEXT("WHISKEY");DragKeepsPanels=true;}
    if(WaterCount)DragName=FString::Printf(TEXT("%d WHISKEY"),WaterCount);
    J Actions=Data["actions"];
    for(const auto& Action:Data["actions"])for(const auto& Gesture:Action.value("gestures",J::array()))
        for(const auto& Card:Gesture["cards"])if(Card==CardId) { Actions.push_back(Gesture); break; }
    for (const auto& Action : Actions)
    {
        const J& Command = Action["command"];
        const bool Gesture=Action.contains("cards");
        const bool SpatialChoice = Action.contains("placement") && ((Supply&&Action["placement"].value("punk",false)) || Action["placement"].value("card", -1) == CardId ||
            (Action["placement"].value("punk",false) && Action.value("drag_source",-1)==CardId));
        const bool HandPlay = Command.value("type", std::string()) == "play" && Command.value("card", -1) == CardId;
        if (!SpatialChoice && !HandPlay && !Gesture)
        {
            const std::string Type=Command.value("type",std::string());
            const int32 Source=Command.value("source",Command.value("card",0));
            if(Supply||(!(WaterSource&&Type=="activate")&&!oldwest::FieldActionMatches(Action,CardId)))continue;
            FDropTarget Target;Target.Command=Command;
            Target.Label=Text(Action.value("label",std::string()));
            if(Action.value("cost",0)>0)Target.Label+=FString::Printf(TEXT(" · %d whiskey"),Action.value("cost",0));
            if(Type=="junk"&&CardId>0) {
                Target.World=AOldWestStaging::UtilityPosition(Seat,4);Target.TargetCard=-3004;
                for(const auto& HandCard:View["players"][Seat]["hand"])if(HandCard.value("id",0)==CardId) {
                    const J* Def=CardDefinition(HandCard.value("card_id",std::string()));
                    if(Def&&Def->value("junk",std::string())=="draw") {
                        auto DrawTarget=Target;DrawTarget.World=AOldWestStaging::UtilityPosition(Seat,0);
                        DrawTarget.TargetCard=-3000;DrawTarget.World.Z+=45.f;
                        DropTargets.Add(MoveTemp(DrawTarget));
                    }
                }
            }
            else if(Type=="draw"){Target.World=AOldWestStaging::UtilityPosition(Seat,0);Target.TargetCard=-3000;}
            else if(Type=="end_turn")Target.World=AOldWestStaging::UtilityPosition(Seat,1);
            else if(Type=="silo"){Target.World=AOldWestStaging::UtilityPosition(Seat,2);Target.TargetCard=-3002;}
            else
            {
                // Targetless choices belong at Bunkhouse; abilities belong
                // to their source, and targeted effects to the actual card.
                Target.World=AOldWestStaging::UtilityPosition(Seat,3);Target.TargetCard=-3003;
                const int32 TargetId=Action.value("target",Source);
                if(TargetId>0)for(TActorIterator<AOldWestUnit> It(Owner->GetWorld());It;++It)
                    if(It->EntityId==TargetId&&!It->IsPreviewOnly()&&!It->IsHidden())
                    {Target.World=It->GetSelectionBounds().GetCenter();Target.TargetCard=TargetId;break;}
            }
            Target.World.Z+=45.f;DropTargets.Add(MoveTemp(Target));
            continue;
        }
        FDropTarget Target;
        Target.Command = Command;
        if (Gesture) DragKeepsPanels=true;
        if (Gesture && Action.contains("target")) {
            Target.TargetCard=Action["target"];
            bool Found=false;
            for(TActorIterator<AOldWestUnit> It(Owner->GetWorld());It;++It)
                if(It->EntityId==Target.TargetCard&&!It->IsPreviewOnly()&&!It->IsHidden()) {
                    Target.World=It->GetSelectionBounds().GetCenter();Found=true;break;
                }
            if(!Found)continue;
            Target.Label=Text(Action.value("label",std::string())).Replace(TEXT("Sacrifice at "),TEXT("Sacrifice\n"));
        }
        else if (Action.contains("event_slot"))
        {
            DragKeepsPanels=true;
            const int32 EventSlot = Action.value("event_slot", 1);
            Target.Side=Seat; Target.EventSlot=EventSlot;
            Target.World = AOldWestBattlefield::EventPosition(Seat, EventSlot);
            Target.Label = EventSlot < 0 ? TEXT("0 · PLAY NOW") : FString::Printf(TEXT("TROUBLE · %d"), EventSlot+1);
        }
        else
        {
            const J& Placement = Action.contains("placement") ? Action["placement"] : Command;
            const int32 Side = Placement.value("player", Seat), Column = Placement.value("column", -1);
            if (Side < 0 || Side > 1 || Column < 0 || Column > 2) continue;
            TArray<J> Cards;
            FString ReplacedName;
            for (const auto& C : View["players"][Side]["columns"][Column])
            {
                if (C.value("id", -1) == Placement.value("replace", -2)) { ReplacedName = Text(C.value("name", std::string())); continue; }
                if (Placement.value("moving", false) && C.value("id", -1) == CardId) { DragName = Text(C.value("name", std::string())); continue; }
                Cards.Add(C);
            }
            const int32 At = FMath::Clamp(Placement.value("position", 0), 0, Cards.Num());
            Cards.Insert(J{{"id", -12345}, {"type", "person"}}, At);
            int32 CampIndex = INDEX_NONE;
            for (int32 I = 0; I < Cards.Num(); ++I) if (Cards[I].value("type", std::string()) == "camp") { CampIndex = I; break; }
            if (CampIndex != INDEX_NONE && !Cards[CampIndex].value("destroyed", false))
            {
                const int32 Advance = Cards[CampIndex].value("advance", 0);
                if (Advance == 2 || (Advance == 1 && Cards.Num() == 3))
                { J Camp = Cards[CampIndex]; Cards.RemoveAt(CampIndex); Cards.Insert(Camp, Advance == 2 ? 0 : 1); }
            }
            int32 Ghost = 0, CampRow = 2;
            CampIndex = INDEX_NONE;
            for (int32 I = 0; I < Cards.Num(); ++I)
            {
                if (Cards[I].value("id", 0) == -12345) Ghost = I;
                if (Cards[I].value("type", std::string()) == "camp") { CampIndex = I; CampRow = 2 - Cards[I].value("advance", 0); }
            }
            const int32 Row = Placement.value("row", CampIndex == INDEX_NONE ? 3 - Cards.Num() + Ghost : CampRow + Ghost - CampIndex);
            Target.Side=Side; Target.Column=Column; Target.Row=Row;
            Target.World = AOldWestBattlefield::DeploymentPosition(Side, Column, Row);
            int32 PeopleBefore=0,PeopleCount=0;
            for(int32 I=0;I<Cards.Num();++I)if(Cards[I].value("type",std::string())=="person") {++PeopleCount;if(I<Ghost)++PeopleBefore;}
            const FString Position = PeopleBefore==0?TEXT("Front"):PeopleBefore==PeopleCount-1?TEXT("Behind"):TEXT("Middle");
            Target.Label = FString::Printf(TEXT("Lane %d · %s"), Column + 1, *Position);
            if (!ReplacedName.IsEmpty()) Target.Label += TEXT("\nReplace ") + ReplacedName;
        }
        if(Gesture && !Action.contains("target")) Target.Label+=TEXT("\n")+Text(Action.value("label",std::string()));
        if(Gesture) Target.Label+=FString::Printf(TEXT(" · %d whiskey"),Action.value("cost",0));
        FHitResult Ground;
        FCollisionQueryParams Query(SCENE_QUERY_STAT(OldWestDropGround), true);
        if (Owner->GetWorld()->LineTraceSingleByChannel(Ground, Target.World + FVector(0,0,500), Target.World - FVector(0,0,600), ECC_Visibility, Query))
            Target.World.Z = Ground.ImpactPoint.Z;
        Target.World.Z += 45.f;
        DropTargets.Add(MoveTemp(Target));
    }
    // A physical destination is one drop zone. Multiple legal commands at
    // that destination are selected explicitly after release.
    for(int32 I=0;I<DropTargets.Num();++I) {
        auto& Destination=DropTargets[I];
        const auto NeedsConfirmation=[&View](const FDropTarget& T) {
            const FString Prompt=View["choice"].is_object()?Text(View["choice"].value("prompt",std::string())):FString();
            return T.Command.value("kind",std::string())=="sacrifice"||T.Label.Contains(TEXT("Replace"))||T.Label.Contains(TEXT("Sacrifice"))||
                T.Command.dump().find("\"replace\"")!=std::string::npos||
                (Prompt.Contains(TEXT("sacrifice"))&&!T.Label.Equals(TEXT("Skip"),ESearchCase::IgnoreCase));
        };
        Destination.Alternatives.push_back({{"command",Destination.Command},{"label",std::string(TCHAR_TO_UTF8(*Destination.Label))},{"confirm",NeedsConfirmation(Destination)}});
        for(int32 K=DropTargets.Num()-1;K>I;--K) {
            const auto& Other=DropTargets[K];
            const bool SameCard=Destination.TargetCard!=0&&Destination.TargetCard==Other.TargetCard;
            const bool SameSlot=Destination.TargetCard==0&&Other.TargetCard==0&&Destination.Side==Other.Side&&
                Destination.Column==Other.Column&&Destination.Row==Other.Row&&Destination.EventSlot==Other.EventSlot&&
                FVector::DistSquaredXY(Destination.World,Other.World)<100.f;
            if(SameCard||SameSlot) {
                Destination.Alternatives.push_back({{"command",Other.Command},{"label",std::string(TCHAR_TO_UTF8(*Other.Label))},{"confirm",NeedsConfirmation(Other)}});
                DropTargets.RemoveAt(K);
            }
        }
        if(Destination.Alternatives.size()>1)Destination.Label=TEXT("CHOOSE ACTION · ")+FString::FromInt(Destination.Alternatives.size())+TEXT(" options");
    }
    // Keep unavailable abilities inspectable without inventing a legal command.
    if(WaterSource)for(const auto& Column:View["players"][Seat]["columns"])for(const auto& Card:Column) {
        const int32 Id=Card.value("id",0);
        bool HasTarget=false;
        for(const auto& Target:DropTargets)if(Target.TargetCard==Id){HasTarget=true;break;}
        if(HasTarget||Card.value("public_abilities",J::array()).empty())continue;
        FString Details=CardGlanceText(Card);
        for(TActorIterator<AOldWestUnit> It(Owner->GetWorld());It;++It)
            if(It->EntityId==Id&&!It->IsPreviewOnly()&&!It->IsHidden()) {
                FDropTarget Target;Target.TargetCard=Id;Target.World=It->GetSelectionBounds().GetCenter()+FVector(0,0,45);
                Target.Label=Text(Card.value("name",std::string()))+TEXT(" · Ability unavailable");
                for(const auto& Status:Card.value("ability_availability",J::array())) {
                    const std::string Reason=Status.value("reason",std::string());
                    if(Reason.rfind("Not enough water",0)==0){Target.Label=Text(Reason);break;}
                }
                Target.BlockedReason=Details;DropTargets.Add(MoveTemp(Target));break;
            }
    }
    if (DropTargets.IsEmpty()) { EndDeployment(); Owner->ClientNotice(TEXT("No legal action is available from this source. Check whiskey, readiness, pending choices, and open spaces.")); return nullptr; }
    // Keep formation cards reachable while dragging a deployed person, even
    // for a previously activated movement choice. Hand events keep their
    // countdown/Play Now panel destinations reachable as well.
    for(const auto& Player:View["players"])for(const auto& Column:Player["columns"])for(const auto& Card:Column)
        if(Card.value("id",-1)==CardId)DragKeepsPanels=true;
    DragPointer=GetCachedGeometry().AbsoluteToLocal(FSlateApplication::Get().GetCursorPos());
    if(Supply){PunkShelter->BeginDrag(CardId);DragKeepsPanels=true;}
    DraggedCard = CardId;
    DragRevision = View.value("revision", -1);
    DragMatch = Text(Data.value("match_id", std::string()));
    const TWeakPtr<SOldWestHUD> Weak = SharedThis(this);
    J PreviewCard={{"name",std::string(TCHAR_TO_UTF8(*DragName))},{"punk",CardId==0||Supply},{"type","person"}};
    for(const auto& Card:View["players"][Seat]["hand"])if(Card.value("id",-1)==CardId)PreviewCard=Card;
    for(const auto& Player:View["players"])for(const auto& Column:Player["columns"])for(const auto& Card:Column)
        if(Card.value("id",-1)==CardId)PreviewCard=Card;
    for(const auto& Player:View["players"])for(const auto& Card:Player["queue"])
        if(!Card.is_null()&&Card.value("id",-1)==CardId){PreviewCard=Card;DragName=Text(Card.value("name",std::string()));}
    TSharedRef<SWidget> Preview=SNullWidget::NullWidget;
    if(BattlePlanOpen&&!Supply) Preview=SNew(SBox).WidthOverride(176)
        .Visibility_Lambda([Weak](){const auto HUD=Weak.Pin();return HUD.IsValid()&&HUD->DraggedCard!=INDEX_NONE?EVisibility::HitTestInvisible:EVisibility::Collapsed;})
        [SNew(SBorder).BorderImage(FCoreStyle::Get().GetBrush("WhiteBrush"))
            .BorderBackgroundColor_Lambda([Weak](){const auto HUD=Weak.Pin();return HUD.IsValid()&&HUD->HoveredDrop!=INDEX_NONE?FLinearColor(.14f,.85f,.65f,1):FLinearColor(.28f,.42f,.44f,1);}).Padding(3)
            [SNew(SVerticalBox)
                +SVerticalBox::Slot().AutoHeight()[AnimatedCard(PreviewCard,100,true)]
                +SVerticalBox::Slot().AutoHeight().Padding(6)
                [SNew(STextBlock).Text_Lambda([Weak](){const auto HUD=Weak.Pin();return FText::FromString(HUD.IsValid()&&HUD->HoveredDrop!=INDEX_NONE?TEXT("RELEASE TO EXECUTE"):TEXT("DRAG TO A LIT TARGET"));})
                    .Font(FCoreStyle::GetDefaultFontStyle("Bold",11)).ColorAndOpacity(FLinearColor::White)]]];
    // World interaction carries the actual hand model, never a portrait card.
    if(!BattlePlanOpen)
    {
        for(TActorIterator<AOldWestUnit> It(Owner->GetWorld());It;++It)
            if(It->EntityId==CardId&&(It->ActorHasTag(TEXT("OldWestHandStaging"))||It->ActorHasTag(TEXT("OldWestWaterBundle"))))
            {DraggedWorldPreview=*It;DragWorldStart=It->GetActorLocation();It->Tags.AddUnique(TEXT("OldWestDragPreview"));break;}
        Preview=SNullWidget::NullWidget;
    }
    if(Supply)Preview=SNullWidget::NullWidget;
    return FOldWestCardDrag::New(CardId, [Weak]() { if (auto HUD = Weak.Pin()) HUD->EndDeployment(); }, Preview,
        [Weak](){const auto HUD=Weak.Pin();return HUD.IsValid()&&HUD->DraggedCard!=INDEX_NONE;},
        [Weak](FVector2D P){
            if(const auto HUD=Weak.Pin()){
                const auto& G=HUD->GetCachedGeometry();
                const FVector2D Min=G.LocalToAbsolute(FVector2D::ZeroVector),Max=G.LocalToAbsolute(G.GetLocalSize());
                P.X=FMath::Clamp(P.X,Min.X,FMath::Max(Min.X,Max.X-184.));
                P.Y=FMath::Clamp(P.Y,Min.Y,FMath::Max(Min.Y,Max.Y-250.));
            }
            return P;
        });
}
void SOldWestHUD::EndDeployment()
{
    if(DraggedWorldPreview.IsValid()){DraggedWorldPreview->SetActorLocation(DragWorldStart);DraggedWorldPreview->Tags.Remove(TEXT("OldWestDragPreview"));}
    DraggedWorldPreview.Reset();
    if(PunkShelter.IsValid())PunkShelter->CancelDrag(DraggedCard);
    DraggedCard = INDEX_NONE; HoveredDrop = INDEX_NONE; HoveredPanelSurface=INDEX_NONE; DragKeepsPanels=false; DropTargets.Empty();
}
float SOldWestHUD::OverlayUnit() const
{
    // Overlay sizes are screen pixels, independent of UI canvas/DPI and zoom.
    return 1.f / FMath::Max(.1f, GetCachedGeometry().GetAccumulatedLayoutTransform().GetScale());
}
FSlateRect SOldWestHUD::BattlefieldRect() const
{
    int32 W=0,H=0;
    if (Owner.IsValid()) Owner->GetViewportSize(W,H);
    FIntRect Pixels(0,0,W,H);
    if (Owner.IsValid()) if (ULocalPlayer* Player=Owner->GetLocalPlayer())
        if (Player->ViewportClient && Player->ViewportClient->Viewport) {
            FSceneViewProjectionData Projection;
            if (Player->GetProjectionData(Player->ViewportClient->Viewport,Projection)) Pixels=Projection.GetConstrainedViewRect();
        }
    const FVector2D Local=GetCachedGeometry().GetLocalSize();
    const FVector2D Ratio(Local.X/FMath::Max(1,W),Local.Y/FMath::Max(1,H));
    const float Top=SceneHitArea.IsValid()?GetCachedGeometry().AbsoluteToLocal(
        SceneHitArea->GetCachedGeometry().LocalToAbsolute(FVector2D::ZeroVector)).Y:0.f;
    const float Bottom=SceneHitArea.IsValid()?GetCachedGeometry().AbsoluteToLocal(
        SceneHitArea->GetCachedGeometry().LocalToAbsolute(SceneHitArea->GetCachedGeometry().GetLocalSize())).Y:Local.Y;
    return FSlateRect(Pixels.Min.X*Ratio.X,FMath::Max(float(Pixels.Min.Y*Ratio.Y),Top),Pixels.Max.X*Ratio.X,
        FMath::Min(float(Pixels.Max.Y*Ratio.Y),Bottom));
}
bool SOldWestHUD::ProjectToHUD(const FVector& World, FVector2D& LocalPosition) const
{
    if (!Owner.IsValid() || !Owner->ProjectWorldLocationToScreen(World,LocalPosition)) return false;
    int32 W=0,H=0; Owner->GetViewportSize(W,H);
    if (W<=0||H<=0) return false;
    const FVector2D Size=GetCachedGeometry().GetLocalSize();
    LocalPosition*=FVector2D(Size.X/W,Size.Y/H);
    const FSlateRect Rect=BattlefieldRect();
    return LocalPosition.X>=Rect.Left&&LocalPosition.X<=Rect.Right&&LocalPosition.Y>=Rect.Top&&LocalPosition.Y<=Rect.Bottom;
}
void SOldWestHUD::LayoutDeployment() const
{
    const float U=OverlayUnit();
    const auto Font=FCoreStyle::GetDefaultFontStyle("Bold", FMath::Max(1,FMath::RoundToInt(16*U)));
    const auto Measure=FSlateApplication::Get().GetRenderer()->GetFontMeasureService();
    const FSlateRect Bounds=BattlefieldRect();
    TArray<FSlateRect> Occupied;
    TArray<TPair<const FDropTarget*,FVector2D>> PhysicalAnchors;
    for(const FDropTarget& Target:DropTargets) {
        FVector2D At;if(ProjectToHUD(Target.World,At))PhysicalAnchors.Emplace(&Target,At);
    }
    for (FDropTarget& Target:DropTargets) {
        FVector2D Anchor;
        Target.Visible=ProjectToHUD(Target.World,Anchor);
        if (!Target.Visible) continue;
        if(AOldWestPunkShelter::IsToken(DraggedCard))Anchor.Y-=70*U; // Keep the carried person visible below its landing label.
        // Wrap at a readable font size instead of shrinking whole action descriptions.
        Target.DisplayLabel.Empty();
        TArray<FString> Paragraphs; Target.Label.ParseIntoArrayLines(Paragraphs);
        const float MaxWidth=FMath::Max(80.f*U,FMath::Min(360.f*U,Bounds.Right-Bounds.Left-32.f*U));
        for(const FString& Paragraph:Paragraphs) {
            TArray<FString> Words; Paragraph.ParseIntoArray(Words,TEXT(" "),true);
            FString Line;
            for(const FString& Word:Words) {
                const FString Candidate=Line.IsEmpty()?Word:Line+TEXT(" ")+Word;
                if(!Line.IsEmpty()&&Measure->Measure(Candidate,Font).X>MaxWidth) {
                    if(!Target.DisplayLabel.IsEmpty())Target.DisplayLabel+=TEXT("\n");
                    Target.DisplayLabel+=Line; Line=Word;
                } else Line=Candidate;
            }
            if(!Target.DisplayLabel.IsEmpty())Target.DisplayLabel+=TEXT("\n");
            Target.DisplayLabel+=Line;
        }
        const FVector2D TextSize=Measure->Measure(Target.DisplayLabel,Font);
        Target.LabelSize=FVector2D(FMath::Max(160.f*U,TextSize.X+24.f*U),FMath::Max(48.f*U,TextSize.Y+20.f*U));
        const FVector2D Half=Target.LabelSize*.5f;
        const FVector2D Step=Target.LabelSize+FVector2D(8,8)*U;
        float Best=TNumericLimits<float>::Max();
        // All choices remain distinct. Share one layout for paint, hit testing
        // and telemetry; never select a different victim under another label.
        for (int32 Row=-8;Row<=8;++Row) for (int32 Col=-4;Col<=4;++Col) {
            FVector2D P=Anchor+FVector2D(Col*Step.X,Row*Step.Y);
            if (P.X-Half.X<Bounds.Left+4*U||P.X+Half.X>Bounds.Right-4*U||
                P.Y-Half.Y<Bounds.Top+40*U||P.Y+Half.Y>Bounds.Bottom-4*U) continue;
            bool Free=true;
            // A destination's text must never cover another physical landing
            // marker; otherwise a visible lane can activate a different action.
            for(const auto& Other:PhysicalAnchors)if(Other.Key!=&Target) {
                const FVector2D At=Other.Value;
                if(P.X+Half.X>At.X-24*U&&P.X-Half.X<At.X+24*U&&P.Y+Half.Y>At.Y-24*U&&P.Y-Half.Y<At.Y+24*U){Free=false;break;}
            }
            if(DragKeepsPanels)for(const auto& Dock:DockPanels)if(Dock.IsValid()&&Dock->GetVisibility().IsVisible()) {
                const auto& DG=Dock->GetCachedGeometry();
                const FVector2D A=GetCachedGeometry().AbsoluteToLocal(DG.LocalToAbsolute(FVector2D::ZeroVector));
                const FVector2D B=GetCachedGeometry().AbsoluteToLocal(DG.LocalToAbsolute(DG.GetLocalSize()));
                if(P.X+Half.X>A.X&&P.X-Half.X<B.X&&P.Y+Half.Y>A.Y&&P.Y-Half.Y<B.Y){Free=false;break;}
            }
            for (const FSlateRect& Q:Occupied) if (P.X+Half.X+8*U>Q.Left&&P.X-Half.X-8*U<Q.Right&&P.Y+Half.Y+8*U>Q.Top&&P.Y-Half.Y-8*U<Q.Bottom) {Free=false;break;}
            const float Distance=FVector2D::DistSquared(P,Anchor);
            if (Free&&Distance<Best) {Best=Distance;Target.Screen=P;}
        }
        Target.Visible=Best<TNumericLimits<float>::Max();
        if (Target.Visible) Occupied.Add(FSlateRect(Target.Screen.X-Half.X,Target.Screen.Y-Half.Y,Target.Screen.X+Half.X,Target.Screen.Y+Half.Y));
    }
}
bool SOldWestHUD::DropMatchesSurface(const FDropTarget& Target, const FPanelDropSurface& Surface) const
{
    if(Target.TargetCard>0)return Target.TargetCard==Surface.Card;
    if(Target.EventSlot!=-99)return Target.Side==Surface.Side && Target.EventSlot==Surface.EventSlot;
    return Target.Side==Surface.Side && Target.Column==Surface.Column && Target.Row==Surface.Row;
}
bool SOldWestHUD::UpdateDeployment(const FVector2D& ScreenPosition)
{
    if (DraggedCard==INDEX_NONE||!Owner.IsValid()) return false;
    DragPointer=GetCachedGeometry().AbsoluteToLocal(ScreenPosition); HoveredDrop=INDEX_NONE; HoveredPanelSurface=INDEX_NONE;
    LayoutDeployment();
    // Use Slate's actual hit path, including clipping and collapsed ancestors.
    // Hidden/offscreen panel cards must never accept a drop through the board.
    if(DragKeepsPanels) {
        const auto Path=FSlateApplication::Get().LocateWindowUnderMouse(ScreenPosition,FSlateApplication::Get().GetInteractiveTopLevelWindows());
        for(int32 S=0;S<PanelDropSurfaces.Num();++S)if(auto Widget=PanelDropSurfaces[S].Widget.Pin())
            if(Path.ContainsWidget(Widget.Get())) {
                int32 Match=INDEX_NONE,Count=0;
                for(int32 I=0;I<DropTargets.Num();++I)if(DropMatchesSurface(DropTargets[I],PanelDropSurfaces[S])) {Match=I;++Count;}
                if(Count==1){HoveredDrop=Match;HoveredPanelSurface=S;return true;}
                // Multiple costs/sources/replacements require an explicit badge.
                return false;
            }
    }
    if (!OverBattlefield(ScreenPosition)) return false;
    const float U=OverlayUnit();
    for (int32 I=0;I<DropTargets.Num();++I) {
        const auto& T=DropTargets[I];
        if (BattlefieldTextVisible&&T.Visible&&FMath::Abs(T.Screen.X-DragPointer.X)<=T.LabelSize.X*.5f&&FMath::Abs(T.Screen.Y-DragPointer.Y)<=T.LabelSize.Y*.5f) {HoveredDrop=I;return true;}
    }
    int32 Width=0,Height=0;Owner->GetViewportSize(Width,Height);
    const FVector2D Size=GetCachedGeometry().GetLocalSize();
    const FVector2D Pixel=DragPointer*FVector2D(Width/FMath::Max(1.,Size.X),Height/FMath::Max(1.,Size.Y));
    const int32 Pick=OldWestWorldInteraction::PickVisibleUnitAtScreen(Owner.Get(),Pixel);
    // A camp's roof can occlude the ground marker immediately in front of it.
    // A precise drop on that marked lane takes precedence over reselecting
    // the dragged camp itself; unrelated visible cards still block the lane.
    if(Pick==DraggedCard||Pick==INDEX_NONE) {
        float Closest=20*U,RunnerUp=TNumericLimits<float>::Max();int32 Lane=INDEX_NONE;
        for(int32 I=0;I<DropTargets.Num();++I)if(DropTargets[I].TargetCard==0&&DropTargets[I].Column>=0) {
            FVector2D At;if(!ProjectToHUD(DropTargets[I].World,At))continue;
            const float Distance=FVector2D::Distance(At,DragPointer);
            if(Distance<Closest){if(Lane!=INDEX_NONE)RunnerUp=Closest;Closest=Distance;Lane=I;}
            else RunnerUp=FMath::Min(RunnerUp,Distance);
        }
        if(Lane!=INDEX_NONE&&RunnerUp-Closest>8*U){HoveredDrop=Lane;return true;}
    }
    int32 Exact=INDEX_NONE,Count=0;
    for(int32 I=0;I<DropTargets.Num();++I)if(DropTargets[I].TargetCard!=0&&DropTargets[I].TargetCard==Pick){Exact=I;++Count;}
    if(Count==1){HoveredDrop=Exact;return true;}
    if(Count>1)return false;
    // The lit camp area includes its open interior: users need not hit a thin
    // fence or beam. A different visible card still blocks this fallback.
    // Lane landing rings likewise accept drops, not only their offset labels.
    float Best=60*U,Second=TNumericLimits<float>::Max();int32 Nearest=INDEX_NONE;
    for(int32 I=0;I<DropTargets.Num();++I) {
        if(DropTargets[I].TargetCard!=0&&Pick!=INDEX_NONE&&Pick!=DropTargets[I].TargetCard)continue;
        FVector2D Anchor;if(!ProjectToHUD(DropTargets[I].World,Anchor))continue;
        const float Distance=FVector2D::Distance(Anchor,DragPointer);
        if(Distance<Best){if(Nearest!=INDEX_NONE)Second=Best;Best=Distance;Nearest=I;}else Second=FMath::Min(Second,Distance);
    }
    if(Nearest!=INDEX_NONE&&Second-Best>8*U)HoveredDrop=Nearest;
    return HoveredDrop!=INDEX_NONE;
}
bool SOldWestHUD::DropDeployment()
{
    if (!Owner.IsValid() || !DropTargets.IsValidIndex(HoveredDrop)) { EndDeployment(); return false; }
    const auto Destination=DropTargets[HoveredDrop];
    if(!Destination.BlockedReason.IsEmpty()) {
        const FString Reason=Destination.BlockedReason;EndDeployment();Owner->ClientNotice(Reason);return false;
    }
    const J Command = Destination.Command;
    J Current;
    try { Current = J::parse(TCHAR_TO_UTF8(*Owner->GetPresentationSnapshot())); } catch (const std::exception&) { EndDeployment(); return false; }
    const bool Same = Current.value("match_id", std::string()) == std::string(TCHAR_TO_UTF8(*DragMatch))
        && Current["view"].value("revision", -1) == DragRevision;
    bool Legal = false;
    for (const auto& Action : Current["actions"]) {
        if (Action["command"] == Command) { Legal = true; break; }
        for(const auto& Gesture:Action.value("gestures",J::array()))if(Gesture["command"]==Command){Legal=true;break;}
        if(Legal)break;
    }
    const int32 ExpectedRevision = DragRevision;
    const FString ExpectedMatch = DragMatch;
    const int32 SourceCard=DraggedCard;
    const bool Destructive=!Destination.Alternatives.empty()&&Destination.Alternatives[0].value("confirm",false);
    const bool NeedsMenu=Destination.Alternatives.size()>1||Destructive;
    if(Same&&Legal&&!NeedsMenu&&PunkShelter.IsValid()&&AOldWestPunkShelter::IsToken(SourceCard))PunkShelter->Submitted(SourceCard);
    EndDeployment();
    if (!Same || !Legal) { Owner->ClientNotice(TEXT("The battlefield changed. Drag the card again.")); return false; }
    if(NeedsMenu) {
        FMenuBuilder Menu(true,nullptr);
        const TWeakPtr<SOldWestHUD> Weak=SharedThis(this);
        for(const auto& Option:Destination.Alternatives) {
            const J Chosen=Option["command"];
            const FString Caption=(Option.value("confirm",false)?TEXT("CONFIRM · "):TEXT(""))+Text(Option["label"]);
            Menu.AddMenuEntry(FText::FromString(Caption),FText(),FSlateIcon(),FUIAction(FExecuteAction::CreateLambda([Weak,Chosen,ExpectedRevision,ExpectedMatch,SourceCard](){
                if(auto HUD=Weak.Pin())if(HUD->Owner.IsValid()) {
                    if(HUD->PunkShelter.IsValid()&&AOldWestPunkShelter::IsToken(SourceCard))HUD->PunkShelter->Submitted(SourceCard);
                    HUD->Owner->ServerSubmit(Text(Chosen.dump()),ExpectedRevision,ExpectedMatch);
                    HUD->SelectedSource=0;HUD->Dirty=true;
                }
            })));
        }
        Menu.AddMenuEntry(FText::FromString(TEXT("Cancel")),FText(),FSlateIcon(),FUIAction(FExecuteAction::CreateLambda([](){})));
        const auto MenuWidget=Menu.MakeWidget();
#if !UE_BUILD_SHIPPING
        LastContextWidget=MenuWidget;LastContextActions=Destination.Alternatives;
#endif
        FSlateApplication::Get().PushMenu(SharedThis(this),FWidgetPath(),MenuWidget,FSlateApplication::Get().GetCursorPos(),FPopupTransitionEffect(FPopupTransitionEffect::ContextMenu));
    } else Owner->ServerSubmit(Text(Command.dump()), ExpectedRevision, ExpectedMatch);
    SelectedSource = 0; Dirty = true;
    return true;
}
void SOldWestHUD::UpdateShelterDrag(const FVector2D& Position)
{
    if(DraggedWorldPreview.IsValid())
    {
        if(DropTargets.IsValidIndex(HoveredDrop))
            DraggedWorldPreview->SetActorLocation(DropTargets[HoveredDrop].World-FVector(0,0,45));
        else if(OverBattlefield(Position))
        {
            int32 W=0,H=0;Owner->GetViewportSize(W,H);
            const auto& G=GetCachedGeometry();const auto Size=G.GetLocalSize(),Local=G.AbsoluteToLocal(Position);
            FVector O,D;
            if(Owner->DeprojectScreenPositionToWorld(Local.X*W/Size.X,Local.Y*H/Size.Y,O,D)&&D.Z<-.05f)
                DraggedWorldPreview->SetActorLocation(O+D*((DragWorldStart.Z-O.Z)/D.Z));
        }
    }
    if(!PunkShelter.IsValid()||!AOldWestPunkShelter::IsToken(DraggedCard))return;
    if(DropTargets.IsValidIndex(HoveredDrop)){PunkShelter->PreviewAt(DraggedCard,DropTargets[HoveredDrop].World-FVector(0,0,45));return;}
    if(!OverBattlefield(Position))return;
    int32 W=0,H=0;Owner->GetViewportSize(W,H);
    const auto& G=GetCachedGeometry();const FVector2D Size=G.GetLocalSize(),Local=G.AbsoluteToLocal(Position);
    FVector O,D;
    if(Owner->DeprojectScreenPositionToWorld(Local.X*W/Size.X,Local.Y*H/Size.Y,O,D)&&D.Z<-.05f) {
        const FVector P=O+D*((PunkShelter->GetActorLocation().Z-O.Z)/D.Z);
        if(FVector::Dist2D(P,PunkShelter->GetActorLocation())<6000)PunkShelter->PreviewAt(DraggedCard,P);
    }
}
FReply SOldWestHUD::OnDragOver(const FGeometry&, const FDragDropEvent& Event)
{
    if (!Event.GetOperationAs<FOldWestCardDrag>()) return FReply::Unhandled();
    UpdateDeployment(Event.GetScreenSpacePosition());
    UpdateShelterDrag(Event.GetScreenSpacePosition());
    return FReply::Handled();
}
FReply SOldWestHUD::OnDrop(const FGeometry&, const FDragDropEvent& Event)
{
    if (!Event.GetOperationAs<FOldWestCardDrag>()) return FReply::Unhandled();
    UpdateDeployment(Event.GetScreenSpacePosition()); DropDeployment();
    return FReply::Handled();
}
FString SOldWestHUD::DeploymentHintText() const
{
    return DragName + (HoveredDrop == INDEX_NONE ? TEXT(" · Choose a position") : (DropTargets[HoveredDrop].BlockedReason.IsEmpty()?TEXT(" · Release: "):TEXT(" · ")) + DropTargets[HoveredDrop].Label.Replace(TEXT("\n"), TEXT(" ")));
}

FSlateRect SOldWestHUD::DeploymentHintRect() const
{
    const float U=OverlayUnit();
    const FSlateRect Bounds=BattlefieldRect();
    const float Width=FMath::Min(500*U,Bounds.Right-Bounds.Left-16*U);
    return FSlateRect((Bounds.Left+Bounds.Right-Width)*.5f,Bounds.Top+5*U,
        (Bounds.Left+Bounds.Right+Width)*.5f,Bounds.Top+31*U);
}

int32 SOldWestHUD::OnPaint(const FPaintArgs& Args, const FGeometry& Geometry, const FSlateRect& CullingRect,
    FSlateWindowElementList& Elements, int32 Layer, const FWidgetStyle& Style, bool ParentEnabled) const
{
    const int32 Underlay=PaintDamageMarkers(Geometry,Elements,Layer);
    int32 Top = SCompoundWidget::OnPaint(Args, Geometry, CullingRect, Elements, Underlay, Style, ParentEnabled);
#if !UE_BUILD_SHIPPING
    // Observe after the child paint traversal. Session reports occur earlier
    // than Slate attribute evaluation and can see previous-frame visibility.
    static const bool CapturePaint = FParse::Param(FCommandLine::Get(), TEXT("OldWestVisualTest"));
    if (CapturePaint)
    {
        J Painted = {{"match_id", Owner.IsValid() ? std::string(TCHAR_TO_UTF8(*Owner->GetPresentationMatchId())) : std::string()},
            {"sequence", Owner.IsValid() ? Owner->GetCinematicSequence() : INDEX_NONE},
            {"busy", Owner.IsValid() && Owner->IsCinematicBusy()},
            {"analysis_choice_framed", Owner.IsValid() && Owner->IsAnalysisChoiceFramed()},
            {"view_generation", SeenGeneration}, {"visible_docks", J::array()}};
        for (const auto& Dock : DockPanels)
            if (Dock.IsValid() && Dock->GetVisibility().IsVisible())
                Painted["visible_docks"].push_back(std::string(TCHAR_TO_UTF8(*Dock->GetPanelId())));
        const TSharedPtr<SWidget> EndPanel = MatchEndPanel.Pin();
        Painted["end_panel_present"] = EndPanel.IsValid();
        Painted["end_panel_visible"] = EndPanel.IsValid() && EndPanel->GetVisibility().IsVisible();
        LastPaintFrame = GFrameCounter;
        // Keep the first paint of each visibility/shot state, including any
        // one-frame flash. Repeated identical frames must not erase it.
        if (Painted != LastPaintObservation)
        {
            LastPaintObservation = Painted;
            Painted["frame"] = GFrameCounter;
            PaintTransitions.push_back(MoveTemp(Painted));
            if (PaintTransitions.size() > 128) PaintTransitions.erase(PaintTransitions.begin());
        }
    }
#endif
    if (DraggedCard == INDEX_NONE || !Owner.IsValid()) return Top;
    const float Scale = OverlayUnit();
    if(PanelDropSurfaces.IsValidIndex(HoveredPanelSurface))if(auto Widget=PanelDropSurfaces[HoveredPanelSurface].Widget.Pin()) {
        const FGeometry& G=Widget->GetCachedGeometry();
        const FVector2D A=Geometry.AbsoluteToLocal(G.LocalToAbsolute(FVector2D::ZeroVector)), B=Geometry.AbsoluteToLocal(G.LocalToAbsolute(G.GetLocalSize()));
        FSlateDrawElement::MakeLines(Elements,Top+2,Geometry.ToPaintGeometry(),{A,FVector2D(B.X,A.Y),B,FVector2D(A.X,B.Y),A},
            ESlateDrawEffect::None,FLinearColor(.18f,1.f,.72f,1),true,3.f);
    }
    LayoutDeployment();
    for (int32 I = 0; I < DropTargets.Num(); ++I)
    {
        const FDropTarget& Target = DropTargets[I];
        FVector2D Position;
        if (!Target.Visible || !ProjectToHUD(Target.World, Position)) continue;
        const FVector2D GroundPoint = Position;
        const bool Active=I==HoveredDrop;
        const float Radius=(Active?24.f:18.f)*Scale;
        const float Pulse=.65f+.25f*FMath::Sin(float(FPlatformTime::Seconds()*4.));
        const FLinearColor RingColor=Active?FLinearColor(.18f,1.f,.72f,1):FLinearColor(.24f,.81f,.73f,Pulse);
        TArray<FVector2D> Ring;
        for(int32 Step=0;Step<=32;++Step){const float A=Step*2.f*PI/32;Ring.Add(GroundPoint+FVector2D(FMath::Cos(A)*Radius,FMath::Sin(A)*Radius*.45f));}
        FSlateDrawElement::MakeLines(Elements,Top+1,Geometry.ToPaintGeometry(),Ring,ESlateDrawEffect::None,RingColor,true,Active?3.f:1.5f);
        if(Active){
            const FVector2D Cursor=Geometry.AbsoluteToLocal(FSlateApplication::Get().GetCursorPos());
            FSlateDrawElement::MakeLines(Elements,Top+1,Geometry.ToPaintGeometry(),{Cursor,GroundPoint},ESlateDrawEffect::None,RingColor,true,2.f);
        }
        if(!BattlefieldTextVisible)continue;
        Position = Target.Screen;
        const FVector2D Size=Target.LabelSize;
        const FLinearColor Color = I == HoveredDrop ? FLinearColor(0.14f,0.85f,0.65f,0.96f) : FLinearColor(0.06f,0.19f,0.21f,0.92f);
        TArray<FVector2D> Link; Link.Add(GroundPoint); Link.Add(Position);
        FSlateDrawElement::MakeLines(Elements, Top+1, Geometry.ToPaintGeometry(), Link, ESlateDrawEffect::None, Color, true, 2.f);
        FSlateDrawElement::MakeBox(Elements, Top + 1, Geometry.ToPaintGeometry(Size, FSlateLayoutTransform(Position - Size * .5f)),
            FCoreStyle::Get().GetBrush("WhiteBrush"), ESlateDrawEffect::None, Color);
        const auto Font = FCoreStyle::GetDefaultFontStyle("Bold", FMath::Max(1, FMath::RoundToInt(16 * Scale)));
        FSlateDrawElement::MakeText(Elements, Top + 2, Geometry.ToPaintGeometry(Size, FSlateLayoutTransform(Position - Size * .5f + FVector2D(12,10)*Scale)),
            Target.DisplayLabel, Font, ESlateDrawEffect::None, FLinearColor::White);
    }
    if(!BattlefieldTextVisible)return Top+2;
    const FString Hint = DeploymentHintText();
    const FSlateRect HintRect = DeploymentHintRect();
    const FVector2D Position(HintRect.Left, HintRect.Top), Size(HintRect.Right-HintRect.Left, HintRect.Bottom-HintRect.Top);
    FSlateDrawElement::MakeBox(Elements, Top + 3, Geometry.ToPaintGeometry(Size, FSlateLayoutTransform(Position)),
        FCoreStyle::Get().GetBrush("WhiteBrush"), ESlateDrawEffect::None, Panel);
    FSlateDrawElement::MakeText(Elements, Top + 4, Geometry.ToPaintGeometry(Size, FSlateLayoutTransform(Position + FVector2D(8,5)*Scale)),
        Hint, FCoreStyle::GetDefaultFontStyle("Bold", FMath::Max(1,FMath::RoundToInt(11*Scale))), ESlateDrawEffect::None, Sand);
    return Top + 4;
}
TSharedRef<SWidget> SOldWestHUD::AnimatedCard(const J& Card, float PortraitHeight, bool Compact)
{
    const bool Hidden = Card.value("punk", false);
    const FString Id = Hidden ? TEXT("punk") : Text(Card.value("card_id", Card.value("id", J("")).is_string() ? Card.value("id", std::string()) : std::string()));
    const J* Definition = Hidden ? nullptr : CardDefinition(std::string(TCHAR_TO_UTF8(*Id)));
    // Raw catalog type: the portrait builder keys on it and it is never displayed here.
    const FString Type = Hidden ? TEXT("person") : Text(Definition ? Definition->value("type", std::string("person")) : Card.value("type", std::string("person")));
    TSharedRef<SVerticalBox> Visual = SNew(SVerticalBox);
    Visual->AddSlot().AutoHeight()[SNew(SBox).HeightOverride(PortraitHeight)
        [MakeOldWestCardPortrait(Owner->GetWorld(), Text(OldWestCosmetics::Visual(Card)), Type, Hidden)]];
    Visual->AddSlot().AutoHeight().Padding(8,4,8,0)[Label(Text(Card.value("name", std::string("Punk"))), Compact ? 17 : 20, Sand)];
    if (Definition)
    {
        FString Meta;
        if (Definition->contains("play_cost")) Meta = FString::Printf(TEXT("%d WHISKEY"),
            Card.contains("play_availability")?Card["play_availability"].value("cost",0):Definition->value("play_cost",0));
        else if (Definition->contains("starting_cards")) Meta = FString::Printf(TEXT("%d STARTING CARDS"), Definition->value("starting_cards",0));
        if (Definition->contains("junk")) Meta += OldWestDisplay::Text((Compact ? TEXT("\nJunk: ") : TEXT(" · JUNK ")) + Text((*Definition)["junk"]));
        Visual->AddSlot().AutoHeight().Padding(8,2,8,6)[Label(Meta, 14, Sand)];
    }
    return SNew(SBorder).BorderImage(FCoreStyle::Get().GetBrush("WhiteBrush")).BorderBackgroundColor(Panel).Padding(0)[Visual];
}

TSharedRef<SWidget> SOldWestHUD::Label(const FString& Value, int32 Size, FLinearColor Color)
{
    return SNew(STextBlock).Text(FText::FromString(Value)).Font(FCoreStyle::GetDefaultFontStyle(Size >= 22 ? "Bold" : "Regular", Size))
        .ColorAndOpacity(Color).AutoWrapText(true);
}
void SOldWestHUD::PlayUiSound(bool Cancel)
{
    if (!Owner.IsValid()) return;
    const TCHAR* Path = Cancel ? TEXT("/Game/Audio/SW_UI_Cancel.SW_UI_Cancel") : TEXT("/Game/Audio/SW_UI_Confirm.SW_UI_Confirm");
    if (USoundBase* Sound = LoadObject<USoundBase>(nullptr, Path)) UGameplayStatics::PlaySound2D(Owner.Get(), Sound, 0.6f);
}
TSharedRef<SWidget> SOldWestHUD::Button(const FString& Value, TFunction<void()> OnClick, const FString& Tooltip, bool Enabled, bool CancelSound, float WrapAt)
{
    return SNew(SButton).ButtonStyle(&ActionButtonStyle()).ContentPadding(FMargin(8.f, 4.f))
        .IsEnabled(Enabled).ToolTip(OldWestTooltip(FText::FromString(Tooltip)))
        .OnClicked_Lambda([this, CancelSound, OnClick = MoveTemp(OnClick)]() { PlayUiSound(CancelSound); OnClick(); return FReply::Handled(); })
        [SNew(STextBlock).Text(FText::FromString(Value)).Font(FCoreStyle::GetDefaultFontStyle("Regular", 12))
            .ColorAndOpacity(Sand).WrapTextAt(WrapAt).AutoWrapText(WrapAt <= 0.f)];
}
const J* SOldWestHUD::CardDefinition(const std::string& CardId) const
{
    for (const auto& Card : Catalog["cards"]) if (Card["id"] == CardId) return &Card;
    return nullptr;
}
FString SOldWestHUD::CardDescription(const std::string& CardId) const
{
    if (const J* Found = CardDefinition(CardId))
    {
        const J& Card = *Found;
        FString Detail = Text(Card.value("trait", std::string()));
        if (Card.contains("effect")) Detail += TEXT("\n") + Text(Card["effect"]);
        for (const auto& Ability : Card["abilities"])
            Detail += FString::Printf(TEXT("\n%d whiskey · "), Ability.value("cost", 0)) + Text(Ability.value("effect", std::string()));
        if (Card.contains("junk")) Detail += TEXT("\nHock: ") + Text(Card["junk"]);
        return Detail.TrimStartAndEnd();
    }
    return FString();
}
void SOldWestHUD::Inspect(int32 CardId, bool Owned)
{
    if (Owner.IsValid() && Owner->IsAnalysisChoiceFramed()) Owner->SetAnalysisChoiceFramed(false);
    InspectedCard = CardId;
    SelectedSource = Owned ? CardId : 0;
    HistoryOpen = false;
    if(Owned&&Owner.IsValid()&&!Owner->GetPresentationSnapshot().IsEmpty()) {
        const J Data=J::parse(TCHAR_TO_UTF8(*Owner->GetPresentationSnapshot()));
        if(Data.contains("view")&&Data.contains("seat"))for(const auto& Column:Data["view"]["players"][Data.at("seat").get<int>()]["columns"])
            for(const auto& Card:Column)if(Card.value("id",0)==CardId) {
                if(Card.contains("private_peek")) {
                    BattleSections.Add(TEXT("your.details"),false);
                    BattleScrollOffsets.Add(TEXT("your."),0.f);
                }
                if(Card.contains("private_peek")||Card.value("card_id",std::string())=="wanted_poster_board")
                    BattleSections.Add(TEXT("your.actions"),false);
            }
    }
    Dirty = true;
}

bool SOldWestHUD::InspectVisibleCard(int32 CardId)
{
    if (!Owner.IsValid() || Owner->GetPresentationSnapshot().IsEmpty()) return false;
    const J Snapshot = J::parse(TCHAR_TO_UTF8(*Owner->GetPresentationSnapshot()));
    if (!Snapshot.contains("view") || !Snapshot.contains("seat")) return false;
    const int32 Seat = Snapshot.at("seat");
    if (Seat < 0 || Seat > 1) return false;
    const J& Players = Snapshot.at("view").at("players");
    // Use exactly the public board/queues and this player's private hand. The
    // bridge cannot select an unknown opponent hand or inspect a hidden face.
    for (int32 Side = 0; Side < 2; ++Side)
    {
        const J& Player = Players.at(Side);
        for (const auto& Column : Player.at("columns"))
            for (const auto& Card : Column)
                if (Card.value("id", 0) == CardId)
                {
                    InspectorSide = Side;
                    Inspect(CardId, Side == Seat);
                    PlayUiSound(false);
                    return true;
                }
        for (const auto& Event : Player.at("queue"))
            if (!Event.is_null() && Event.value("id", 0) == CardId)
            {
                InspectorSide = Side;
                Inspect(CardId, Side == Seat);
                PlayUiSound(false);
                return true;
            }
    }
    for (const auto& Card : Players.at(Seat).at("hand"))
        if (Card.value("id", 0) == CardId)
        {
            InspectorSide = Seat;
            Inspect(CardId, true);
            PlayUiSound(false);
            return true;
        }
    return false;
}
#if !UE_BUILD_SHIPPING
void SOldWestHUD::PointerForVisualTest(const J& Command)
{
    const FVector2D Local(Command.value("x",0.0), Command.value("y",0.0));
    const FVector2D Position = GetCachedGeometry().LocalToAbsolute(Local);
    const FString ButtonName = Text(Command.value("button",std::string("left")));
    const FKey Button = ButtonName == TEXT("right") ? EKeys::RightMouseButton : ButtonName == TEXT("middle") ? EKeys::MiddleMouseButton : EKeys::LeftMouseButton;
    const std::string Phase = Command.value("phase",std::string("move"));
    if (Phase == "down" || Phase == "double") TestPointerButtons.Add(Button);
    if (Phase == "up") TestPointerButtons.Remove(Button);
    // Match real desktop mouse input. Keyboard replies (including Esc) release
    // CursorPointerIndex; a synthetic touch index would leave mouse capture stuck.
    FPointerEvent Event(FSlateApplication::CursorPointerIndex, Position, TestPointerPosition, TestPointerButtons, Button,
        Command.value("wheel",0.f), FModifierKeysState());
    auto& App = FSlateApplication::Get();
    App.SetCursorPos(Position);
    if (Phase == "down")
    {
        TSharedPtr<SWindow> Window = App.FindWidgetWindow(SharedThis(this));
        App.ProcessMouseButtonDownEvent(Window.IsValid() ? Window->GetNativeWindow() : nullptr, Event);
    }
    else if (Phase == "up") App.ProcessMouseButtonUpEvent(Event);
    else if (Phase == "double") {
        const auto Window=App.FindWidgetWindow(SharedThis(this));
        if(Window.IsValid())App.ProcessMouseButtonDoubleClickEvent(Window->GetNativeWindow(),Event);
    }
    else if (Phase == "wheel") App.ProcessMouseWheelOrGestureEvent(Event, nullptr);
    else App.ProcessMouseMoveEvent(Event, false);
    TestPointerPosition = Position;
}
void SOldWestHUD::GalleryForVisualTest(const J& Command)
{
    if(Command.contains("details") && Command["details"].is_array())
    {
        for(const auto& Detail:Command["details"])
            if(Detail.is_object() && Detail.contains("id") && Detail["id"].is_string())
            {
                const std::string Id=Detail["id"];
                const J* Definition=CardDefinition(Id);
                if(Definition && Definition->value("type",std::string())=="person")
                    SetOldWestCardPortraitDetail(Owner.IsValid()?Owner->GetWorld():nullptr,Text(Id),
                        Detail.value("enabled",true),Text(Detail.value("expression",std::string("neutral"))));
            }
        return;
    }
    if (Command.contains("conditions") && Command["conditions"].is_array())
    {
        // Presentation-only inspection of already-created public catalog scenes.
        for (const auto& Condition : Command["conditions"])
            if (Condition.is_object() && Condition.contains("id") && Condition["id"].is_string())
            {
                const std::string Id = Condition["id"];
                const J* Definition = CardDefinition(Id);
                if (Definition && Definition->value("type", std::string()) == "camp")
                    SetOldWestCardPortraitCondition(Owner.IsValid() ? Owner->GetWorld() : nullptr, Text(Id),
                        FMath::Clamp(Condition.value("damage", 0), 0, 2), Condition.value("destroyed", false));
            }
        return;
    }
    GalleryCards.Empty();
    if (Command.value("enabled",true) && Command.contains("ids"))
        for (const auto& Id : Command["ids"]) if (Id.is_string() && GalleryCards.Num() < 6 && CardDefinition(Id.get<std::string>())) GalleryCards.Add(Text(Id.get<std::string>()));
    EndDeployment(); Dirty = true;
}
bool SOldWestHUD::InspectForVisualTest(int32 CardId)
{
    return InspectVisibleCard(CardId);
}
void SOldWestHUD::SetRulesForVisualTest(bool Open)
{
    if (Open && SettingsOpen) CloseSettings();
    HelpOpen = Open;
    Dirty = true;
}
void SOldWestHUD::SettingsForVisualTest(const J& Command)
{
    const std::string Operation = Command.value("operation", std::string("open"));
    if (Operation == "open") OpenSettings();
    else if (Operation == "close") CloseSettings();
    else if (SettingsOpen && Operation == "edit")
    {
        if (Command.contains("width")) SettingsDraft.Resolution = FIntPoint(Command.at("width").get<int32>(), Command.at("height").get<int32>());
        if (Command.contains("window_mode")) SettingsDraft.WindowMode = static_cast<EWindowMode::Type>(Command.at("window_mode").get<int32>());
        if (Command.contains("quality")) SettingsDraft.Quality = Command.at("quality").get<int32>();
        if (Command.contains("frame_limit")) SettingsDraft.FrameLimit = Command.at("frame_limit").get<float>();
        if (Command.contains("volume")) SettingsDraft.Volume = Command.at("volume").get<float>();
        if (Command.contains("card_hover")) SettingsDraft.CardHover = Command.at("card_hover").get<bool>();
        Dirty = true;
    }
    else if (SettingsOpen && Operation == "apply") ApplySettingsDraft();
    else if (Operation == "keep") KeepSettings();
    else if (Operation == "revert") RevertSettings();
}
J SOldWestHUD::VisualTestState() const
{
    J State = {{"inspected_card", InspectedCard}, {"selected_source", SelectedSource},
        {"inspector_side", InspectorSide}, {"rules_open", HelpOpen},
        {"war_room_open",WarRoomOpen},{"rules_category",std::string(TCHAR_TO_UTF8(*RulesCategory))},
        {"rules_card_count",RulesContent.value("cards",J::array()).size()},{"rules_visible_cards",RulesVisibleCards},
        {"reference_width", 1920}, {"reference_height", 1080},
        {"cinematic_busy", Owner.IsValid() && Owner->IsCinematicBusy()}, {"controls_visible", SceneControlsVisible()}};
    State["asset_history"] = J::object();
    if(const auto Link=AssetHistoryButton.Pin()) {
        State["asset_history"]=AssetHistoryNote;
        State["asset_history"]["open"]=Link->IsOpen();
    }
    State["invite_buttons"] = J::array();
    const FGeometry& ViewportGeometry = GetCachedGeometry();
    const FVector2D ViewportSize = ViewportGeometry.GetLocalSize();
    State["hud_size"] = {ViewportSize.X, ViewportSize.Y};
    int32 PixelWidth = 0, PixelHeight = 0;
    if (Owner.IsValid()) Owner->GetViewportSize(PixelWidth, PixelHeight);
    State["viewport_size"] = {PixelWidth, PixelHeight};
    if (SceneHitArea.IsValid())
    {
        const FGeometry& Scene = SceneHitArea->GetCachedGeometry();
        const FVector2D Min = ViewportGeometry.AbsoluteToLocal(Scene.LocalToAbsolute(FVector2D::ZeroVector));
        const FVector2D Max = ViewportGeometry.AbsoluteToLocal(Scene.LocalToAbsolute(Scene.GetLocalSize()));
        State["scene_rect"] = {{"min",{Min.X,Min.Y}},{"max",{Max.X,Max.Y}}};
        State["drag_rect"] = {{"min",{0,Min.Y}},{"max",{ViewportSize.X,ViewportSize.Y}}};
    }
    auto GeometryList = [&ViewportGeometry](const auto& Entries) {
        J Result = J::array();
        for (const auto& Entry : Entries) if (TSharedPtr<SWidget> Widget = Entry.Value.Pin())
        {
            const FGeometry& G = Widget->GetCachedGeometry();
            const FVector2D Min = ViewportGeometry.AbsoluteToLocal(G.LocalToAbsolute(FVector2D::ZeroVector));
            const FVector2D Max = ViewportGeometry.AbsoluteToLocal(G.LocalToAbsolute(G.GetLocalSize()));
            const FVector2D Size = G.GetLocalSize(), Desired = Widget->GetDesiredSize();
            Result.push_back({{"id",std::string(TCHAR_TO_UTF8(*Entry.Key))},{"min",{Min.X,Min.Y}},{"max",{Max.X,Max.Y}},
                {"allocated_size",{Size.X,Size.Y}},{"desired_size",{Desired.X,Desired.Y}},
                {"visible",Widget->GetVisibility().IsVisible()},{"enabled",Widget->IsEnabled()}});
        }
        return Result;
    };
    State["world_hover_targets"]=J::array();
    if(Owner.IsValid()) for(TActorIterator<AOldWestUnit> It(Owner->GetWorld());It;++It) {
        if(It->IsHidden()||It->ActorHasTag(TEXT("OldWestPortraitPreview")))continue;
        const FBox Bounds=It->GetSelectionBounds();
        if(!Bounds.IsValid)continue;
        FVector2D Pixel;
        if(Owner->ProjectWorldLocationToScreen(Bounds.GetCenter(),Pixel))
            State["world_hover_targets"].push_back({{"id",It->EntityId},{"screen",{Pixel.X*ViewportSize.X/FMath::Max(1,PixelWidth),Pixel.Y*ViewportSize.Y/FMath::Max(1,PixelHeight)}},
                {"pick",OldWestWorldInteraction::PickVisibleUnitAtScreen(Owner.Get(),Pixel)}});
    }
    State["panel_drop_surfaces"]=J::array();
    for(const auto& Surface:PanelDropSurfaces)if(auto Widget=Surface.Widget.Pin()) {
        const auto Entries=GeometryList(TArray<TPair<FString,TWeakPtr<SWidget>>>{{TEXT("surface"),Surface.Widget}});
        if(Entries.empty())continue;
        J Entry=Entries[0];Entry["card"]=Surface.Card;Entry["side"]=Surface.Side;Entry["column"]=Surface.Column;Entry["row"]=Surface.Row;Entry["event_slot"]=Surface.EventSlot;
        State["panel_drop_surfaces"].push_back(Entry);
    }
    State["hand_cards"] = GeometryList(HandCards);
    State["context_actions"] = LastContextActions;
    TArray<TPair<FString,TWeakPtr<SWidget>>> MenuTexts;
    if(auto Menu=LastContextWidget.Pin()) {
        TFunction<void(TSharedRef<SWidget>)> Visit=[&](TSharedRef<SWidget> Widget) {
            if(Widget->GetTypeAsString()==TEXT("STextBlock"))MenuTexts.Emplace(StaticCastSharedRef<STextBlock>(Widget)->GetText().ToString(),Widget);
            if(auto* Children=Widget->GetChildren())for(int32 I=0;I<Children->Num();++I)Visit(Children->GetChildAt(I));
        };
        Visit(Menu.ToSharedRef());
    }
    State["context_entries"]=GeometryList(MenuTexts);
    State["field_buttons"] = GeometryList(FieldButtons);
    State["status_buttons"] = GeometryList(StatusButtons);
    State["punk_shelter"] = PunkShelter.IsValid()?J::parse(TCHAR_TO_UTF8(*PunkShelter->DebugState())):J();
    State["enemy_punk_shelter"] = EnemyPunkShelter.IsValid()?J::parse(TCHAR_TO_UTF8(*EnemyPunkShelter->DebugState())):J();
    State["own_stats_open"]=OwnStatsOpen;State["enemy_stats_open"]=EnemyStatsOpen;State["field_history_open"]=FieldHistoryOpen;
    State["enemy_speed"]=Preferences()?Preferences()->GetEnemySpeed():.5f;
    if(!State["punk_shelter"].is_null())for(auto& Punk:State["punk_shelter"]["crew"]) {
        const auto& W=Punk["world"];FVector2D P;
        if(ProjectToHUD(FVector(W[0].get<double>(),W[1].get<double>(),W[2].get<double>()+85),P))Punk["screen"]={P.X,P.Y};
    }
    State["battle_plan_open"] = BattlePlanOpen;
    State["master_tabs"] = GeometryList(MasterTabs);
    State["history_open"] = HistoryOpen;
    State["layout_generation"] = LayoutGeneration;
    State["battle_sections"] = GeometryList(SectionButtons);
    for(auto& Section:State["battle_sections"]) {
        const FString Key=Text(Section.value("id",std::string()));
        const bool* Closed=BattleSections.Find(Key);
        Section["collapsed"]=Closed&&*Closed;
        Section["forced_open"]=Key==TEXT("your.actions")&&PendingChoice;
    }
    State["damage_markers"] = DamageMarkers();
    State["battlefield_text_visible"] = BattlefieldTextVisible;
    State["battlefield_labels"] = BattlefieldLabels();
    State["fuse_line"] = Staging.IsValid()?J::parse(TCHAR_TO_UTF8(*Staging->GetFuseDebug())):J(nullptr);
    State["region"] = Staging.IsValid()?J::parse(TCHAR_TO_UTF8(*Staging->GetRegionDebug())):J(nullptr);
    State["route_scenery"] = J::parse(TCHAR_TO_UTF8(*AOldWestRegion::GetRouteSceneryDebug(Owner.IsValid()?Owner->GetWorld():nullptr)));
    const auto RenderRect=BattlefieldRect();
    State["battlefield_rect"]={RenderRect.Left,RenderRect.Top,RenderRect.Right,RenderRect.Bottom};
    State["overlay_unit"]=OverlayUnit();
    State["master_cards"] = GeometryList(MasterCards);
    State["formation_slots"] = GeometryList(FormationSlots);
    State["battle_scroll"]=GeometryList(TArray<TPair<FString,TWeakPtr<SWidget>>>{{TEXT("body"),BattleScrollWidget}});
    State["section_bodies"]=J::array();
    for(const auto& Body:SectionBodies)if(Body.IsValid())State["section_bodies"].push_back(Body->GetDebugGeometry(ViewportGeometry));
    State["master_actions"] = GeometryList(MasterActionButtons);
    State["master_actions_visible"] = MasterActionsVisible;
    State["card_hover"] = {{"enabled",CardHoverEnabled()},{"world_card",HoveredWorldCard},{"visible",WorldHoverVisible&&SceneControlsVisible()&&!SettingsOpen&&!HelpOpen},
        {"text",std::string(TCHAR_TO_UTF8(*WorldHoverText))}};
    if(WorldHoverBox.IsValid()) {
        const FGeometry& G=WorldHoverBox->GetCachedGeometry();
        const FVector2D Min=ViewportGeometry.AbsoluteToLocal(G.LocalToAbsolute(FVector2D::ZeroVector));
        const FVector2D Max=ViewportGeometry.AbsoluteToLocal(G.LocalToAbsolute(G.GetLocalSize()));
        State["card_hover"]["rect"]={{"min",{Min.X,Min.Y}},{"max",{Max.X,Max.Y}}};
    }
    State["paint"] = {{"last_frame", LastPaintFrame}, {"transitions", PaintTransitions}};
    State["analysis_choice_view"] = {{"available", Owner.IsValid() && Owner->HasAnalysisChoiceView()},
        {"framed", Owner.IsValid() && Owner->IsAnalysisChoiceFramed()}};
    State["overview_open"] = OverviewOpen;
    State["overview_cards"] = GeometryList(OverviewCards);
    State["dock_panels"] = J::array();
    for(const auto& Dock:DockPanels) if(Dock.IsValid()) State["dock_panels"].push_back(Dock->GetDebugGeometry(ViewportGeometry));
    State["chrome_visible"] = Root.IsValid()&&Root->GetVisibility().IsVisible();
    const TSharedPtr<SWidget> EndPanel = MatchEndPanel.Pin();
    State["end_panel"] = {{"present", EndPanel.IsValid()},
        {"visible", EndPanel.IsValid() && EndPanel->GetVisibility().IsVisible()}};
    State["history_ascending"]=FieldHistoryAscending;
    State["history_rendered_sequences"]=J::array();
    for(int32 Sequence:FieldHistoryRenderedSequences)State["history_rendered_sequences"].push_back(Sequence);
    State["camera_buttons"] = GeometryList(CameraButtons);
    State["roster_lanes"] = GeometryList(RosterLanes);
    State["placement_drag_buttons"] = GeometryList(PlacementDragButtons);
    State["portrait_gallery_cards"] = GeometryList(GalleryWidgets);
    State["portrait_gallery_enabled"] = !GalleryCards.IsEmpty();
    State["portraits"] = J::parse(TCHAR_TO_UTF8(*GetOldWestCardPortraitDebug(Owner.IsValid() ? Owner->GetWorld() : nullptr)));
    State["drag_diagnostics"]={{"active",FSlateApplication::Get().IsDragDropping()},{"pointer",{DragPointer.X,DragPointer.Y}}};
    if(auto Scroll=BattleDropScroll.Pin())State["drag_diagnostics"]["scroll"]={{"offset",Scroll->GetScrollOffset()},{"end",Scroll->GetScrollOffsetOfEnd()}};
    State["deployment"] = {{"card",DraggedCard},{"hovered",HoveredDrop},{"revision",DragRevision},{"keeps_panels",DragKeepsPanels},{"panel_surface",HoveredPanelSurface},{"targets",J::array()}};
    if (DraggedCard != INDEX_NONE)
    {
        const FSlateRect Hint = DeploymentHintRect();
        State["deployment"]["name"] = std::string(TCHAR_TO_UTF8(*DragName));
        State["deployment"]["hint"] = std::string(TCHAR_TO_UTF8(*DeploymentHintText()));
        State["deployment"]["hint_rect"] = {Hint.Left, Hint.Top, Hint.Right, Hint.Bottom};
    }
    LayoutDeployment();
    for (const FDropTarget& Target : DropTargets)
    {
        FVector2D Screen = FVector2D::ZeroVector, ProjectedPixels = FVector2D::ZeroVector;
        const bool Projected = Target.Visible;
        Screen = Target.Screen;
        if (Owner.IsValid()) Owner->ProjectWorldLocationToScreen(Target.World, ProjectedPixels);

        const FVector2D LabelPixels = ViewportSize.X > 0 && ViewportSize.Y > 0
            ? Screen * FVector2D(PixelWidth / ViewportSize.X, PixelHeight / ViewportSize.Y) : FVector2D::ZeroVector;
        State["deployment"]["targets"].push_back({{"world",{Target.World.X,Target.World.Y,Target.World.Z}},
            {"screen",{Screen.X,Screen.Y}},{"screen_pixels",{LabelPixels.X,LabelPixels.Y}},
            {"world_screen_pixels",{ProjectedPixels.X,ProjectedPixels.Y}},{"projected",Projected},
            {"label",std::string(TCHAR_TO_UTF8(*Target.Label))},{"target_card",Target.TargetCard},{"side",Target.Side},{"column",Target.Column},{"row",Target.Row},{"event_slot",Target.EventSlot},{"command",Target.Command},{"alternatives",Target.Alternatives}});
    }
    State["solo_difficulty"] = std::string(TCHAR_TO_UTF8(*SelectedDifficulty));
    State["solo_ruleset"] = IncludeExpansion ? "boomtown" : "base_2024";
    State["solo_buttons"] = J::array();
    for (const auto& Entry : SoloButtons) if (TSharedPtr<SWidget> Widget = Entry.Value.Pin())
    {
        const FGeometry& Geometry = Widget->GetCachedGeometry();
        const FVector2D Size = Geometry.GetLocalSize(), Desired = Widget->GetDesiredSize();
        const FVector2D Min = ViewportGeometry.AbsoluteToLocal(Geometry.LocalToAbsolute(FVector2D::ZeroVector));
        const FVector2D Max = ViewportGeometry.AbsoluteToLocal(Geometry.LocalToAbsolute(Size));
        State["solo_buttons"].push_back({{"id", std::string(TCHAR_TO_UTF8(*Entry.Key))},
            {"min", {Min.X, Min.Y}}, {"max", {Max.X, Max.Y}},
            {"allocated_size", {Size.X, Size.Y}}, {"desired_size", {Desired.X, Desired.Y}},
            {"enabled", Widget->IsEnabled()}, {"visible", Widget->GetVisibility().IsVisible()}});
    }
    for (const auto& Entry : InviteButtons) if (TSharedPtr<SWidget> Widget = Entry.Value.Pin())
    {
        const FGeometry& Geometry = Widget->GetCachedGeometry();
        const FVector2D Min = ViewportGeometry.AbsoluteToLocal(Geometry.LocalToAbsolute(FVector2D::ZeroVector));
        const FVector2D Max = ViewportGeometry.AbsoluteToLocal(Geometry.LocalToAbsolute(Geometry.GetLocalSize()));
        State["invite_buttons"].push_back({{"endpoint", std::string(TCHAR_TO_UTF8(*Entry.Key))},
            {"min", {Min.X, Min.Y}}, {"max", {Max.X, Max.Y}},
            {"enabled", Widget->IsEnabled()}, {"visible", Widget->GetVisibility().IsVisible()}});
    }
    State["camp_options"] = J::array();
    for (const auto& Entry : CampOptionButtons) if (TSharedPtr<SWidget> Widget = Entry.Value.Pin())
    {
        const FVector2D Size = Widget->GetCachedGeometry().GetLocalSize();
        const FVector2D Desired = Widget->GetDesiredSize();
        State["camp_options"].push_back({{"card", std::string(TCHAR_TO_UTF8(*Entry.Key))},
            {"allocated_size", {Size.X, Size.Y}}, {"desired_size", {Desired.X, Desired.Y}}});
    }
    if (FOldWestPreferences* Settings = Preferences())
    {
        const auto Values = Settings->Read(Owner.IsValid() ? Owner->GetWorld() : nullptr);
        State["settings"] = {{"open", SettingsOpen}, {"pending", Settings->IsPending()}, {"seconds", Settings->SecondsRemaining()},
            {"width", Values.Resolution.X}, {"height", Values.Resolution.Y}, {"window_mode", static_cast<int32>(Values.WindowMode)},
            {"quality", Values.Quality}, {"frame_limit", Values.FrameLimit}, {"volume", Values.Volume}, {"card_hover",Values.CardHover},
            {"persistence_enabled", Settings->CanPersist()}};
    }
    return State;
}
#endif

FOldWestPreferences* SOldWestHUD::Preferences() const
{
    UOldWestGameInstance* GI = Owner.IsValid() ? Cast<UOldWestGameInstance>(Owner->GetGameInstance()) : nullptr;
    return GI ? &GI->Preferences : nullptr;
}
void SOldWestHUD::OpenSettings()
{
    if (FOldWestPreferences* Settings = Preferences()) SettingsDraft = Settings->Read(Owner->GetWorld());
    SettingsOpen = true;
    HelpOpen = false;
    Dirty = true;
}
void SOldWestHUD::CloseSettings()
{
    RevertSettings();
    SettingsOpen = false;
    Dirty = true;
}
void SOldWestHUD::ApplySettingsDraft()
{
    if (FOldWestPreferences* Settings = Preferences()) Settings->Apply(Owner->GetWorld(), SettingsDraft);
    Dirty = true;
}
void SOldWestHUD::KeepSettings()
{
    if (FOldWestPreferences* Settings = Preferences()) Settings->Keep();
    Dirty = true;
}
void SOldWestHUD::RevertSettings()
{
    if (FOldWestPreferences* Settings = Preferences()) Settings->Revert(Owner->GetWorld());
    Dirty = true;
}
TSharedRef<SWidget> SOldWestHUD::SettingsPanel()
{
    FOldWestPreferences* Settings = Preferences();
    TSharedRef<SVerticalBox> Content = SNew(SVerticalBox);
    Content->AddSlot().AutoHeight()[Label(TEXT("SETTINGS"), 30, Sand)];
    if (!Settings) return Content;
    if (Settings->IsPending())
    {
        Content->AddSlot().AutoHeight().Padding(0, 28)[Label(TEXT("KEEP THIS DISPLAY SETTING?"), 26, Sand)];
        Content->AddSlot().AutoHeight()[SNew(STextBlock).Text_Lambda([this]() {
            const FOldWestPreferences* Current = Preferences();
            return FText::FromString(FString::Printf(TEXT("Previous settings return automatically in %d seconds."), Current ? Current->SecondsRemaining() : 0));
        }).Font(FCoreStyle::GetDefaultFontStyle("Regular", 23)).ColorAndOpacity(FLinearColor::White)];
        TSharedRef<SHorizontalBox> Confirm = SNew(SHorizontalBox);
        Confirm->AddSlot().FillWidth(1.f).Padding(0, 0, 10, 0)[Button(TEXT("KEEP"), [this]() { KeepSettings(); })];
        Confirm->AddSlot().FillWidth(1.f)[Button(TEXT("REVERT"), [this]() { RevertSettings(); }, FString(), true, true)];
        Content->AddSlot().AutoHeight().Padding(0, 28)[Confirm];
    }
    else
    {
        auto Row = [&](const FString& Heading, TSharedRef<SWidget> Control) {
            Content->AddSlot().AutoHeight().Padding(0, 12, 0, 5)[Label(Heading, 14, Sand)];
            Content->AddSlot().AutoHeight()[Control];
        };
        Row(TEXT("RESOLUTION"), SNew(SComboButton).ContentPadding(FMargin(10, 6))
            .ButtonContent()[Label(FString::Printf(TEXT("%d × %d"), SettingsDraft.Resolution.X, SettingsDraft.Resolution.Y), 15, Sand)]
            .OnGetMenuContent_Lambda([this]() -> TSharedRef<SWidget> {
                TSharedRef<SScrollBox> Options = SNew(SScrollBox);
                if (FOldWestPreferences* Current = Preferences()) for (const FIntPoint Size : Current->Resolutions(Owner->GetWorld()))
                    Options->AddSlot()[Button(FString::Printf(TEXT("%d × %d"), Size.X, Size.Y), [this, Size]() { SettingsDraft.Resolution = Size; Dirty = true; })];
                return SNew(SBox).WidthOverride(360).MaxDesiredHeight(380)[Options];
            }));
        TSharedRef<SHorizontalBox> Modes = SNew(SHorizontalBox);
        const TPair<EWindowMode::Type, FString> ModeOptions[] = {{EWindowMode::Windowed, TEXT("WINDOWED")},
            {EWindowMode::WindowedFullscreen, TEXT("BORDERLESS")}, {EWindowMode::Fullscreen, TEXT("FULLSCREEN")}};
        for (const auto& Option : ModeOptions)
            Modes->AddSlot().FillWidth(1.f).Padding(0, 0, 8, 0)[Button((SettingsDraft.WindowMode == Option.Key ? TEXT("✓ ") : TEXT("")) + Option.Value,
                [this, Mode = Option.Key]() { SettingsDraft.WindowMode = Mode; Dirty = true; })];
        Row(TEXT("WINDOW MODE"), Modes);
        TSharedRef<SHorizontalBox> Qualities = SNew(SHorizontalBox);
        const TCHAR* QualityNames[] = {TEXT("LOW"), TEXT("MEDIUM"), TEXT("HIGH"), TEXT("EPIC")};
        for (int32 Index = 0; Index < 4; ++Index)
            Qualities->AddSlot().FillWidth(1.f).Padding(0, 0, 8, 0)[Button((SettingsDraft.Quality == Index ? TEXT("✓ ") : TEXT("")) + FString(QualityNames[Index]),
                [this, Index]() { SettingsDraft.Quality = Index; Dirty = true; })];
        Row(SettingsDraft.Quality < 0 ? TEXT("GRAPHICS QUALITY · CUSTOM") : TEXT("GRAPHICS QUALITY"), Qualities);
        TSharedRef<SHorizontalBox> Limits = SNew(SHorizontalBox);
        for (const int32 Limit : {30, 60, 90, 120, 144, 240, 0})
            Limits->AddSlot().FillWidth(1.f).Padding(0, 0, 6, 0)[Button((SettingsDraft.FrameLimit == Limit ? TEXT("✓ ") : TEXT(""))
                + (Limit ? FString::FromInt(Limit) : TEXT("NO LIMIT")), [this, Limit]() { SettingsDraft.FrameLimit = Limit; Dirty = true; })];
        Row(TEXT("FRAME LIMIT"), Limits);
        TSharedRef<SHorizontalBox> Audio = SNew(SHorizontalBox);
        Audio->AddSlot().FillWidth(1.f).VAlign(VAlign_Center)[SNew(SSlider).Value_Lambda([this]() { return SettingsDraft.Volume; })
            .OnValueChanged_Lambda([this](float Value) { SettingsDraft.Volume = Value; })];
        Audio->AddSlot().AutoWidth().Padding(18, 0)[SNew(SBox).WidthOverride(90)[SNew(STextBlock)
            .Text_Lambda([this]() { return FText::FromString(FString::Printf(TEXT("%d%%"), FMath::RoundToInt(SettingsDraft.Volume * 100.f))); })
            .Font(FCoreStyle::GetDefaultFontStyle("Regular", 16)).ColorAndOpacity(Sand)]];
        Row(TEXT("MASTER VOLUME"), Audio);
        Row(TEXT("CARD INFORMATION ON HOVER"), Button(SettingsDraft.CardHover ? TEXT("ON · holdings and crew") : TEXT("OFF"),
            [this]() { SettingsDraft.CardHover = !SettingsDraft.CardHover; Dirty = true; }));
        Content->AddSlot().AutoHeight().Padding(0, 24, 0, 0)[Label(TEXT("Borderless uses your desktop resolution. Display changes require confirmation."), 13)];
        if (!Settings->Message().IsEmpty()) Content->AddSlot().AutoHeight().Padding(0, 14, 0, 0)[Label(Settings->Message(), 13, Sand)];
        TSharedRef<SHorizontalBox> Actions = SNew(SHorizontalBox);
        Actions->AddSlot().FillWidth(1.f).Padding(0, 0, 10, 0)[Button(TEXT("APPLY"), [this]() { ApplySettingsDraft(); })];
        Actions->AddSlot().FillWidth(1.f)[Button(TEXT("BACK"), [this]() { CloseSettings(); }, FString(), true, true)];
        Content->AddSlot().AutoHeight().Padding(0, 24, 0, 0)[Actions];
    }
    return SNew(SBorder).BorderImage(FCoreStyle::Get().GetBrush("WhiteBrush")).BorderBackgroundColor(Panel).Padding(30)[Content];
}

TSharedRef<SWidget> SOldWestHUD::CardDetails(const J& Card, int32 Seat)
{
    TSharedRef<SVerticalBox> Details = SNew(SVerticalBox);
    if (Card.is_null())
    {
        Details->AddSlot().AutoHeight()[Button(TEXT("ALL ABILITIES · G"),[this](){SetBattleOverview(true);},TEXT("Compare both outfits"))];
        Details->AddSlot().AutoHeight().Padding(0, 8)[Label(TEXT("Select a card for details."), 16)];
        return Details;
    }
    const bool Own = Card.value("owner", -1) == Seat;
    Details->AddSlot().AutoHeight()[Label(Text(Card.value("name",std::string("Punk"))),15,Sand)];
    FString State = Own ? TEXT("YOUR CARD") : TEXT("ENEMY CARD");
    if (Card.value("zone", std::string()) == "board")
    {
        State += Card.value("destroyed", false) ? TEXT(" · BURNED OUT") : Card.value("damage", 0) > 0 ? TEXT(" · DAMAGED") : TEXT(" · UNDAMAGED");
        if (!Card.value("destroyed", false)) State += Card.value("protected", false) ? TEXT(" · COVERED") : TEXT(" · EXPOSED");
        if (!Card.value("destroyed", false)) State += TEXT("\n")+OldWestReadiness::Label(Card).ToUpper();
    }
    Details->AddSlot().AutoHeight().Padding(0, 4)[Label(State, 12, Sand)];
    // Keep optional history reachable before long rules or private-peek text.
    Details->AddSlot().AutoHeight().HAlign(HAlign_Left).Padding(0,2,0,2)[AssetHistoryControl(Card,true)];
    auto AddDefinition = [&](const std::string& Id)
    {
        const J* Definition = CardDefinition(Id);
        if (!Definition) return;
        const J& Def = *Definition;
        FString Meta = OldWestDisplay::TypeLabel(Def.value("type", std::string())).ToUpper();
        if (Def.contains("play_cost")) Meta += FString::Printf(TEXT(" · PLAY %d WHISKEY"),
            Card.contains("play_availability")?Card["play_availability"].value("cost",0):Def.value("play_cost",0));
        if (Def.contains("starting_cards")) Meta += FString::Printf(TEXT(" · %d STARTING CARDS"), Def.value("starting_cards", 0));
        if (Def.contains("event_delay")) Meta += Def.value("event_delay", 0) == 0 ? TEXT(" · IMMEDIATE") : FString::Printf(TEXT(" · DELAY %d"), Def.value("event_delay", 0));
        Details->AddSlot().AutoHeight().Padding(0, 4)[Label(Meta, 12, Sand)];
        const FString Trait = Text(Def.value("trait", std::string()));
        if (!Trait.IsEmpty())
        {
            Details->AddSlot().AutoHeight().Padding(0, 6, 0, 2)[Label(TEXT("TRAIT"), 12, Sand)];
            Details->AddSlot().AutoHeight()[Label(Trait, 13)];
        }
        if (Def.contains("effect")) Details->AddSlot().AutoHeight().Padding(0, 10)[Label(Text(Def["effect"]), 13)];
        for (const auto& Ability : Def["abilities"])
        {
            Details->AddSlot().AutoHeight().Padding(0, 6, 0, 2)[Label(FString::Printf(TEXT("ABILITY · %d WHISKEY"), Ability.value("cost", 0)), 12, Sand)];
            Details->AddSlot().AutoHeight()[Label(Text(Ability.value("effect", std::string())), 13)];
        }
        if (Def.contains("junk")) Details->AddSlot().AutoHeight().Padding(0, 6)[Label(OldWestDisplay::Text(TEXT("JUNK · ") + Text(Def["junk"])).ToUpper(), 13, Sand)];
    };
    if (Card.value("punk", false))
    {
        Details->AddSlot().AutoHeight().Padding(0, 4)[Label(TEXT("A drifter is a crew member. Its first hit destroys it. It covers the cards behind it and may gain abilities from your other cards."), 13)];
        // Only owner-authorized information is consumed; the public actor stays Punk.
        if (Own && Card.contains("private_peek"))
        {
            const J& Peek = Card["private_peek"];
            Details->AddSlot().AutoHeight().Padding(0, 18, 0, 6)[Label(TEXT("WANTED POSTER BOARD · PRIVATE INSPECTION"), 12, Sand)];
            Details->AddSlot().AutoHeight()[Label(Text(Peek.value("name", std::string())), 15, Sand)];
            if(Peek.contains("flip_cost"))Details->AddSlot().AutoHeight().Padding(0,4)[Label(FString::Printf(TEXT("FLIP · %d WHISKEY"),Peek.value("flip_cost",0)),13,Sand)];
            Details->AddSlot().AutoHeight().Padding(0, 6)[Label(Peek.value("flip_available",false)
                ? TEXT("Choose Flip in Your Actions to enter play here, ready.")
                : Text(Peek.value("flip_reason",std::string())),13)];
            AddDefinition(Peek.value("card_id", std::string()));
        }
    }
    else AddDefinition(Card.value("card_id", std::string()));
    return Details;
}

TSharedRef<SWidget> SOldWestHUD::RulesHelp(const std::string& Ruleset)
{
    RulesVisibleCards=J::array();
    TSharedRef<SVerticalBox> Help = SNew(SVerticalBox);
    Help->AddSlot().AutoHeight()[Label(TEXT("RULES & CARD GUIDE"),20,Sand)];
    Help->AddSlot().AutoHeight().Padding(0,6)[Label(Text(RulesContent.value("basis",std::string("Offline rules reference unavailable."))),14)];
    auto Search=SNew(SEditableTextBox).Text(FText::FromString(RulesQuery))
        .HintText(FText::FromString(TEXT("Search rules or cards · press Enter")))
        .OnTextCommitted_Lambda([this](const FText& Query,ETextCommit::Type How){if(How==ETextCommit::OnEnter){RulesQuery=Query.ToString();Dirty=true;}});
    Help->AddSlot().AutoHeight()[Search];
#if !UE_BUILD_SHIPPING
    StatusButtons.Emplace(TEXT("rules_search"),Search);
#endif
    auto Tabs=SNew(SHorizontalBox);
    for(const FString& Category:{FString(TEXT("Rules")),FString(TEXT("People")),FString(TEXT("Camps")),FString(TEXT("Events")),FString(TEXT("Special"))})
    {
        auto Tab=Button(OldWestDisplay::Text(Category),[this,Category](){RulesCategory=Category;Dirty=true;});
        Tabs->AddSlot().AutoWidth().Padding(3,6)[Tab];
#if !UE_BUILD_SHIPPING
        StatusButtons.Emplace(TEXT("rules_tab:")+Category,Tab);
#endif
    }
    Tabs->AddSlot().AutoWidth().Padding(12,6)[Button(RulesAllCards?TEXT("ALL CURRENT CARDS"):TEXT("ACTIVE RULESET"),[this](){RulesAllCards=!RulesAllCards;Dirty=true;})];
    Help->AddSlot().AutoHeight()[Tabs];
    TSharedRef<SScrollBox> Rules = SNew(SScrollBox);
    int32 Matches=0;
    if(RulesCategory==TEXT("Rules")) {
        for(const auto& Section:RulesContent.value("sections",J::array())) {
            const FString Title=Text(Section["title"]),Body=StripCitations(Text(Section["text"]));
            if(!RulesQuery.IsEmpty()&&!(Title+Body).Contains(RulesQuery))continue;
            Rules->AddSlot().Padding(0,10)[Label(Title,20,Sand)];
            Rules->AddSlot().Padding(0,4)[Label(Body,16)];++Matches;
        }
    } else for(const auto& Card:Catalog["cards"]) {
        const std::string Type=Card.value("type",std::string());
        const bool Special=Card.value("id",std::string())=="stampede"||Card.value("id",std::string())=="hip_flask";
        if(RulesCategory==TEXT("Special")?!Special:Special)continue;
        if(RulesCategory==TEXT("People")&&Type!="person")continue;
        if(RulesCategory==TEXT("Camps")&&Type!="camp")continue;
        if(RulesCategory==TEXT("Events")&&Type!="event")continue;
        if(!RulesAllCards&&Type=="camp"&&Catalog.contains("rulesets")&&Catalog["rulesets"].contains(Ruleset)) {
            bool Included=false;for(const auto& Id:Catalog["rulesets"][Ruleset]["camp_ids"])if(Id==Card["id"])Included=true;
            if(!Included)continue;
        }
        FString Explanation;
        for(const auto& Entry:RulesContent.value("cards",J::array()))if(Entry["id"]==Card["id"])Explanation=StripCitations(Text(Entry["explanation"]));
        const FString Name=Text(Card["name"]),Printed=CardDescription(Card["id"]);
        if(!RulesQuery.IsEmpty()&&!(Name+Printed+Explanation).Contains(RulesQuery))continue;
        RulesVisibleCards.push_back(Card["id"]);
        FString Metadata=Text(Type);
        if(Card.contains("play_cost"))Metadata+=FString::Printf(TEXT(" · Play %d whiskey"),Card.value("play_cost",0));
        if(Card.contains("starting_cards"))Metadata+=FString::Printf(TEXT(" · Starting cards %d"),Card.value("starting_cards",0));
        if(Card.contains("event_delay"))Metadata+=FString::Printf(TEXT(" · Delay %d"),Card.value("event_delay",0));
        Rules->AddSlot().Padding(0,12,0,4)[Label(Name,20,Sand)];
        Rules->AddSlot()[Label(Metadata,14,Sand)];
        Rules->AddSlot().Padding(0,6)[Label(Printed,16)];
        Rules->AddSlot().Padding(0,6)[Label(Explanation,16)];++Matches;
    }
    if(!Matches)Rules->AddSlot().Padding(0,12)[Label(TEXT("No matching entries in this section."),16)];
    if (RulesCategory==TEXT("Rules") && Catalog.contains("rulesets") && Catalog["rulesets"].contains(Ruleset) && Catalog["rulesets"][Ruleset].contains("confirmed_rulings"))
    {
        Rules->AddSlot().Padding(0, 18)[Label(TEXT("DESIGNER CLARIFICATIONS"), 20, Sand)];
        for (const auto& Ruling : Catalog["rulesets"][Ruleset]["confirmed_rulings"].items())
            Rules->AddSlot().Padding(0, 8)[Label(Text(Ruling.value()), 16)];
    }
    if (RulesCategory==TEXT("Rules") && Catalog.contains("rulesets") && Catalog["rulesets"].contains(Ruleset) && Catalog["rulesets"][Ruleset].contains("interpretation_policy"))
    {
        Rules->AddSlot().Padding(0, 18)[Label(TEXT("DECLARED MATCH RULINGS"), 20, Sand)];
        for (const auto& Policy : Catalog["rulesets"][Ruleset]["interpretation_policy"].items())
            Rules->AddSlot().Padding(0, 8)[Label(Text(Policy.value()), 16)];
    }
    Help->AddSlot().FillHeight(1.f).Padding(0, 12)[Rules];
    Help->AddSlot().AutoHeight()[Button(TEXT("BACK TO THE GAME"), [this]() { HelpOpen = false; Dirty = true; }, FString(), true, true)];
    return SNew(SBorder).BorderImage(FCoreStyle::Get().GetBrush("WhiteBrush")).BorderBackgroundColor(Panel).Padding(28)[Help];
}
void SOldWestHUD::Send(const J& Command)
{
    if (Owner.IsValid()) Owner->Submit(Text(Command.dump()));
    SelectedSource = 0;
    Dirty = true;
}
TSharedRef<SWidget> SOldWestHUD::CampSelection(const J& Player)
{
    TSharedRef<SVerticalBox> Box = SNew(SVerticalBox);
    Box->AddSlot().AutoHeight().Padding(0, 10)[Label(TEXT("CHOOSE YOUR THREE HOLDINGS"), 28, Sand)];
    Box->AddSlot().AutoHeight().Padding(0, 4)[Label(TEXT("Select them in left-to-right order. Their supply values determine your opening hand."), 16)];
    Box->AddSlot().AutoHeight().HAlign(HAlign_Left)[Button(TEXT("READY FOR THE TERRITORY"), [this]() {
        J Ids = J::array(); for (const FString& Id : ChosenCamps) Ids.push_back(std::string(TCHAR_TO_UTF8(*Id)));
        Send({{"type", "select_camps"}, {"camps", Ids}}); ChosenCamps.Empty();
    }, FString(), ChosenCamps.Num() == 3)];
    TSharedRef<SUniformGridPanel> Camps = SNew(SUniformGridPanel).SlotPadding(FMargin(6.f));
    int32 CardIndex = 0;
    if (Player.contains("offers")) for (const auto& Card : Player["offers"])
    {
        const FString Id = Text(Card["id"]);
        const int32 Index = ChosenCamps.Find(Id);
        TSharedRef<SVerticalBox> CampFace = SNew(SVerticalBox);
        CampFace->AddSlot().AutoHeight()[AnimatedCard(Card, 170.f)];
        CampFace->AddSlot().AutoHeight().Padding(10,3)[SNew(STextBlock).Text(FText::FromString(CardDescription(Card["id"])))
            .Font(FCoreStyle::GetDefaultFontStyle("Regular",14)).ColorAndOpacity(Sand).WrapTextAt(480.f)];
        if (Index != INDEX_NONE) CampFace->AddSlot().AutoHeight().Padding(10,2)[Label(FString::Printf(TEXT("SELECTED · HOLDING %d"),Index+1),14, FLinearColor(0.2f,0.9f,0.65f))];
        TSharedRef<SWidget> Option = SNew(SButton).ContentPadding(3)
            .OnClicked_Lambda([this,Id]() { if (ChosenCamps.Contains(Id)) ChosenCamps.Remove(Id); else if (ChosenCamps.Num()<3) ChosenCamps.Add(Id); Dirty=true; return FReply::Handled(); })[CampFace];
        Camps->AddSlot(CardIndex % 3, CardIndex / 3)[SNew(SBox).WidthOverride(530).MinDesiredHeight(140)[Option]];
#if !UE_BUILD_SHIPPING
        CampOptionButtons.Emplace(Id, Option);
#endif
        ++CardIndex;
    }
    Box->AddSlot().FillHeight(1.f).Padding(0, 6)[SNew(SScaleBox).Stretch(EStretch::ScaleToFit).StretchDirection(EStretchDirection::DownOnly)[Camps]];
    return SNew(SBorder).BorderImage(FCoreStyle::Get().GetBrush("WhiteBrush")).BorderBackgroundColor(Panel).Padding(24)[Box];
}
void SOldWestHUD::Rebuild()
{
    PanelDropSurfaces.Reset();
    FieldSurfaces.Reset();
    SectionBodies.Reset();
#if !UE_BUILD_SHIPPING
    ++LayoutGeneration;
#endif
    if (!Owner.IsValid() || !Root.IsValid()) return;
    Dirty = false;
    SeenGeneration = Owner->GetViewGeneration();
    Root->ClearChildren();
    SceneHitArea.Reset();
    Workspace.Reset();
    MatchEndPanel.Reset();
    DockPanels.Reset();
    CardHoverTargets.Reset();
#if !UE_BUILD_SHIPPING
    InviteButtons.Reset();
    CampOptionButtons.Reset();
    SoloButtons.Reset();
    HandCards.Reset();
    FieldButtons.Reset();
    StatusButtons.Reset();
    SectionButtons.Reset();
    MasterTabs.Reset(); MasterCards.Reset(); FormationSlots.Reset(); MasterActionButtons.Reset();
    RosterLanes.Reset();
    PlacementDragButtons.Reset();
    GalleryWidgets.Reset();
    CameraButtons.Reset();
    OverviewCards.Reset();
#endif
    PendingChoice = false;
    MasterActionsVisible = false;
    J Data;
    try { Data = J::parse(TCHAR_TO_UTF8(*Owner->GetPresentationSnapshot())); } catch (const std::exception&) { Data = {{"hosted", false}}; }
    BattlefieldReadiness.Reset();
    DiscardChoiceCards.Reset();
    for(const auto& Action:Data.value("actions",J::array()))
        if(Action.value("discard_choice",false)&&Action.value("target",0)>0)
            DiscardChoiceCards.Add(Action["target"].get<int32>());
    if(Data.contains("view")&&Data["view"].is_object()&&Data["view"].contains("players"))for(const auto& Player:Data["view"]["players"])
        for(const auto& Column:Player["columns"])for(const auto& Card:Column)
            BattlefieldReadiness.Add(Card.value("id",0),OldWestReadiness::State(Card));
    const bool Hosted = Data.value("hosted", false);
    const FString LeaveMatchId = Text(Data.value("match_id", std::string()));
    if (!Hosted || LeaveConfirmationMatch != LeaveMatchId) LeaveConfirmationMatch.Reset();
    const bool SinglePlayer = Data.value("mode", std::string()) == "single_player";
    if (Hosted && Data.contains("view"))
    {
        const J& CurrentView = Data["view"];
        PendingChoice = !CurrentView["choice"].is_null() &&
            CurrentView["choice"].value("player", -1) == Data.value("seat", 0);
        // Announce each actual owner choice once. A user may then reopen
        // Overview until they explicitly return; unrelated rebuilds must not
        // override that inspection. Keep the exact local choice shape (owner,
        // prompt/options/kind if present), revision and match in its identity.
        const FString Identity = PendingChoice ? Text(J{{"match_id", Data.value("match_id", std::string())},
            {"revision", CurrentView.value("revision", -1)}, {"choice", CurrentView["choice"]}}.dump()) : FString();
        if (PendingChoice && Identity != LastAnnouncedChoiceIdentity && OverviewOpen)
        {
            OverviewOpen = false;
            Owner->SetOverviewCamera(false);
        }
        LastAnnouncedChoiceIdentity = Identity;
    }
    else LastAnnouncedChoiceIdentity.Reset();
    TSharedRef<SHorizontalBox> Header = SNew(SHorizontalBox);
    Header->AddSlot().FillWidth(1.f).VAlign(VAlign_Center)[Label(TEXT("BATTLE OF THE OLD WEST"), 18, Sand)];
    if(Hosted)
    {
        TSharedRef<SWidget> PlanToggle=Button(BattlePlanOpen?TEXT("HIDE BATTLE PLAN"):TEXT("BATTLE PLAN"),[this](){BattlePlanOpen=!BattlePlanOpen;Dirty=true;});
        Header->AddSlot().AutoWidth().Padding(6,0)[PlanToggle];
#if !UE_BUILD_SHIPPING
        CameraButtons.Emplace(TEXT("battle_plan"),PlanToggle);
#endif
        TSharedRef<SWidget> OverviewButton=Button(OverviewOpen?TEXT("CLOSE OVERVIEW · G"):TEXT("ABILITY OVERVIEW · G"),[this](){ToggleBattleOverview();},TEXT("Compare both outfits, every crew member and every holding ability"));
        Header->AddSlot().AutoWidth().Padding(6,0)[OverviewButton];
        TSharedRef<SWidget> ResetPanels=Button(TEXT("RESET PANELS"),[this](){ResetPanelLayout();},TEXT("Restore panel positions, sizes and expanded state"));
        Header->AddSlot().AutoWidth().Padding(6,0)[ResetPanels];
#if !UE_BUILD_SHIPPING
        CameraButtons.Emplace(TEXT("ability_overview"),OverviewButton);
        CameraButtons.Emplace(TEXT("reset_panels"),ResetPanels);
#endif
    }
    if (Hosted && Data.contains("view"))
    {
        const FString CurrentMatch = Text(Data.value("match_id", std::string()));
        const std::string CurrentStatus = Data["view"].value("status", std::string());
        const bool Finished = CurrentStatus == "won" || CurrentStatus == "draw";
        if (Finished || NewGameConfirmationMatch != CurrentMatch) NewGameConfirmationMatch.Reset();
        auto NewGame = Button(TEXT("NEW GAME"), [this, CurrentMatch, Finished]() {
            if (Finished) { if (Owner.IsValid()) Owner->ServerNewGame(CurrentMatch); }
            else NewGameConfirmationMatch = CurrentMatch;
            Dirty = true;
        });
        Header->AddSlot().AutoWidth().Padding(6,0)[NewGame];
#if !UE_BUILD_SHIPPING
        CameraButtons.Emplace(TEXT("new_game"),NewGame);
#endif
    }
    Header->AddSlot().AutoWidth().Padding(8, 0)[Button(SettingsOpen ? TEXT("CLOSE SETTINGS") : TEXT("SETTINGS"),
        [this]() { if (SettingsOpen) CloseSettings(); else OpenSettings(); }, FString(), true, SettingsOpen)];
    Header->AddSlot().AutoWidth().Padding(8, 0)[Button(HelpOpen ? TEXT("CLOSE RULES") : TEXT("RULES"), [this]() {
        if (SettingsOpen) CloseSettings();
        HelpOpen = !HelpOpen;
        Dirty = true;
    }, FString(), true, HelpOpen)];
    Header->AddSlot().AutoWidth().Padding(8, 0)[Button(TEXT("CAMERA · TAB"), [this]() { if (Owner.IsValid()) Owner->ToggleCamera(); })];
    TSharedRef<SWidget> ResetView = Button(TEXT("RESET VIEW"), [this]() { if (Owner.IsValid()) Owner->ResetBattlefieldCamera(); });
    Header->AddSlot().AutoWidth().Padding(4,0)[ResetView];
#if !UE_BUILD_SHIPPING
    CameraButtons.Emplace(TEXT("reset_view"),ResetView);
#endif
    if (Hosted) Header->AddSlot().AutoWidth()[Button(TEXT("LEAVE"), [this, LeaveMatchId]() {
        LeaveConfirmationMatch = LeaveMatchId;
        NewGameConfirmationMatch.Reset();
        Dirty = true;
    }, TEXT("Ask to leave this match"), true, true)];
    Root->AddSlot().AutoHeight()[SNew(SBorder).BorderImage(FCoreStyle::Get().GetBrush("WhiteBrush"))
        .BorderBackgroundColor(Panel).Padding(FMargin(14,6))[Header]];
    if (!LeaveConfirmationMatch.IsEmpty())
    {
        const FString ConfirmMatch = LeaveConfirmationMatch;
        auto Confirm = SNew(SHorizontalBox);
        Confirm->AddSlot().AutoWidth().VAlign(VAlign_Center).Padding(14,0)[Label(TEXT("Leave match?"),18,Sand)];
        Confirm->AddSlot().AutoWidth()[Button(TEXT("STAY"),[this]() { LeaveConfirmationMatch.Reset(); Dirty=true; })];
        Confirm->AddSlot().AutoWidth().Padding(12,0)[Button(TEXT("CONFIRM LEAVE"),[this,ConfirmMatch]() {
            if (LeaveConfirmationMatch != ConfirmMatch || !Owner.IsValid()) return;
            LeaveConfirmationMatch.Reset();
            Dirty=true;
            try {
                const J Current = J::parse(TCHAR_TO_UTF8(*Owner->GetPresentationSnapshot()));
                if (Current.value("hosted",false) && Text(Current.value("match_id",std::string())) == ConfirmMatch)
                    Owner->LeaveMatch();
            } catch (const std::exception&) { }
        }, FString(), true, true)];
        Root->AddSlot().AutoHeight().Padding(0,6)[SNew(SBorder)
            .BorderImage(FCoreStyle::Get().GetBrush("WhiteBrush")).BorderBackgroundColor(Panel).Padding(10)[Confirm]];
    }
    if (!NewGameConfirmationMatch.IsEmpty() && Hosted)
    {
        const FString ConfirmMatch = NewGameConfirmationMatch;
        auto Confirm = SNew(SHorizontalBox);
        Confirm->AddSlot().FillWidth(1.f).VAlign(VAlign_Center)[Label(TEXT("Starting a new game forfeits this game. Continue?"),18,Sand)];
        auto ConfirmNewGame = Button(TEXT("FORFEIT & NEW GAME"),[this,ConfirmMatch]() {
            NewGameConfirmationMatch.Reset();
            if (Owner.IsValid()) Owner->ServerNewGame(ConfirmMatch);
            Dirty=true;
        });
        Confirm->AddSlot().AutoWidth()[ConfirmNewGame];
#if !UE_BUILD_SHIPPING
        CameraButtons.Emplace(TEXT("confirm_new_game"),ConfirmNewGame);
#endif
        Confirm->AddSlot().AutoWidth()[Button(TEXT("CANCEL"),[this]() {NewGameConfirmationMatch.Reset();Dirty=true;})];
        Root->AddSlot().AutoHeight()[Confirm];
    }
    if (!Owner->GetNotice().IsEmpty())
    {
        auto Notice=SNew(SHorizontalBox);
        Notice->AddSlot().FillWidth(1.f).VAlign(VAlign_Center)[Label(Owner->GetNotice(),18,Sand)];
        TSharedRef<SWidget> Dismiss=Button(TEXT("DISMISS ×"),[this](){Owner->DismissNotice();Dirty=true;});
        Notice->AddSlot().AutoWidth()[Dismiss];
#if !UE_BUILD_SHIPPING
        StatusButtons.Emplace(TEXT("dismiss_notice"),Dismiss);
#endif
        Root->AddSlot().AutoHeight().Padding(0,6)[SNew(SBorder).BorderImage(FCoreStyle::Get().GetBrush("WhiteBrush")).BorderBackgroundColor(Panel).Padding(10)[Notice]];
    }
#if !UE_BUILD_SHIPPING
    if (!GalleryCards.IsEmpty())
    {
        TSharedRef<SUniformGridPanel> Gallery = SNew(SUniformGridPanel).SlotPadding(FMargin(12));
        for (int32 I=0; I<GalleryCards.Num(); ++I)
        {
            const J* Card = CardDefinition(std::string(TCHAR_TO_UTF8(*GalleryCards[I])));
            if (!Card) continue;
            TSharedRef<SWidget> Face = SNew(SBox).WidthOverride(580).HeightOverride(380)[AnimatedCard(*Card,300.f)];
            Gallery->AddSlot(I%3,I/3)[Face];
            GalleryWidgets.Emplace(GalleryCards[I],Face);
        }
        Root->AddSlot().FillHeight(1.f).VAlign(VAlign_Center)[Gallery];
        return;
    }
#endif
    if (SettingsOpen)
    {
        Root->AddSlot().FillHeight(1.f).VAlign(VAlign_Center).HAlign(HAlign_Center).Padding(0, 18)
            [SNew(SBox).WidthOverride(1160.f)[SettingsPanel()]];
        return;
    }
    if (HelpOpen)
    {
        const std::string Ruleset = Data.contains("view") ? Data["view"].value("ruleset", std::string("base_2024")) : IncludeExpansion ? "boomtown" : "base_2024";
        Root->AddSlot().FillHeight(1.f).Padding(0, 18).HAlign(HAlign_Center)[SNew(SBox).WidthOverride(1280.f)[RulesHelp(Ruleset)]];
        return;
    }
    if (!Hosted)
    {
        InspectedCard = 0; SelectedSource = 0; WarRoomOpen=false; InspectorSide = -1; OverviewOpen=false;HistoryOpen=false;BattleScrollOffsets.Reset();
        TSharedRef<SVerticalBox> Menu = SNew(SVerticalBox);
        Menu->AddSlot().AutoHeight().Padding(0, 10)[Label(TEXT("EVERY HOLDING IS WORTH FIGHTING FOR."), 28, Sand)];
        Menu->AddSlot().AutoHeight().Padding(0, 8)[Label(TEXT("Two rival outfits. One territory.\nFace the AI, or challenge a friend."), 18)];
        auto MenuControl = [this](const FString& Id, TSharedRef<SWidget> Widget) {
#if !UE_BUILD_SHIPPING
            SoloButtons.Emplace(Id, Widget);
#endif
            return Widget;
        };
        Menu->AddSlot().AutoHeight().Padding(0, 10)[SNew(SEditableTextBox).Text(FText::FromString(Address))
            .HintText(FText::FromString(TEXT("Host address : port"))).Font(FCoreStyle::GetDefaultFontStyle("Regular", 20))
            .OnTextChanged_Lambda([this](const FText& NewText) { Address = NewText.ToString(); })];
        Menu->AddSlot().AutoHeight()[Button(TEXT("JOIN MATCH"), [this]() { if (Owner.IsValid()) Owner->JoinMatch(Address); })];
        TSharedRef<SHorizontalBox> Sets = SNew(SHorizontalBox);
        Sets->AddSlot().FillWidth(1.f).Padding(0, 0, 6, 0)[MenuControl(TEXT("base_2024"), Button(IncludeExpansion ? TEXT("BASE GAME") : TEXT("BASE GAME · SELECTED"),
            [this]() { IncludeExpansion = false; Dirty = true; }))];
        Sets->AddSlot().FillWidth(1.f)[MenuControl(TEXT("boomtown"), Button(IncludeExpansion ? TEXT("+ BOOMTOWN · SELECTED") : TEXT("+ BOOMTOWN"),
            [this]() { IncludeExpansion = true; Dirty = true; }))];
        Menu->AddSlot().AutoHeight().Padding(0, 10)[Sets];
        TSharedRef<SHorizontalBox> Difficulties = SNew(SHorizontalBox);
        for (const FString& Difficulty : {FString(TEXT("easy")), FString(TEXT("normal")), FString(TEXT("hard"))})
        {
            const FString Caption = Difficulty.ToUpper() + (SelectedDifficulty == Difficulty ? TEXT(" · SELECTED") : TEXT(""));
            Difficulties->AddSlot().FillWidth(1.f).Padding(0, 0, 6, 0)[MenuControl(Difficulty, Button(Caption,
                [this, Difficulty]() { SelectedDifficulty = Difficulty; Dirty = true; }))];
        }
        Menu->AddSlot().AutoHeight().Padding(0, 8)[Difficulties];
        const FString DifficultyHint = SelectedDifficulty == TEXT("easy") ? TEXT("EASY · A forgiving opponent while you learn.")
            : SelectedDifficulty == TEXT("hard") ? TEXT("HARD · Plans attack sequences and holding combinations.")
            : TEXT("NORMAL · Balances attacks, defense, and whiskey.");
        Menu->AddSlot().AutoHeight().Padding(0, 4)[Label(DifficultyHint, 17, Sand)];
        Menu->AddSlot().AutoHeight().Padding(0, 10)[MenuControl(TEXT("play_single_player"), Button(TEXT("PLAY SINGLE PLAYER"), [this]() {
            if (Owner.IsValid()) Owner->StartSinglePlayer(IncludeExpansion ? TEXT("boomtown") : TEXT("base_2024"), SelectedDifficulty); }))];
        Menu->AddSlot().AutoHeight().Padding(0,14,0,2)[Label(TEXT("PLAY WITH A FRIEND"),18,Sand)];
        Menu->AddSlot().AutoHeight().Padding(0, 10)[Button(TEXT("HOST A MATCH"), [this]() {
            if (Owner.IsValid()) Owner->HostMatch(IncludeExpansion ? TEXT("boomtown") : TEXT("base_2024")); })];
        Menu->AddSlot().AutoHeight().Padding(0,8)[Label(TEXT("Both players need the same game build. Internet play needs a reachable VPN address, or a public address with router/firewall access to the host's UDP game port."),16)];
        Menu->AddSlot().AutoHeight().Padding(0, 12, 0, 0)[Button(TEXT("QUIT"), [this]() { if (Owner.IsValid()) Owner->QuitGame(); }, FString(), true, true)];
        Root->AddSlot().FillHeight(1.f).VAlign(VAlign_Center).HAlign(HAlign_Left)
            [SNew(SBox).WidthOverride(800)[SNew(SBorder).BorderImage(FCoreStyle::Get().GetBrush("WhiteBrush")).BorderBackgroundColor(Panel).Padding(28)[Menu]]];
        return;
    }
    if (!Data.contains("view")) return;
    const J& View = Data["view"];
    const int32 Seat = Data.value("seat", 0);
    const J& Mine = View["players"][Seat];
    const J& Other = View["players"][1-Seat];
    const std::string Status = View.value("status", std::string());
    FString TurnLabel = View.value("active_player", -1) == Seat ? TEXT("YOUR TURN") : SinglePlayer ? TEXT("AI'S TURN") : TEXT("OPPONENT'S TURN");
    if (Status == "selection") TurnLabel = TEXT("PREPARE YOUR HOLDINGS");
    if (Data.value("connected", 0) < 2) TurnLabel = TEXT("WAITING FOR THE OTHER PLAYER");
    if (Status == "won" || Status == "draw") TurnLabel = TEXT("MATCH COMPLETE");
    if (SinglePlayer) TurnLabel += TEXT(" · AI ") + Text(Data.value("ai_difficulty", std::string("normal"))).ToUpper();
    auto TurnStrip=SNew(SHorizontalBox);
    TurnStrip->AddSlot().FillWidth(1.f).VAlign(VAlign_Center)[Label(FString::Printf(TEXT("%s   ·   TURN %d"),*TurnLabel,View.value("turn",0)),16,Sand)];
    if(SinglePlayer)
    {
        TurnStrip->AddSlot().AutoWidth().VAlign(VAlign_Center).Padding(10,0)[SNew(STextBlock).Text_Lambda([this](){return FText::FromString(FString::Printf(TEXT("ENEMY SPEED  %.2fx"),Preferences()?Preferences()->GetEnemySpeed():.5f));}).Font(FCoreStyle::GetDefaultFontStyle("Regular",16)).ColorAndOpacity(Sand)];
        TSharedRef<SWidget> SpeedSlider=SNew(SSlider).MinValue(.25f).MaxValue(2.f).StepSize(.25f)
            .Value_Lambda([this](){return Preferences()?Preferences()->GetEnemySpeed():.5f;})
            .OnValueChanged_Lambda([this](float Value){if(Preferences())Preferences()->SetEnemySpeed(Value);});
        TurnStrip->AddSlot().AutoWidth().VAlign(VAlign_Center)[SNew(SBox).WidthOverride(220)[SpeedSlider]];
#if !UE_BUILD_SHIPPING
        StatusButtons.Emplace(TEXT("enemy_speed"),SpeedSlider);
#endif
    }
    Root->AddSlot().AutoHeight().Padding(0,3)[SNew(SBorder).BorderImage(FCoreStyle::Get().GetBrush("WhiteBrush")).BorderBackgroundColor(Panel).Padding(FMargin(14,6))[TurnStrip]];
    if (Data.value("connected", 0) < 2)
    {
        const TArray<FString> Addresses = OldWestNetworkAddresses::GetLocalListenAddresses(Owner->GetWorld());
        if (!Addresses.IsEmpty())
        {
            TSharedRef<SVerticalBox> Invite = SNew(SVerticalBox);
            Invite->AddSlot().AutoHeight().Padding(0, 0, 0, 8)[Label(TEXT("SUGGESTED LAN JOIN ADDRESSES"), 18, Sand)];
            TSharedRef<SWrapBox> Endpoints = SNew(SWrapBox).UseAllottedSize(true).InnerSlotPadding(FVector2D(8, 8));
            for (const FString& Endpoint : Addresses)
            {
                TSharedRef<SWidget> Copy = Button(Endpoint + TEXT(" · COPY"), [Endpoint]() {
                    FPlatformApplicationMisc::ClipboardCopy(*Endpoint);
                });
                Endpoints->AddSlot()[Copy];
#if !UE_BUILD_SHIPPING
                InviteButtons.Emplace(Endpoint, Copy);
#endif
            }
            Invite->AddSlot().AutoHeight()[Endpoints];
            Invite->AddSlot().AutoHeight().Padding(0,6,0,0)[Label(TEXT("Choose the address on your shared Ethernet or Wi-Fi network. Internet guests need a reachable VPN or public address; this list does not discover it."),16)];
            Root->AddSlot().AutoHeight().Padding(0, 0, 0, 8)[Invite];
        }
    }
    if(Status!="selection") {
        auto Navigation=SNew(SHorizontalBox);
        auto Nav=[this,Navigation](const FString& Id,const FString& Caption,float OX,float OY,float PX,float PY,float Zoom,float Elevation=0.f) {
            auto Control=Button(Caption,[this,OX,OY,PX,PY,Zoom,Elevation](){if(Owner.IsValid())Owner->NavigateBattlefieldCamera(OX,OY,PX,PY,Zoom,Elevation);});
            Navigation->AddSlot().AutoWidth().Padding(2,0)[Control];
#if !UE_BUILD_SHIPPING
            CameraButtons.Emplace(Id,Control);
#endif
        };
        auto TextToggle=Button(BattlefieldTextVisible?TEXT("TEXT: ON"):TEXT("TEXT: OFF"),[this](){
            BattlefieldTextVisible=!BattlefieldTextVisible;Dirty=true;
            if(Staging.IsValid())Staging->SetTextVisible(BattlefieldTextVisible&&SceneControlsVisible());
        },TEXT("Show or hide all battlefield names, signs, lane numbers and hover text"));
        Navigation->AddSlot().AutoWidth().Padding(2,0)[TextToggle];
#if !UE_BUILD_SHIPPING
        CameraButtons.Emplace(TEXT("battlefield_text"),TextToggle);
#endif
        Nav(TEXT("zoom_in"),TEXT("ZOOM +"),0,0,0,0,1);
        Nav(TEXT("zoom_out"),TEXT("ZOOM −"),0,0,0,0,-1);
        Nav(TEXT("pan_left"),TEXT("PAN ←"),0,0,100,0,0);
        Nav(TEXT("pan_right"),TEXT("→"),0,0,-100,0,0);
        Nav(TEXT("pan_up"),TEXT("↑"),0,0,0,100,0);
        Nav(TEXT("pan_down"),TEXT("↓"),0,0,0,-100,0);
        Nav(TEXT("height_up"),TEXT("HEIGHT +"),0,0,0,0,0,100);
        Nav(TEXT("height_down"),TEXT("−"),0,0,0,0,0,-100);
        Nav(TEXT("orbit_left"),TEXT("ROTATE ↶"),60,0,0,0,0);
        Nav(TEXT("orbit_right"),TEXT("↷"),-60,0,0,0,0);
        Nav(TEXT("tilt_up"),TEXT("TILT +"),0,60,0,0,0);
        Nav(TEXT("tilt_down"),TEXT("−"),0,-60,0,0,0);
        Navigation->AddSlot().AutoWidth().VAlign(VAlign_Center).Padding(12,0)[
            SNew(SBorder).BorderImage(FCoreStyle::Get().GetBrush("WhiteBrush"))
            .BorderBackgroundColor(FLinearColor(.018f,.027f,.029f,.92f)).Padding(FMargin(6,3))[
                Label(TEXT("Wheel: zoom · Right-drag: rotate · Middle / Shift-right: pan · Ctrl-drag: height"),11,Sand)]];
        Root->AddSlot().AutoHeight()[Navigation];
    }
    if (Status == "selection")
    {
        Root->AddSlot().FillHeight(1.f).Padding(0, 12)[Mine.value("selected", false)
            ? Label(TEXT("HOLDINGS LOCKED. WAITING FOR YOUR OPPONENT."), 26, Sand) : CampSelection(Mine)];
        return;
    }
    if (Status == "won" || Status == "draw")
    {
        const FString Result = Status == "draw" ? TEXT("THE TERRITORY WINS · DRAW") : View.value("winner", -1) == Seat ? TEXT("VICTORY") : TEXT("DEFEAT");
        Root->AddSlot().AutoHeight().Padding(14,6)[Label(Result + TEXT(" · Inspect the battlefield or open Battle Plan for history."),18,Sand)];
        if (!SinglePlayer && Data.contains("rematch_votes") && Data["rematch_votes"][Seat].get<bool>())
            Root->AddSlot().AutoHeight()[Label(TEXT("New game requested. Waiting for the other player."))];
    }
    const FString FieldMatch=Text(Data.value("match_id",std::string()));
    if(FieldMatch!=FramedFieldMatch){FramedFieldMatch=FieldMatch;FrameFieldPending=true;}
    TSharedRef<SOverlay> BattleSpace=SNew(SOverlay);
    Workspace=BattleSpace;
    BattleSpace->AddSlot()[SAssignNew(SceneHitArea,SBox)];

    if(!BattlePlanOpen&&InspectedCard>0)
    {
        J Inspected;
        for(const auto& Player:View["players"])
        {
            for(const auto& Column:Player["columns"])for(const auto& Card:Column)if(Card.value("id",0)==InspectedCard)Inspected=Card;
            for(const auto& Card:Player["queue"])if(!Card.is_null()&&Card.value("id",0)==InspectedCard)Inspected=Card;
        }
        for(const auto& Card:Mine["hand"])if(Card.value("id",0)==InspectedCard)Inspected=Card;
        if(!Inspected.is_null())
        {
            TSharedRef<SWidget> Inspector=SNew(SBox)
                .Visibility_Lambda([this](){return DraggedCard!=INDEX_NONE||!SceneControlsVisible()?EVisibility::Hidden:EVisibility::Visible;})
                [CardInspector(Inspected)];
            FieldSurfaces.Add(Inspector);
            BattleSpace->AddSlot().HAlign(HAlign_Center).VAlign(VAlign_Bottom).Padding(0,0,0,0)[Inspector];
        }
    }
    TSharedRef<SConstraintCanvas> Floating=SNew(SConstraintCanvas).Visibility(EVisibility::SelfHitTestInvisible);
    BattleSpace->AddSlot()[Floating];
    AddDockPanel(Floating,TEXT("field_you"),FText::FromString(TEXT("YOUR INFO · drag / resize")),FVector2D(0,0),FVector2D(280,260),FVector2D(180,120),FieldStatus(Data,false));
    AddDockPanel(Floating,TEXT("field_enemy"),FText::FromString(Status=="won"||Status=="draw"?TEXT("ENEMY INFO"):TEXT("ENEMY / TURN HISTORY")),FVector2D(1584,0),FVector2D(280,360),FVector2D(180,180),FieldStatus(Data,true));

    AddDockPanel(Floating,TEXT("master"),FText::FromString(TEXT("BATTLE PLAN")),FVector2D(1224,8),FVector2D(640,936),FVector2D(360,400),MasterPanel(Data),false,true);
    AddDockPanel(Floating,TEXT("ability_reference"),FText::FromString(TEXT("ABILITIES IN PLAY")),FVector2D(0,270),FVector2D(280,310),FVector2D(220,100),AbilityReference(Data));
    if(WarRoomOpen) {
        TSharedRef<SWidget> Board=SNew(SBox).WidthOverride(720).HeightOverride(440)
            .Visibility_Lambda([this](){return SceneControlsVisible()?EVisibility::Visible:EVisibility::Hidden;})[WarRoom(Data)];
        WarRoomSurface=Board;FieldSurfaces.Add(Board);
        BattleSpace->AddSlot().HAlign(HAlign_Center).VAlign(VAlign_Center)[Board];
    }
    Root->AddSlot().FillHeight(1.f).Padding(0,4)[BattleSpace];
    const FString NextAction=PendingChoice&&!View["choice"].is_null()
        ?Text(View["choice"].value("prompt",std::string()))
        :View.value("active_player",-1)==Seat?TEXT("Play a card, use an ability, or visit the Ledger for all actions.")
        :TEXT("Watch your opponent's actions. Your turn follows.");
    Root->AddSlot().AutoHeight()[SNew(SBorder)
        .Visibility_Lambda([this](){return SceneControlsVisible()?EVisibility::Visible:EVisibility::Hidden;})
        .BorderImage(FCoreStyle::Get().GetBrush("WhiteBrush"))
        .BorderBackgroundColor(FLinearColor(.075f,.045f,.008f,1)).Padding(12,8)
        [Label(TEXT("NEXT ACTION · ")+NextAction,16,FLinearColor(1.f,.83f,.25f,1))]];

    AddDockPanel(Floating,TEXT("overview"),FText::FromString(TEXT("BATTLE OVERVIEW · G to return")),FVector2D(0,4),FVector2D(1864,908),FVector2D(1540,850),BattleOverview(Data),true);
}
