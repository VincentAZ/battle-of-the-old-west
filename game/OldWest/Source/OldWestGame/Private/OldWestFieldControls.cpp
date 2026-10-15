#include "OldWestDisplayNames.h"
#include "OldWestHUD.h"
#include "OldWestMasterStyle.h"
#include "OldWestReadiness.h"
#include "OldWestHUDIcon.h"
#include "Widgets/Input/SButton.h"
#include "OldWestDockPanel.h"
#include "OldWestCardDrag.h"
#include "OldWestSession.h"
#include "Widgets/Layout/SBorder.h"
#include "Widgets/Layout/SBox.h"
#include "Widgets/Layout/SScrollBox.h"
#include "Widgets/SBoxPanel.h"
#include "Widgets/Text/STextBlock.h"
#include "Framework/Application/SlateApplication.h"
#include "Styling/CoreStyle.h"
using J=nlohmann::ordered_json;
namespace {
FString Text(const std::string& S){return OldWestDisplay::Text(FString(UTF8_TO_TCHAR(S.c_str())));}
const FLinearColor Gold(1.f,.72f,.30f,1.f);
TSharedRef<SWidget> Copy(const FString& Value,int32 Size,FLinearColor Color,bool Bold=false)
{
    return SNew(STextBlock).Text(FText::FromString(Value))
        .Font(FCoreStyle::GetDefaultFontStyle(Bold?"Bold":"Regular",Size))
        .ColorAndOpacity(Color).AutoWrapText(true).LineHeightPercentage(1.15f);
}
TSharedRef<SWidget> IconCopy(EOldWestHUDIcon Icon,const FString& Value,FLinearColor Color,bool Bold=false)
{
    return SNew(SHorizontalBox)
        +SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Top).Padding(0,1,8,0)[SNew(SOldWestHUDIcon).Kind(Icon).Color(Color).Size(18)]
        +SHorizontalBox::Slot().FillWidth(1)[Copy(Value,12,Color,Bold)];
}
TSharedRef<SWidget> Stat(EOldWestHUDIcon Icon,const FString& Name,const FString& Value,FLinearColor Color)
{
    return SNew(SHorizontalBox)
        +SHorizontalBox::Slot().FillWidth(1).VAlign(VAlign_Center)[IconCopy(Icon,Name,OldWestMasterStyle::Muted)]
        +SHorizontalBox::Slot().AutoWidth().Padding(8,0)[Copy(Value,16,Color,true)];
}
}

