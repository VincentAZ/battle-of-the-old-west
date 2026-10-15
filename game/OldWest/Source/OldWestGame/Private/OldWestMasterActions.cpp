#include "OldWestCosmetics.h"
#include "OldWestHUD.h"
#include "OldWestHUDIcon.h"
#include "OldWestCardPortrait.h"
#include "OldWestSession.h"
#include "OldWestCardDrag.h"
#include "OldWestTooltip.h"
#include "Widgets/Input/SButton.h"
#include "Widgets/Layout/SBorder.h"
#include "Widgets/Layout/SBox.h"
#include "Widgets/Layout/SScrollBox.h"
#include "Widgets/SBoxPanel.h"
#include "Widgets/Text/STextBlock.h"
#include "OldWestMasterStyle.h"
using J = nlohmann::ordered_json;
using namespace OldWestMasterStyle;
TSharedRef<SWidget> SOldWestHUD::MasterActions(const J& Data)
{
    const J& View=Data["view"];
    const int32 Seat=Data.value("seat",0);
    TSharedRef<SVerticalBox> Controls = SNew(SVerticalBox);
    FString Prompt = View.value("active_player", -1) == Seat ? TEXT("ACTIONS") : TEXT("OPPONENT'S TURN");
    if (!View["choice"].is_null()) Prompt = Text(View["choice"]["prompt"]);
    if(PendingChoice) Controls->AddSlot().AutoHeight().Padding(0,0,0,8)[Label(Prompt,16,Sand)];
    if (SelectedSource != 0 && View["choice"].is_null()) Controls->AddSlot().AutoHeight().Padding(0, 0, 0, 8)[Button(TEXT("ALL ACTIONS"), [this]() { SelectedSource = 0; Dirty = true; }, FString(), true, true)];
    TSharedRef<SWidget> InspectBoard = Button(TEXT("INSPECT BOARD · ESC"), [this]() {
        if (Owner.IsValid()) Owner->SetAnalysisChoiceFramed(false);
    }, TEXT("Keep this choice open while inspecting the board"));
    TSharedRef<SWidget> BackToSamples = Button(TEXT("BACK TO SAMPLES"), [this]() {
        if (!Owner.IsValid()) return;
        if (OverviewOpen) SetBattleOverview(false);
        Owner->SetAnalysisChoiceFramed(true);
    }, TEXT("Return to the current analysis without choosing an effect"));
    Controls->AddSlot().AutoHeight().Padding(0, 0, 0, 6)[SNew(SHorizontalBox)
        .Visibility_Lambda([this]() { return Owner.IsValid() && Owner->HasAnalysisChoiceView()
            ? EVisibility::Visible : EVisibility::Collapsed; })
        +SHorizontalBox::Slot().AutoWidth()[SNew(SBox).Visibility_Lambda([this]() {
            return Owner.IsValid() && Owner->IsAnalysisChoiceFramed() ? EVisibility::Visible : EVisibility::Collapsed;
        })[InspectBoard]]
        +SHorizontalBox::Slot().AutoWidth()[SNew(SBox).Visibility_Lambda([this]() {
            return Owner.IsValid() && Owner->HasAnalysisChoiceView() && !Owner->IsAnalysisChoiceFramed()
                ? EVisibility::Visible : EVisibility::Collapsed;
        })[BackToSamples]]];
#if !UE_BUILD_SHIPPING
    CameraButtons.Emplace(TEXT("inspect_choice_board"), InspectBoard);
    CameraButtons.Emplace(TEXT("back_to_samples"), BackToSamples);
#endif
    TSharedRef<SScrollBox> Actions = SNew(SScrollBox);
    bool MasqueradeSelected=false;
    for(const auto& Column:View["players"][Seat]["columns"])for(const auto& Card:Column)
        if(Card.value("id",0)==SelectedSource&&Card.value("card_id",std::string())=="wanted_poster_board")MasqueradeSelected=true;
    int32 ActionCount = 0;
    TSet<int32> SpatialCards;
    for (const auto& Action : Data["actions"])
    {
        const J Command = Action["command"];
        if (Action.value("category",std::string()) == "play_person") continue;
        const bool EventPlay=Action.value("category",std::string())=="play_event";
        if (Action.contains("placement"))
        {
            const int32 Moving = Action["placement"].value("card",0);
            if (!SpatialCards.Contains(Moving))
            {
                SpatialCards.Add(Moving);
                FString Title = Moving == 0 ? TEXT("DRAG DRIFTER TO THE BATTLEFIELD") : TEXT("DRAG CREW MEMBER TO A NEW SPACE");
                for (const auto& Player : View["players"]) for (const auto& Column : Player["columns"]) for (const auto& C : Column)
                    if (C.value("id",-1) == Moving) Title = TEXT("DRAG ") + Text(C.value("name",std::string())).ToUpper();
                const TWeakPtr<SOldWestHUD> Weak = SharedThis(this);
                TSharedRef<SWidget> DragButton = SNew(SOldWestDragCard).BeginDrag([Weak,Moving]() -> TSharedPtr<FDragDropOperation> {
                    if (auto HUD=Weak.Pin()) return HUD->BeginDeployment(Moving); return nullptr; })
                    [SNew(SBorder).Padding(8).BorderBackgroundColor(FLinearColor(0.04f,0.2f,0.2f,1))
                        [SNew(SHorizontalBox)
                            +SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center).Padding(0,0,10,0)[SNew(SOldWestHUDIcon).Kind(EOldWestHUDIcon::Deploy).Size(36)]
                            +SHorizontalBox::Slot().FillWidth(1.f).VAlign(VAlign_Center)[SNew(STextBlock).Text(FText::FromString(Title)).SimpleTextMode(true)
                                .Font(FCoreStyle::GetDefaultFontStyle("Regular",15)).ColorAndOpacity(Sand).Clipping(EWidgetClipping::ClipToBounds)]]];
                Actions->AddSlot().Padding(0,0,0,4)[DragButton];
#if !UE_BUILD_SHIPPING
                PlacementDragButtons.Emplace(FString::FromInt(Moving),DragButton);
#endif
                ++ActionCount;
            }
            continue;
        }
        const bool Choice = Action["category"] == "choice";
        const bool Flip = Action["category"] == "flip";
        const int32 Id = Command.value("card", Command.value("source", 0));
        if (!Choice && SelectedSource != 0 && Id != SelectedSource && !(Flip&&MasqueradeSelected)) continue;
        if (!Choice && !Flip && !EventPlay && SelectedSource == 0 && Command.contains("card")) continue;
        FString Caption = Text(Action["label"]);
        const std::string Category = Action.value("category", std::string());
        FString Title=Caption,Effect;
        Caption.Split(TEXT(" — "),&Title,&Effect);
        if(Choice&&Action.contains("target_detail"))Effect=Text(Action["target_detail"]);
        Title.RemoveFromStart(TEXT("Use "));
        if(EventPlay)Effect=Action.value("event_slot",0)<0?TEXT("Resolves immediately"):
            FString::Printf(TEXT("Trouble position %d"),Action.value("event_slot",0)+1);
        if(Flip)for(int32 Column=0;Column<3;++Column)for(const auto& Card:View["players"][Seat]["columns"][Column])
            if(Card.value("id",0)==Id&&Card.contains("private_peek")) {
                Title=TEXT("Flip ")+Text(Card["private_peek"].value("name",std::string()));
                Effect=FString::Printf(TEXT("Column %d · enters ready in this space"),Column+1);
            }
        TSharedRef<SVerticalBox> ActionFace=SNew(SVerticalBox);
        TSharedRef<SHorizontalBox> ActionHeading=SNew(SHorizontalBox);
        ActionHeading->AddSlot().FillWidth(1.f)[Label(Title,15,Sand)];
        if(!Choice&&Category!="junk"&&Category!="turn")
            ActionHeading->AddSlot().AutoWidth().Padding(10,0,0,0)[Label(FString::Printf(TEXT("%d whiskey"),Action.value("cost",0)),14,FLinearColor(.28f,.82f,.74f,1))];
        ActionFace->AddSlot().AutoHeight()[ActionHeading];
        if(!Effect.IsEmpty())ActionFace->AddSlot().AutoHeight().Padding(0,4,0,0)[Label(Effect,14,FLinearColor(.64f,.71f,.72f,1))];
        const EOldWestHUDIcon Icon=Category=="turn"?EOldWestHUDIcon::Turn:Category=="draw"||Category=="junk"?EOldWestHUDIcon::Cards:
            EventPlay?EOldWestHUDIcon::Event:Category=="silo"?EOldWestHUDIcon::Water:EOldWestHUDIcon::Attack;
        TSharedRef<SWidget> Graphic=SNew(SOldWestHUDIcon).Kind(Icon).Size(30);
        // Only use cards already present in this player's redacted snapshot.
        J Source=nullptr;
        for(const auto& P:View["players"])for(const auto& Col:P["columns"])for(const auto& C:Col)
            if(C.value("id",0)==Id)Source=C;
        for(const auto& C:View["players"][Seat]["hand"])if(C.value("id",0)==Id)Source=C;
        if(!Source.is_null())Graphic=SNew(SBox).WidthOverride(52).HeightOverride(52)
            [MakeOldWestCardPortrait(Owner->GetWorld(),Source.value("punk",false)?TEXT("punk"):Text(OldWestCosmetics::Visual(Source)),Text(Source.value("type",std::string("person"))),Source.value("punk",false))];
        TSharedRef<SWidget> ActionRow=SNew(SHorizontalBox)
            +SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center).Padding(0,0,10,0)[Graphic]
            +SHorizontalBox::Slot().FillWidth(1.f).VAlign(VAlign_Center)[ActionFace];
        TSharedRef<SWidget> ActionButton=SNew(SButton).ButtonStyle(&ActionButtonStyle()).ContentPadding(FMargin(10,8))
            .IsEnabled(Data.value("connected",0)==2).ToolTip(OldWestTooltip(FText::FromString(Caption)))
            .OnClicked_Lambda([this,Command](){PlayUiSound(false);Send(Command);return FReply::Handled();})[ActionRow];
        Actions->AddSlot().Padding(0,0,0,4)[ActionButton];
