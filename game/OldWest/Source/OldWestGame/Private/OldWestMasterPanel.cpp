#include "OldWestCosmetics.h"
#include "OldWestDisplayNames.h"
#include "OldWestHUD.h"
#include "OldWestHUDIcon.h"
#include "Widgets/SOverlay.h"
#include "OldWestReadiness.h"
#include "OldWestSession.h"
#include "OldWestCardPortrait.h"
#include "OldWestCardDrag.h"
#include "OldWestTooltip.h"
#include "OldWestMasterStyle.h"
#include "Widgets/Input/SButton.h"
#include "Widgets/Layout/SBorder.h"
#include "Widgets/Layout/SBox.h"
#include "Widgets/Layout/SScrollBox.h"
#include "Widgets/Layout/SWrapBox.h"
#include "Widgets/SBoxPanel.h"
#include "Widgets/SLeafWidget.h"
#include "Widgets/SNullWidget.h"
#include "Widgets/Text/STextBlock.h"
#include "Rendering/DrawElements.h"
using J = nlohmann::ordered_json;
using namespace OldWestMasterStyle;
namespace {
constexpr float FormationCardHeight=158.f;
constexpr float FormationPortraitHeight=78.f;
class SWaterDrops : public SLeafWidget {
public:
    SLATE_BEGIN_ARGS(SWaterDrops) {} SLATE_ARGUMENT(int32, Count) SLATE_END_ARGS()
    void Construct(const FArguments& Args) { Count=FMath::Clamp(Args._Count,0,12); }
    FVector2D ComputeDesiredSize(float) const override { return FVector2D(FMath::Max(3,Count)*18,24); }
    int32 OnPaint(const FPaintArgs&,const FGeometry& G,const FSlateRect&,FSlateWindowElementList& Out,int32 L,const FWidgetStyle&,bool) const override {
        for(int32 I=0;I<FMath::Max(3,Count);++I) {
            // Whiskey (the canonical water resource): filled amber bottles, drawn in logical units.
            const FLinearColor Color=I<Count?FLinearColor(.93f,.55f,.12f,1):FLinearColor(.16f,.12f,.08f,1);
            for(int32 Y=0;Y<18;++Y) {
                const float Half=Y<6?1.6f:Y<9?1.6f+(Y-5)*1.4f:5.8f;
                const float X=8+I*18;
                TArray<FVector2D> P={FVector2D(X-Half,Y+3),FVector2D(X+Half,Y+3)};
                FSlateDrawElement::MakeLines(Out,L,G.ToPaintGeometry(),P,ESlateDrawEffect::None,Color,true,1.5f);
            }
        }
        return L;
    }
private: int32 Count=0;
};
FString Condition(const J& C) {
    if(C.value("destroyed",false)) return TEXT("BURNED OUT");
    if(C.value("zone",std::string())!="board") return FString();
    FString S=C.value("damage",0)>0?TEXT("Damaged · ")+OldWestReadiness::Label(C).ToLower():OldWestReadiness::Label(C);
    return S+(C.value("protected",false)?TEXT("\nguarded"):TEXT("\nexposed"));
}
}