TSharedRef<SWidget> SOldWestHUD::FieldStatus(const J& Data,bool Enemy)
{
    const int32 Seat=Data.value("seat",0),Side=Enemy?1-Seat:Seat;
    const auto& View=Data["view"];const auto& Player=View["players"][Side];
    auto Body=SNew(SVerticalBox);
    const bool Open=Enemy?EnemyStatsOpen:OwnStatsOpen;
    TSharedRef<SWidget> Toggle=Button((Enemy?TEXT("ENEMY"):TEXT("YOU"))+FString(Open?TEXT("  −"):TEXT("  +")),[this,Enemy](){if(Enemy)EnemyStatsOpen=!EnemyStatsOpen;else OwnStatsOpen=!OwnStatsOpen;Dirty=true;});
    Body->AddSlot().AutoHeight()[Toggle];
#if !UE_BUILD_SHIPPING
    StatusButtons.Emplace(Enemy?TEXT("enemy_stats"):TEXT("own_stats"),Toggle);
#endif
    if(Open)
    {
        auto Water=Stat(EOldWestHUDIcon::Water,TEXT("WHISKEY"),FString::FromInt(Player.value("water",0)),OldWestMasterStyle::Aqua);
        if(Enemy)Body->AddSlot().AutoHeight().Padding(6,6)[Water];
        else {
            TSharedRef<SWidget> WaterDrag=SNew(SOldWestDragCard)
                .Context([this](FVector2D P){CardActions(-3002,P);})
                .BeginDrag([this](){return BeginDeployment(-3002);})[Water];
            Body->AddSlot().AutoHeight().Padding(6,6)[WaterDrag];
#if !UE_BUILD_SHIPPING
            StatusButtons.Emplace(TEXT("water_drag"),WaterDrag);
#endif
        }
        if(!Enemy)Body->AddSlot().AutoHeight().Padding(6,0,6,6)[Copy(TEXT("Drag whiskey to act"),10,OldWestMasterStyle::Muted)];
        Body->AddSlot().AutoHeight().Padding(6,3)[Stat(EOldWestHUDIcon::Cards,TEXT("HAND"),FString::FromInt(Player.value("hand_count",0)),OldWestMasterStyle::Sand)];
        Body->AddSlot().AutoHeight().Padding(6,3)[Stat(EOldWestHUDIcon::Water,TEXT("FLASK"),Player.value("silo_in_hand",false)?TEXT("FULL"):TEXT("EMPTY"),Player.value("silo_in_hand",false)?OldWestMasterStyle::Aqua:OldWestMasterStyle::Muted)];
        int32 Alive=0,Damaged=0;
        for(const auto& Column:Player["columns"])for(const auto& Card:Column)if(Card.value("type",std::string())=="camp"&&!Card.value("destroyed",false))
        {++Alive;if(Card.value("damage",0)>0)++Damaged;}
        Body->AddSlot().AutoHeight().Padding(6,3)[Stat(EOldWestHUDIcon::Shield,TEXT("HOLDINGS"),FString::Printf(TEXT("%d / 3"),Alive),OldWestMasterStyle::Sand)];
        Body->AddSlot().AutoHeight().Padding(6,3)[Stat(EOldWestHUDIcon::Attack,TEXT("DAMAGED"),FString::FromInt(Damaged),Damaged?OldWestMasterStyle::Pink:OldWestMasterStyle::Muted)];
        if(!Enemy) {
            Body->AddSlot().AutoHeight().Padding(6,3)[Stat(EOldWestHUDIcon::Cards,TEXT("DECK"),FString::FromInt(View.value("deck_count",0)),OldWestMasterStyle::Sand)];
            Body->AddSlot().AutoHeight().Padding(6,3)[Stat(EOldWestHUDIcon::Cards,TEXT("DISCARD"),FString::FromInt(View.value("discard_count",0)),OldWestMasterStyle::Muted)];
        }
    }
    if(Enemy && View.value("status",std::string())!="won" && View.value("status",std::string())!="draw")
    {
        TSharedRef<SWidget> HistoryToggle=Button(FieldHistoryOpen?TEXT("TURN HISTORY  −"):TEXT("TURN HISTORY  +"),[this](){
            FieldHistoryOpen=!FieldHistoryOpen;
            if(const auto State=PanelStates.FindRef(TEXT("field_enemy")))State->Size.Y=FieldHistoryOpen?550:360;
            Dirty=true;
        });
        Body->AddSlot().AutoHeight().Padding(0,12,0,0)[HistoryToggle];
#if !UE_BUILD_SHIPPING
        StatusButtons.Emplace(TEXT("history"),HistoryToggle);
#endif
        if(FieldHistoryOpen)Body->AddSlot().FillHeight(1.f).Padding(0,8,0,0)[BattleHistory(View,Seat,true)];
    }
    if(Enemy) {
        auto Feed=SNew(SVerticalBox);
        Feed->AddSlot().AutoHeight()[Copy(TEXT("OPPONENT PLAY-BY-PLAY"),11,Gold,true)];
        TArray<FString> Lines;
        for(const auto& E:View.value("history",J::array())) {
            if(E.value("player",-1)!=1-Seat)continue;
            const std::string Kind=E.value("type",std::string());
            const FString Source=Text(E.value("source_name",std::string()));
            const FString Target=Text(E.value("target_name",std::string()));
            const FString Detail=Text(E.value("detail",std::string()));
            FString Line;
            if(Kind=="junk")Line=TEXT("Junked ")+Detail;
            else if(Kind=="event_play")Line=TEXT("Played ")+Source;
            else if(Kind=="event_resolve")Line=Source+TEXT(" resolved");
            else if(Kind=="enter")Line=TEXT("Deployed ")+Target;
            else if(Kind=="ability")Line=TEXT("Used ")+Source+TEXT(": ")+Detail;
            else if(Kind=="store_water")Line=TEXT("Stowed whiskey in Hip Flask");
            else if(Kind=="draw_card")Line=TEXT("Drew a card");
            if(!Line.IsEmpty())Lines.Add(Line);
        }
        for(int32 I=FMath::Max(0,Lines.Num()-3);I<Lines.Num();++I)
            Feed->AddSlot().AutoHeight().Padding(0,4)[IconCopy(EOldWestHUDIcon::Turn,Lines[I],OldWestMasterStyle::Sand)];
        Body->InsertSlot(1).AutoHeight().Padding(6,8)[Feed];
    }
    // Keep text at its authored size; the history owns a bounded scroll area.
    TSharedRef<SWidget> Surface=SNew(SBorder)
        .BorderImage(FCoreStyle::Get().GetBrush("WhiteBrush"))
        .BorderBackgroundColor(FLinearColor(.012f,.020f,.026f,1.f)).Padding(10)[Body];
    FieldSurfaces.Add(Surface);
    return Surface;
}