#if !UE_BUILD_SHIPPING
        MasterActionButtons.Emplace(Text(Command.dump()),ActionButton);
#endif
        ++ActionCount;
    }
    // Keep unavailable abilities visible on the selected card. Previously a
    // damaged, spent or unaffordable camp could display only a generic drag hint.
    if(SelectedSource!=0&&!PendingChoice)for(const auto& Card:View["players"][Seat]["hand"])
        if(Card.value("id",0)==SelectedSource&&Card.contains("play_availability")&&!Card["play_availability"].value("available",false)) {
            Actions->AddSlot().Padding(0,0,0,4)[Label(TEXT("Play ")+Text(Card.value("name",std::string()))+TEXT(" · ")+
                Text(Card["play_availability"].value("reason",std::string("Unavailable"))),14,FLinearColor(.94f,.57f,.3f,1))];
            ++ActionCount;
        }
    if(SelectedSource!=0 && !PendingChoice) for(const auto& Column:View["players"][Seat]["columns"])
        for(const auto& Card:Column) if(Card.value("id",0)==SelectedSource&&Card.contains("public_abilities"))
            for(const auto& Status:Card.value("ability_availability",J::array())) if(!Status.value("available",false)) {
                J Ability;for(const auto& Public:Card["public_abilities"])if(Public["index"]==Status["index"])Ability=Public;
                TSharedRef<SVerticalBox> Explanation=SNew(SVerticalBox);
                if(Ability.contains("activation_label"))Explanation->AddSlot().AutoHeight()[Label(Text(Ability["activation_label"]),14,Sand)];
                Explanation->AddSlot().AutoHeight()[Label(Text(Ability.value("effect",std::string())),14,Muted)];
                Explanation->AddSlot().AutoHeight().Padding(0,3)[Label(Text(Status.value("reason",std::string("Unavailable"))),14,FLinearColor(.94f,.57f,.3f,1))];
                Actions->AddSlot().Padding(0,0,0,4)[SNew(SBorder).Padding(8).BorderBackgroundColor(FLinearColor(.025f,.035f,.04f,1))[Explanation]];
                ++ActionCount;
            }
    if(!PendingChoice)for(const auto& Column:View["players"][Seat]["columns"])for(const auto& Card:Column)
        if(Card.contains("private_peek")&&(Card.value("id",0)==SelectedSource||MasqueradeSelected)) {
            const J& Peek=Card["private_peek"];
            if(!Peek.value("flip_available",false)) {
                Actions->AddSlot().Padding(0,0,0,4)[Label(Text(Peek.value("name",std::string()))+TEXT(" · ")+Text(Peek.value("flip_reason",std::string())),14,Muted)];
                ++ActionCount;
            }
        }
    if (ActionCount == 0) Actions->AddSlot()[Label(SelectedSource != 0 ? TEXT("Drag a hand card into a lit battlefield space to deploy it. Its other actions appear here.") : TEXT("Select a card for its actions, or drag a hand card to deploy."), 13)];
    if(PendingChoice&&View["choice"].contains("help"))
        Actions->AddSlot().Padding(0,4,0,0)[BattleSection(TEXT("target.rules"),TEXT("WHY THESE TARGETS?"),Label(Text(View["choice"]["help"]),11,Muted))];
    Controls->AddSlot().FillHeight(1.f)[Actions];
    return Controls;
}