TSharedRef<SWidget> SOldWestHUD::MasterCard(const J& Card,bool Hand)
{
    const bool Punk=Card.value("punk",false),Camp=Card.value("type",std::string())=="camp";
    const int32 Id=Card.value("id",0);
    const J* Def=Punk?nullptr:CardDefinition(Card.value("card_id",std::string()));
    TSharedRef<SVerticalBox> Face=SNew(SVerticalBox);
    const bool Playable=Hand&&Card.contains("play_availability")&&Card["play_availability"].value("available",false);
    Face->AddSlot().AutoHeight()[SNew(SBox).HeightOverride(Hand?100.f:FormationPortraitHeight)
        [SNew(SOverlay)
            +SOverlay::Slot()[MakeOldWestCardPortrait(Owner->GetWorld(),Punk?TEXT("punk"):Text(OldWestCosmetics::Visual(Card)),Camp?TEXT("camp"):Text(Card.value("type",std::string("person"))),Punk)]
            +SOverlay::Slot().HAlign(HAlign_Right).VAlign(VAlign_Top).Padding(4)
            [SNew(SBorder).BorderImage(FCoreStyle::Get().GetBrush("WhiteBrush")).BorderBackgroundColor(FLinearColor(.01f,.025f,.03f,.94f)).Padding(3)
                .Visibility(EVisibility::HitTestInvisible)
                [SNew(SOldWestHUDIcon).Size(22).Color(Hand?(Playable?Aqua:Muted):Card.value("damage",0)>0?Pink:Aqua)
                    .Kind(Hand?EOldWestHUDIcon::Deploy:Card.value("protected",false)?EOldWestHUDIcon::Shield:EOldWestHUDIcon::Attack)]]]];
    Face->AddSlot().AutoHeight().Padding(5,3,5,1)[SNew(STextBlock).Text(FText::FromString(Punk&&Card.contains("private_peek")?TEXT("Drifter · inspect"):Text(Card.value("name",std::string("Punk")))))
        .Font(FCoreStyle::GetDefaultFontStyle("Bold",15)).ColorAndOpacity(Card.value("destroyed",false)?Muted:Sand)
        .OverflowPolicy(ETextOverflowPolicy::Ellipsis)];
    FString Meta=Condition(Card);
    if(Hand&&Def) Meta=FString::Printf(TEXT("%d whiskey"),Def->value("play_cost",0));
    if(Hand&&Def&&Card.contains("play_availability")) {
        const int32 Price=Card["play_availability"].value("cost",0),Printed=Def->value("play_cost",0);
        Meta=FString::Printf(TEXT("%d whiskey"),Price);
        if(Price!=Printed)Meta+=FString::Printf(TEXT(" · was %d"),Printed);
    }
    if(Hand) Face->AddSlot().AutoHeight().Padding(5,0,5,3)[Label(Meta,14,Card.value("damage",0)>0?Pink:Muted)];
    else Face->AddSlot().AutoHeight().Padding(5,0,5,3)[SNew(SBox).HeightOverride(44)
        [SNew(STextBlock).Text(FText::FromString(Meta)).Font(FCoreStyle::GetDefaultFontStyle("Regular",14))
            .ColorAndOpacity(Card.value("damage",0)>0?Pink:Muted).OverflowPolicy(ETextOverflowPolicy::Ellipsis)]];
    if(Hand&&Def&&Def->contains("junk")) Face->AddSlot().AutoHeight().Padding(5,0,5,3)[Label(OldWestDisplay::Text(TEXT("Junk · ")+Text((*Def)["junk"])),13,Aqua)];
    const bool Hurt=!Card.value("destroyed",false)&&Card.value("damage",0)>0;
    TSharedRef<SWidget> Inner=SNew(SBorder).BorderImage(FCoreStyle::Get().GetBrush("WhiteBrush"))
        .BorderBackgroundColor(Hurt?FLinearColor(.16f,.045f,.027f,1):FLinearColor(.022f,.034f,.041f,1)).Padding(0)[Face];
    TSharedRef<SWidget> Surface=SNew(SBorder).BorderImage(FCoreStyle::Get().GetBrush("WhiteBrush"))
        .BorderBackgroundColor(Hurt?FLinearColor(1.f,.38f,.12f,1):Id==InspectedCard?Aqua:Hand&&Card.contains("play_availability")&&Card["play_availability"].value("available",false)?FLinearColor(.13f,.48f,.44f,1):FLinearColor(.10f,.16f,.18f,1)).Padding(2.f)[Inner];
    CardHoverTargets.Emplace(Card,Surface);
    return Surface;
}