#include "OldWestPunkShelter.h"
#include "OldWestStaging.h"
#include "Engine/World.h"
void SOldWestHUD::UpdatePunkShelter()
{
    if(!Owner.IsValid())return;
    J Data;
    try{Data=J::parse(TCHAR_TO_UTF8(*Owner->GetPresentationSnapshot()));}catch(...){return;}
    const bool Match=Data.value("hosted",false)&&Data.contains("view")&&Data["view"].value("status",std::string())!="selection";
    const FString Id=Text(Data.value("match_id",std::string()));
    if(PunkShelter.IsValid()&&(!Match||Id!=PunkShelterMatch)){PunkShelter->Destroy();PunkShelter.Reset();}
    if(EnemyPunkShelter.IsValid()&&(!Match||Id!=PunkShelterMatch)){EnemyPunkShelter->Destroy();EnemyPunkShelter.Reset();}
    if(Staging.IsValid()&&(!Match||Id!=PunkShelterMatch)){Staging->Destroy();Staging.Reset();StagingGeneration=-1;}
    if(!Match)return;
    if(!PunkShelter.IsValid()) {PunkShelter=Owner->GetWorld()->SpawnActor<AOldWestPunkShelter>();PunkShelterMatch=Id;PunkShelter->Initialize(Data.value("seat",0));}
    if(!EnemyPunkShelter.IsValid()) {EnemyPunkShelter=Owner->GetWorld()->SpawnActor<AOldWestPunkShelter>();EnemyPunkShelter->Initialize(1-Data.value("seat",0));}
    if(!Staging.IsValid())Staging=Owner->GetWorld()->SpawnActor<AOldWestStaging>();
    if(StagingGeneration!=Owner->GetViewGeneration()) {Staging->ApplySnapshot(Owner->GetPresentationSnapshot());StagingGeneration=Owner->GetViewGeneration();}
    int Count=0;
    for(const auto& Action:Data["actions"])if(Action.contains("placement")&&Action["placement"].value("punk",false))Count=FMath::Max(Count,Action.value("punk_remaining",1));
    TSet<int32> Board;
    for(const auto& Column:Data["view"]["players"][Data.value("seat",0)]["columns"])for(const auto& Card:Column)if(Card.value("punk",false))Board.Add(Card.value("id",0));
    PunkShelter->SetSupply(Count,Data["view"].value("revision",-1),Board);
}

TSharedRef<SWidget> SOldWestHUD::WarRoom(const J& Data)
{
    auto Body=SNew(SVerticalBox);
    Body->AddSlot().AutoHeight()[Label(TEXT("LEDGER"),20,OldWestMasterStyle::Sand)];
    Body->AddSlot().AutoHeight().Padding(0,6)[Label(TEXT("Choose an action. Costs and targets follow the battlefield rules."),14)];
    Body->AddSlot().AutoHeight()[Button(TEXT("RETURN TO BATTLEFIELD · ESC"),[this](){WarRoomOpen=false;Dirty=true;})];
    auto Actions=SNew(SScrollBox);
    const int32 Seat=Data.value("seat",0);
    const auto& Mine=Data["view"]["players"][Seat];
    for(const std::string Group:{"Required choices","General actions","Camps","People","Hand cards","Events"})
    {
        auto Entries=SNew(SVerticalBox);int32 Count=0;
        for(const auto& Action:Data["actions"])
        {
            const J Command=Action["command"];
            const int32 Source=Command.value("source",Command.value("card",0));
            std::string Category=Action.value("category",std::string())=="choice"?"Required choices":"General actions";
            if(Category!="Required choices") {
                for(const auto& Column:Mine["columns"])for(const auto& Card:Column)if(Card.value("id",0)==Source)
                    Category=Card.value("type",std::string())=="camp"?"Camps":"People";
                for(const auto& Card:Mine["hand"])if(Card.value("id",0)==Source)Category="Hand cards";
                for(const auto& Card:Mine["queue"])if(!Card.is_null()&&Card.value("id",0)==Source)Category="Events";
            }
            if(Category!=Group)continue;
            const int32 Revision=Data["view"].value("revision",-1);
            const FString Match=Text(Data.value("match_id",std::string()));
            FString Caption=Text(Action.value("label",std::string()));
            Caption+=FString::Printf(TEXT(" · %d whiskey"),Action.value("cost",0));
            if(Action.contains("target_detail"))Caption+=TEXT("\n")+Text(Action["target_detail"]);
            auto ActionButton=Button(Caption,[this,Command,Revision,Match]() {
                if(!Owner.IsValid())return;
                // Bind to the displayed position, not whichever revision exists
                // when a delayed click reaches the controller.
                Owner->ServerSubmit(Text(Command.dump()),Revision,Match);
                WarRoomOpen=false;SelectedSource=0;Dirty=true;
            });
            Entries->AddSlot().AutoHeight().Padding(0,3)[ActionButton];
#if !UE_BUILD_SHIPPING
            StatusButtons.Emplace(TEXT("war_action:")+Text(Command.dump()),ActionButton);
#endif
            ++Count;
        }
        if(Count){Actions->AddSlot().Padding(0,12,0,3)[Label(Text(Group),16,OldWestMasterStyle::Sand)];Actions->AddSlot()[Entries];}
    }
    if(Data["actions"].empty())Actions->AddSlot().Padding(0,12)[Label(TEXT("No legal actions right now. Watch the opponent or wait for a required response."),16)];
    Body->AddSlot().FillHeight(1.f)[Actions];
    return SNew(SBorder).BorderImage(FCoreStyle::Get().GetBrush("WhiteBrush"))
        .BorderBackgroundColor(FLinearColor(.012f,.02f,.026f,1.f)).Padding(18)[Body];
}

TSharedRef<SWidget> SOldWestHUD::AbilityReference(const J& Data)
{
    auto Body=SNew(SVerticalBox);
    Body->AddSlot().AutoHeight()[Button(AbilityReferenceOpen?TEXT("HIDE ABILITY SUMMARIES"):TEXT("SHOW ABILITY SUMMARIES"),[this](){AbilityReferenceOpen=!AbilityReferenceOpen;Dirty=true;})];
    if(AbilityReferenceOpen) {
        auto List=SNew(SScrollBox);
        const int32 Seat=Data.value("seat",0);
        for(int32 Side:{Seat,1-Seat}) {
            List->AddSlot().Padding(0,8)[IconCopy(EOldWestHUDIcon::Shield,Side==Seat?TEXT("YOUR CARDS"):TEXT("ENEMY CARDS"),Side==Seat?OldWestMasterStyle::Aqua:OldWestMasterStyle::Pink,true)];
            J Cards=J::array();
            for(const auto& Column:Data["view"]["players"][Side]["columns"])for(const auto& Card:Column)Cards.push_back(Card);
            for(const auto& Card:Data["view"]["players"][Side]["queue"])if(!Card.is_null())Cards.push_back(Card);
            for(const auto& Card:Cards) {
                if(Card.value("destroyed",false))continue;
                const int32 Id=Card.value("id",0);
                auto Content=SNew(SVerticalBox);
                Content->AddSlot().AutoHeight()[Copy(Text(Card.value("name",std::string("Punk"))),16,OldWestMasterStyle::Sand,true)];
                const FString State=OldWestReadiness::Label(Card);
                if(!State.IsEmpty())Content->AddSlot().AutoHeight().Padding(0,4)[IconCopy(EOldWestHUDIcon::Event,State,State==TEXT("Ready")?OldWestMasterStyle::Aqua:Gold,true)];
                const bool Punk=Card.value("punk",false);
                const J* Def=Punk?nullptr:CardDefinition(Card.value("card_id",std::string()));
                if(Punk)Content->AddSlot().AutoHeight().Padding(0,4)[IconCopy(EOldWestHUDIcon::Shield,TEXT("Covers; first hit destroys"),OldWestMasterStyle::Muted)];
                if(Def) {
                    const FString Trait=Text(Def->value("trait",std::string()));
                    if(!Trait.IsEmpty())Content->AddSlot().AutoHeight().Padding(0,4)[IconCopy(EOldWestHUDIcon::Shield,Trait,Gold)];
                    if(Def->contains("effect"))Content->AddSlot().AutoHeight().Padding(0,4)[IconCopy(EOldWestHUDIcon::Event,Text((*Def)["effect"]),OldWestMasterStyle::Sand)];
                }
                const J Abilities=Card.value("public_abilities",Def?Def->value("abilities",J::array()):J::array());
                for(const auto& Ability:Abilities) {
                    Content->AddSlot().AutoHeight().Padding(0,8,0,3)[IconCopy(EOldWestHUDIcon::Water,FString::Printf(TEXT("%d WHISKEY"),Ability.value("cost",0)),OldWestMasterStyle::Aqua,true)];
                    Content->AddSlot().AutoHeight().Padding(26,0,0,3)[Copy(Text(Ability.value("effect",std::string())),13,OldWestMasterStyle::Sand)];
                }
                if(Card.value("damage",0)>0)Content->AddSlot().AutoHeight().Padding(0,6)[IconCopy(EOldWestHUDIcon::Attack,Card.value("type",std::string())=="camp"?TEXT("Damaged · hit alone does not block holding abilities"):TEXT("Wounded · ordinary abilities unavailable"),OldWestMasterStyle::Pink)];
                List->AddSlot().Padding(0,4)[SNew(SButton).ButtonStyle(&OldWestMasterStyle::ActionButtonStyle()).ContentPadding(FMargin(12,10))
                    .OnClicked_Lambda([this,Id](){PlayUiSound(false);ClickCard(Id);return FReply::Handled();})[Content]];
            }
        }
        Body->AddSlot().FillHeight(1.f)[List];
    }
    return Body;
}