TSharedRef<SWidget> SOldWestHUD::MasterPanel(const J& Data)
{
    // Keep fixed readouts compact at the dock's smallest supported width.
    auto Readout=[](const FString& Value,int32 Size,FLinearColor Ink) -> TSharedRef<SWidget> {
        return SNew(STextBlock).Text(FText::FromString(Value)).SimpleTextMode(true)
            .Font(FCoreStyle::GetDefaultFontStyle("Regular",Size)).ColorAndOpacity(Ink)
            .Clipping(EWidgetClipping::ClipToBounds);
    };
    const J& View=Data["view"];
    const int32 Seat=Data.value("seat",0);
    if(InspectorSide<0||InspectorSide>1) InspectorSide=Seat;
    const bool Own=InspectorSide==Seat;
    const J& Player=View["players"][InspectorSide];
    J Selected=nullptr;
    for(int32 P=0;P<2;++P) {
        for(const auto& Column:View["players"][P]["columns"]) for(const auto& Card:Column) if(Card.value("id",0)==InspectedCard)Selected=Card;
        for(const auto& Card:View["players"][P]["queue"])if(!Card.is_null()&&Card.value("id",0)==InspectedCard)Selected=Card;
    }
    for(const auto& Card:View["players"][Seat]["hand"])if(Card.value("id",0)==InspectedCard)Selected=Card;
    if(Selected.is_null()) {InspectedCard=0;SelectedSource=0;}
    TSharedRef<SVerticalBox> Main=SNew(SVerticalBox);
    TSharedRef<SHorizontalBox> Tabs=SNew(SHorizontalBox);
    for(int32 I=0;I<2;++I) {
        const int32 Side=I?1-Seat:Seat;
        TSharedRef<SWidget> Tab=SNew(SButton).ButtonStyle(&ActionButtonStyle()).ContentPadding(FMargin(8,6))
            .ButtonColorAndOpacity((!HistoryOpen&&Side==InspectorSide)?FLinearColor(.13f,.48f,.44f,1):FLinearColor::White)
            .HAlign(HAlign_Center).OnClicked_Lambda([this,Side]() { HistoryOpen=false;InspectorSide=Side;SelectedSource=0;InspectedCard=0;Dirty=true;PlayUiSound(false);return FReply::Handled(); })
            [Readout(I?TEXT("ENEMY"):TEXT("YOUR"),14,(!HistoryOpen&&Side==InspectorSide)?Aqua:Muted)];
        Tabs->AddSlot().FillWidth(1.f).Padding(I?3:0,0,I?0:3,0)[Tab];
#if !UE_BUILD_SHIPPING
        MasterTabs.Emplace(I?TEXT("enemy"):TEXT("your"),Tab);
#endif
    }
    TSharedRef<SWidget> HistoryTab=SNew(SButton).ButtonStyle(&ActionButtonStyle()).ContentPadding(FMargin(8,6))
        .ButtonColorAndOpacity(HistoryOpen?FLinearColor(.13f,.48f,.44f,1):FLinearColor::White).HAlign(HAlign_Center)
        .OnClicked_Lambda([this](){HistoryOpen=true;Dirty=true;PlayUiSound(false);return FReply::Handled();})[Readout(TEXT("HISTORY"),14,HistoryOpen?Aqua:Muted)];
    Tabs->AddSlot().FillWidth(1.f).Padding(3,0,0,0)[HistoryTab];
#if !UE_BUILD_SHIPPING
    MasterTabs.Emplace(TEXT("history"),HistoryTab);
#endif
    const bool YourTurn=View.value("active_player",-1)==Seat;
    const auto& You=View["players"][Seat];
    TSharedRef<SHorizontalBox> Status=SNew(SHorizontalBox);
    Status->AddSlot().AutoWidth().VAlign(VAlign_Center).Padding(0,0,8,0)
        [SNew(SOldWestHUDIcon).Kind(PendingChoice?EOldWestHUDIcon::Attack:EOldWestHUDIcon::Turn).Color(PendingChoice?Pink:Aqua)];
    Status->AddSlot().FillWidth(1.f).VAlign(VAlign_Center)
        [Readout(FString::Printf(TEXT("%s · %d"),PendingChoice?TEXT("RESPOND / TURN"):YourTurn?TEXT("YOUR TURN"):TEXT("ENEMY TURN"),View.value("turn",0)),16,PendingChoice?Pink:Sand)];
    Status->AddSlot().AutoWidth().VAlign(VAlign_Center).Padding(8,0,4,0)[SNew(SOldWestHUDIcon).Kind(EOldWestHUDIcon::Water).Size(24)];
    Status->AddSlot().AutoWidth().VAlign(VAlign_Center)[Readout(FString::FromInt(You.value("water",0)),22,Aqua)];
    Status->AddSlot().AutoWidth().VAlign(VAlign_Center).Padding(12,0,4,0)[SNew(SOldWestHUDIcon).Kind(EOldWestHUDIcon::Cards).Size(24)];
    Status->AddSlot().AutoWidth().VAlign(VAlign_Center)[Readout(FString::FromInt(int32(You["hand"].size())),18,Sand)];
    Main->AddSlot().AutoHeight().Padding(0,2,0,8)
        [SNew(SBorder).BorderImage(FCoreStyle::Get().GetBrush("WhiteBrush")).BorderBackgroundColor(FLinearColor(.025f,.07f,.08f,1)).Padding(8)[Status]];
    Main->AddSlot().AutoHeight()[Tabs];
    const FString Prefix=Own?TEXT("your."):TEXT("enemy.");
    TSharedRef<SHorizontalBox> Water=SNew(SHorizontalBox);
    Water->AddSlot().AutoWidth().VAlign(VAlign_Center)[Label(TEXT("WHISKEY"),11,Muted)];
    Water->AddSlot().AutoWidth().Padding(8,0)[SNew(SWaterDrops).Count(Player.value("water",0))];
    Water->AddSlot().AutoWidth().VAlign(VAlign_Center)[Label(FString::FromInt(Player.value("water",0)),16,Aqua)];
    Water->AddSlot().FillWidth(1.f).HAlign(HAlign_Right).VAlign(VAlign_Center)[Label(Own?TEXT("YOUR FORMATION"):TEXT("ENEMY FORMATION"),11,Muted)];

    TSharedRef<SVerticalBox> Body=SNew(SVerticalBox);
    const bool PrivateInspection=Own&&!Selected.is_null()&&Selected.value("owner",-1)==Seat&&Selected.contains("private_peek");
    if(PrivateInspection)Body->AddSlot().AutoHeight()[BattleSection(Prefix+TEXT("details"),TEXT("SELECTED DRIFTER · PRIVATE INSPECTION"),CardDetails(Selected,Seat))];
    Body->AddSlot().AutoHeight()[BattleSection(Prefix+TEXT("water"),TEXT("WHISKEY"),Water)];
    const int32 HandCount=Own?int32(Player["hand"].size()):Player.value("hand_count",0);

    TSharedRef<SWrapBox> Hand=SNew(SWrapBox).UseAllottedSize(true).InnerSlotPadding(FVector2D(6,6));
    if(Own) for(const auto& Card:Player["hand"]) {
        const int32 Id=Card["id"];
        const TWeakPtr<SOldWestHUD> Weak=SharedThis(this);
        TSharedRef<SWidget> Tile=SNew(SBox).WidthOverride(156).HeightOverride(190).Clipping(EWidgetClipping::ClipToBounds)
            [SNew(SOldWestDragCard).Context([this,Id](FVector2D P){CardActions(Id,P);}).Clicked([this,Id,Seat]() {InspectorSide=Seat;ClickCard(Id);})
                .BeginDrag([Weak,Id]()->TSharedPtr<FDragDropOperation>{if(auto HUD=Weak.Pin())return HUD->BeginDeployment(Id);return nullptr;})[MasterCard(Card,true)]];
        Hand->AddSlot()[Tile];
#if !UE_BUILD_SHIPPING
        if(BattlePlanOpen)HandCards.Emplace(FString::FromInt(Id),Tile);
#endif
    }
    else for(int32 I=0;I<FMath::Min(HandCount,24);++I) {
        Hand->AddSlot()[SNew(SBox).WidthOverride(46).HeightOverride(68)
            [SNew(SBorder).BorderImage(FCoreStyle::Get().GetBrush("WhiteBrush")).BorderBackgroundColor(FLinearColor(.07f,.12f,.13f,1))
                .HAlign(HAlign_Center).VAlign(VAlign_Center)[Label(TEXT("?"),18,Muted)]]];
    }
    if(HandCount==0)Hand->AddSlot()[Label(TEXT("No cards in hand"),12,Muted)];
    Body->AddSlot().AutoHeight()[BattleSection(Prefix+TEXT("hand"),FString::Printf(TEXT("HAND · %d"),HandCount)+(Own?TEXT("  /  drag to deploy"):TEXT(" hidden cards")),
        Hand)];

    TSharedRef<SHorizontalBox> Lanes=SNew(SHorizontalBox);
    for(int32 C=0;C<3;++C) {
        TSharedRef<SVerticalBox> Lane=SNew(SVerticalBox);
        const auto& Column=Player["columns"][C];
        auto AddCard=[&](const J& Card) -> TSharedRef<SWidget> {
            const int32 Id=Card.value("id",0);
            TSharedRef<SWidget> Tile=SNew(SBox).HeightOverride(FormationCardHeight).Clipping(EWidgetClipping::ClipToBounds)
                [SNew(SOldWestDragCard).Context([this,Id](FVector2D P){CardActions(Id,P);})
                .Clicked([this,Id](){ClickCard(Id);}).BeginDrag([this,Id](){return BeginDeployment(Id);})[MasterCard(Card)]];
            Lane->AddSlot().AutoHeight().Padding(0,0,0,4)[Tile];
#if !UE_BUILD_SHIPPING
            MasterCards.Emplace(FString::FromInt(Id),Tile);
#endif
            return Tile;
        };
        // Keep the authoritative front-to-rear order, including moving camps
        // and the third person allowed after Boarding House removes a ruin.
        TArray<J> Slots;Slots.Init(J(nullptr),3);
        int32 CampIndex=-1,CampRow=2;
        for(int32 I=0;I<int32(Column.size());++I)if(Column[I].value("type",std::string())=="camp") {
            CampIndex=I;CampRow=Column[I].value("destroyed",false)?2:2-Column[I].value("advance",0);
        }
        for(int32 I=0;I<int32(Column.size());++I) {
            const int32 Row=CampIndex<0?3-int32(Column.size())+I:CampRow+I-CampIndex;
            if(Slots.IsValidIndex(Row))Slots[Row]=Column[I];
        }
        for(int32 Row=0;Row<3;++Row) {
            TSharedRef<SWidget> Tile=SNullWidget::NullWidget;
            if(!Slots[Row].is_null())Tile=AddCard(Slots[Row]);
            else {
                Tile=SNew(SBox).HeightOverride(FormationCardHeight).Clipping(EWidgetClipping::ClipToBounds)
                [SNew(SBorder).BorderImage(FCoreStyle::Get().GetBrush("WhiteBrush")).BorderBackgroundColor(FLinearColor(.018f,.03f,.035f,1))
                    .HAlign(HAlign_Center).VAlign(VAlign_Center)[SNew(SVerticalBox)
                        +SVerticalBox::Slot().AutoHeight().HAlign(HAlign_Center)[SNew(SOldWestHUDIcon).Kind(EOldWestHUDIcon::Deploy).Size(30).Color(Muted)]
                        +SVerticalBox::Slot().AutoHeight().Padding(0,8,0,0)[Label(TEXT("Open space"),14,Muted)]]];
                Lane->AddSlot().AutoHeight().Padding(0,0,0,4)[Tile];
            }
            PanelDropSurfaces.Add({Tile,Slots[Row].is_null()?0:Slots[Row].value("id",0),InspectorSide,C,Row,-99});
#if !UE_BUILD_SHIPPING
            FormationSlots.Emplace(FString::Printf(TEXT("%d:%d"),C,Row),Tile);
#endif
        }
        Lanes->AddSlot().FillWidth(1.f).Padding(3,0,3,0)
            [BattleSection(Prefix+FString::Printf(TEXT("column%d"),C+1),FString::Printf(TEXT("COLUMN %d"),C+1),Lane)];
#if !UE_BUILD_SHIPPING
        RosterLanes.Emplace(FString::FromInt(C),Lane);
#endif
    }
    Body->AddSlot().AutoHeight()[BattleSection(Prefix+TEXT("formation"),TEXT("FORMATION · front to rear"),Lanes)];
    TSharedRef<SHorizontalBox> Events=SNew(SHorizontalBox);
    TSharedRef<SWidget> PlayNow=SNew(SBorder)
        .Visibility(EVisibility::Visible)
        .BorderImage(FCoreStyle::Get().GetBrush("WhiteBrush"))
        .BorderBackgroundColor(FLinearColor(.025f,.07f,.08f,1)).Padding(6)
        [SNew(SVerticalBox)
            +SVerticalBox::Slot().AutoHeight().HAlign(HAlign_Center)[SNew(SOldWestHUDIcon).Kind(EOldWestHUDIcon::Event).Size(26).Color(Aqua)]
            +SVerticalBox::Slot().AutoHeight()[Label(TEXT("0  NOW"),14,Aqua)]
            +SVerticalBox::Slot().AutoHeight().Padding(0,3)[Label(TEXT("Play now"),14,Sand)]];
    PanelDropSurfaces.Add({PlayNow,0,InspectorSide,-1,-1,-1});
    Events->AddSlot().FillWidth(1.f).Padding(0,0,3,0)[PlayNow];
    for(int32 I=0;I<3;++I) {
        const J& Event=Player["queue"][I];
        TSharedRef<SVerticalBox> Entry=SNew(SVerticalBox);
        Entry->AddSlot().AutoHeight().HAlign(HAlign_Center)[SNew(SOldWestHUDIcon).Kind(EOldWestHUDIcon::Event).Size(26).Color(Event.is_null()?Muted:Aqua)];
        Entry->AddSlot().AutoHeight()[Label(FString::Printf(TEXT("%d  %s"),I+1,I==0?TEXT("NEXT"):TEXT("TURNS")),14,Aqua)];
        Entry->AddSlot().AutoHeight().Padding(0,3)[Label(Event.is_null()?TEXT("—"):Text(Event.value("name",std::string())),14,Event.is_null()?Muted:Sand)];
        TSharedRef<SWidget> Tile=SNew(SOldWestDragCard)
            .Context([this,Event](FVector2D P){CardActions(Event.value("id",0),P);})
            .Clicked([this,Event](){if(!Event.is_null())ClickCard(Event.value("id",0));})
            .BeginDrag([this,Event]()->TSharedPtr<FDragDropOperation>{return Event.is_null()?nullptr:BeginDeployment(Event.value("id",0));})[Entry];
        PanelDropSurfaces.Add({Tile,Event.is_null()?0:Event.value("id",0),InspectorSide,-1,-1,I});
        if(!Event.is_null())CardHoverTargets.Emplace(Event,Tile);
        Events->AddSlot().FillWidth(1.f).Padding(I?3:0,0,I==2?0:3,0)[Tile];
    }
    Body->AddSlot().AutoHeight()[BattleSection(Prefix+TEXT("events"),TEXT("TROUBLE · countdown"),Events)];
    if(!PrivateInspection&&!Selected.is_null()&&Selected.value("owner",Seat)==InspectorSide) {
        Body->AddSlot().AutoHeight()[BattleSection(Prefix+TEXT("details"),TEXT("SELECTED CARD"),CardDetails(Selected,Seat))];
    }
    const FString ScrollKey=HistoryOpen?TEXT("history"):Prefix;
    TSharedRef<SScrollBox> Scroll=SNew(SScrollBox).ScrollBarThickness(FVector2D(8,8)).AnimateWheelScrolling(false)
        .OnUserScrolled_Lambda([this,ScrollKey](float Offset){BattleScrollOffsets.Add(ScrollKey,Offset);})
        +SScrollBox::Slot()[HistoryOpen?BattleHistory(View,Seat):StaticCastSharedRef<SWidget>(Body)];
    Scroll->SetScrollOffset(BattleScrollOffsets.FindRef(ScrollKey));
    BattleDropScroll=Scroll;
#if !UE_BUILD_SHIPPING
    BattleScrollWidget=Scroll;
#endif
    Scroll->SetVisibility(TAttribute<EVisibility>::CreateLambda([this](){return (Owner.IsValid()&&Owner->IsAnalysisChoiceFramed())||(OverviewOpen&&PendingChoice)?EVisibility::Collapsed:EVisibility::Visible;}));
    Main->AddSlot().FillHeight(1.f)[Scroll];
    MasterActionsVisible=PendingChoice||(View.value("active_player",-1)==Seat&&View["choice"].is_null());
    if(MasterActionsVisible) {
        Main->AddSlot().AutoHeight()[BattleSection(TEXT("your.actions"),PendingChoice?TEXT("YOUR RESPONSE · required"):TEXT("YOUR ACTIONS"),
            MasterActions(Data),PendingChoice)];
    }
    return Main;
}
