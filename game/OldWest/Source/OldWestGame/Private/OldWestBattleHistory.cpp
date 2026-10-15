#include "OldWestHUD.h"
#include "OldWestMasterStyle.h"
#include "OldWestHUDIcon.h"
#include "OldWestSectionBody.h"
#include "OldWestDockPanel.h"
#include "Misc/ConfigCacheIni.h"
#include "Widgets/Input/SButton.h"
#include "Widgets/Layout/SBorder.h"
#include "Widgets/SBoxPanel.h"
#include "Widgets/Layout/SBox.h"
#include "Widgets/Layout/SScrollBox.h"
#include "Widgets/Text/STextBlock.h"
using J=nlohmann::ordered_json;
using namespace OldWestMasterStyle;

bool SOldWestHUD::SectionCollapsed(const FString& Key)
{
    if(const bool* Found=BattleSections.Find(Key))return *Found;
    bool Closed=false;
    if(GConfig&&Preferences()&&Preferences()->CanPersist())GConfig->GetBool(TEXT("OldWest.BattleSections"),*Key,Closed,GGameUserSettingsIni);
    BattleSections.Add(Key,Closed);
    return Closed;
}
TSharedRef<SWidget> SOldWestHUD::BattleSection(const FString& Key,const FString& Title,TSharedRef<SWidget> Content,bool ForceOpen)
{
    SectionCollapsed(Key);
    TSharedRef<SVerticalBox> Section=SNew(SVerticalBox);
    TSharedRef<SWidget> Header=SNew(SButton).ButtonStyle(&ActionButtonStyle()).ContentPadding(FMargin(6,4))
        .OnClicked_Lambda([this,Key,ForceOpen](){
            if(!ForceOpen) {
                const bool Closed=!SectionCollapsed(Key);BattleSections.Add(Key,Closed);
                if(GConfig&&Preferences()&&Preferences()->CanPersist()) {
                    GConfig->SetBool(TEXT("OldWest.BattleSections"),*Key,Closed,GGameUserSettingsIni);
                    GConfig->Flush(false,GGameUserSettingsIni);
                }
                Dirty=true;PlayUiSound(false);
            }
            return FReply::Handled();
        })[SNew(STextBlock).Text_Lambda([this,Key,Title,ForceOpen](){return FText::FromString((!ForceOpen&&SectionCollapsed(Key)?TEXT("+  "):TEXT("-  "))+Title);})
            .Font(FCoreStyle::GetDefaultFontStyle("Bold",14)).ColorAndOpacity(ForceOpen?Aqua:Muted)
            .OverflowPolicy(ETextOverflowPolicy::Ellipsis)];
    Section->AddSlot().AutoHeight().Padding(0,4,0,3)[Header];
    float DefaultHeight=160.f,Minimum=48.f;
    if(Key.EndsWith(TEXT("water"))) {DefaultHeight=28;Minimum=20;}
    else if(Key.EndsWith(TEXT("hand"))) {DefaultHeight=Key.StartsWith(TEXT("your"))?198:80;Minimum=70;}
    else if(Key.Contains(TEXT("column"))) {DefaultHeight=486;Minimum=80;}
    else if(Key.EndsWith(TEXT("formation"))) {DefaultHeight=540;Minimum=110;}
    else if(Key.EndsWith(TEXT("events"))) {DefaultHeight=104;Minimum=36;}
    else if(Key.EndsWith(TEXT("details"))) {DefaultHeight=220;Minimum=80;}
    else if(Key.StartsWith(TEXT("history"))) {DefaultHeight=260;Minimum=80;}
    else if(Key==TEXT("target.rules")) {DefaultHeight=100;Minimum=48;}
    else if(Key==TEXT("your.actions")) {DefaultHeight=ForceOpen?240:168;Minimum=ForceOpen?120:64;}
    const FString StateKey=Key==TEXT("your.actions")&&ForceOpen?TEXT("your.response"):Key;
    auto& Saved=SectionStates.FindOrAdd(StateKey);
    if(!Saved.IsValid()) {
        Saved=MakeShared<FOldWestSectionState>();Saved->Height=DefaultHeight;
        if(GConfig&&Preferences()&&Preferences()->CanPersist())GConfig->GetFloat(TEXT("OldWest.SectionHeights"),*StateKey,Saved->Height,GGameUserSettingsIni);
    }
    const TWeakPtr<SOldWestHUD> Weak=SharedThis(this);
    TSharedRef<SOldWestSectionBody> Wrapper=SNew(SOldWestSectionBody).SectionId(Key).State(Saved)
        .DefaultHeight(DefaultHeight).MinHeight(Minimum).ContentScrolls(Key==TEXT("your.actions"))
        .MaxHeight_Lambda([Weak,Key](){
            if(Key==TEXT("your.actions"))if(const auto HUD=Weak.Pin())if(const auto* P=HUD->PanelStates.Find(TEXT("master")))return float(FMath::Clamp((*P)->Size.Y-280.,120.,900.));
            return 900.f;
        })
        .OnHeightChanged_Lambda([Weak,StateKey](float Height){
            if(const auto HUD=Weak.Pin())if(GConfig&&HUD->Preferences()&&HUD->Preferences()->CanPersist()) {
                GConfig->SetFloat(TEXT("OldWest.SectionHeights"),*StateKey,Height,GGameUserSettingsIni);
                GConfig->Flush(false,GGameUserSettingsIni);
            }
        })
        .Visibility_Lambda([this,Key,ForceOpen](){return !ForceOpen&&SectionCollapsed(Key)?EVisibility::Collapsed:EVisibility::Visible;})[Content];
    Section->AddSlot().AutoHeight()[Wrapper];
    SectionBodies.Add(Wrapper);
#if !UE_BUILD_SHIPPING
    SectionButtons.Emplace(Key,Header);
#endif
    return Section;
}

TSharedRef<SWidget> SOldWestHUD::BattleHistory(const J& View,int32 Seat,bool Compact)
{
    TSharedRef<SVerticalBox> Main=SNew(SVerticalBox);
    if(!Compact)Main->AddSlot().AutoHeight().Padding(2,8)[Label(TEXT("Resolved in order · latest two turns per player\nDrawn cards and hidden drifter faces stay private."),11,Muted)];
    const J Entries=View.value("history",J::array());
    const int32 Current=View.value("turn",0);
    const int32 FirstTurn=FMath::Max(1,Current-3);
    const int32 SelectedTurn=FieldHistoryTurn==0?Current:FMath::Clamp(FieldHistoryTurn,FirstTurn,Current);
    if(Compact) {
        FieldHistoryRenderedSequences.Reset();
        auto Turns=SNew(SHorizontalBox);
        auto Older=Button(TEXT("< OLDER"),[this,SelectedTurn](){FieldHistoryTurn=SelectedTurn-1;Dirty=true;},TEXT("Previous retained turn"),SelectedTurn>FirstTurn);
        auto Newer=Button(TEXT("NEWER >"),[this,SelectedTurn,Current](){FieldHistoryTurn=SelectedTurn+1>=Current?0:SelectedTurn+1;Dirty=true;},TEXT("Next turn"),SelectedTurn<Current);
        auto Latest=Button(TEXT("LATEST"),[this](){FieldHistoryTurn=0;Dirty=true;},TEXT("Follow the current turn"),FieldHistoryTurn!=0);
        Turns->AddSlot().FillWidth(1).Padding(0,0,4,0)[Older];
        Turns->AddSlot().FillWidth(1).Padding(0,0,4,0)[Newer];
        Turns->AddSlot().FillWidth(1)[Latest];
        Main->AddSlot().AutoHeight().Padding(0,0,0,8)[Turns];
#if !UE_BUILD_SHIPPING
        StatusButtons.Emplace(TEXT("history_older"),Older);
        StatusButtons.Emplace(TEXT("history_newer"),Newer);
        StatusButtons.Emplace(TEXT("history_latest"),Latest);
#endif
        auto Navigation=SNew(SHorizontalBox);
        auto Ascending=Button(TEXT("OLDEST FIRST"),[this](){FieldHistoryAscending=true;Dirty=true;},FString(),true,FieldHistoryAscending);
        Navigation->AddSlot().FillWidth(1)[Ascending];
        auto Descending=Button(TEXT("NEWEST FIRST"),[this](){FieldHistoryAscending=false;Dirty=true;},FString(),true,!FieldHistoryAscending);
        Navigation->AddSlot().FillWidth(1)[Descending];
#if !UE_BUILD_SHIPPING
        StatusButtons.Emplace(TEXT("history_ascending"),Ascending);
        StatusButtons.Emplace(TEXT("history_descending"),Descending);
#endif
        Main->AddSlot().AutoHeight()[Navigation];
    }
    auto HistoryRows=SNew(SVerticalBox);
    const int32 TurnCount=FMath::Min(Current,4);
    for(int32 Index=0;Index<TurnCount;++Index) {
        const int32 Offset=Compact&&FieldHistoryAscending?TurnCount-1-Index:Index;
        const int32 Turn=Current-Offset;if(Turn<1)continue;
        if(Compact&&Turn!=SelectedTurn)continue;
        TSharedRef<SVerticalBox> Rows=SNew(SVerticalBox);
        int32 Count=0,Player=(Offset%2)?1-View.value("active_player",Seat):View.value("active_player",Seat);
        if(Compact)Main->AddSlot().AutoHeight().Padding(2,12,2,10)[Label(FString::Printf(TEXT("TURN %d · %s%s"),Turn,Player==Seat?TEXT("YOU"):TEXT("ENEMY"),Turn==Current?TEXT(" · CURRENT"):TEXT("")),16,Sand)];
        for(int32 EntryIndex=0;EntryIndex<int32(Entries.size());++EntryIndex) {
            const auto& E=Entries[Compact&&!FieldHistoryAscending?int32(Entries.size())-1-EntryIndex:EntryIndex];
            if(E.value("turn",-1)!=Turn)continue;
            ++Count;Player=E.value("active_player",Player);
            // Raw text here; the composed line is translated exactly once below.
            auto Raw=[&](const char* Key){return FString(UTF8_TO_TCHAR(E.value(Key,std::string()).c_str()));};
            const FString Kind=Raw("type"),Detail=Raw("detail").Replace(TEXT("\t"),TEXT("  ")).TrimStartAndEnd();
            const FString Source=Raw("source_name"),Target=Raw("target_name");
            const int32 Actor=E.value("player",-1);
            const FString Who=Actor<0?TEXT("GAME"):Actor==Seat?TEXT("YOU"):TEXT("ENEMY");
            FString Line=Detail;
            FLinearColor Color=Sand;
            if(Kind==TEXT("action")) {Line=Who+TEXT(" · ")+Detail;Color=Actor==Seat?Aqua:Sand;}
            else if(Kind==TEXT("choice"))Line=Who+TEXT(" · ")+Detail;
            else if(Kind==TEXT("ability"))Line=Source+(Target.IsEmpty()?TEXT(""):TEXT(" copies ")+Target)+TEXT(" · ")+Detail;
            else if(Kind==TEXT("damage")) {Line=Target+TEXT(" takes damage");if(!Source.IsEmpty())Line+=TEXT(" from ")+Source;Color=Pink;}
            else if(Kind==TEXT("destroy")) {Line=(Target.IsEmpty()?Detail:Target)+TEXT(" destroyed");Color=Pink;}
            else if(Kind==TEXT("restore"))Line=Target+TEXT(" restored")+(Source.IsEmpty()?FString():TEXT(" by ")+Source)+(E.value("ready",false)?TEXT(" · ready"):TEXT(" · not ready"));
            else if(Kind==TEXT("enter"))Line=Who+TEXT(" · ")+Target+TEXT(" enters column ")+FString::FromInt(E.value("column",0)+1);
            else if(Kind==TEXT("event_play"))Line=Who+TEXT(" queues ")+Source+FString::Printf(TEXT(" in slot %d"),E.value("queue_slot",0)+1);
            else if(Kind==TEXT("event_resolve")) {Line=Who+TEXT(" · ")+Source+TEXT(" resolves");Color=Aqua;}
            else if(Kind==TEXT("event_advance"))Line=Source+FString::Printf(TEXT(" · slot %d → %d"),E.value("from_slot",0)+1,E.value("to_slot",0)+1);
            else if(Kind==TEXT("draw_card"))Line=Who+TEXT(" draws 1 card");
            else if(Kind==TEXT("water"))Line=Who+TEXT(" gains ")+(Detail.IsEmpty()?TEXT("1"):Detail)+TEXT(" whiskey");
            else if(Kind==TEXT("payment"))Line=Who+TEXT(" · ")+Detail;
            else if(Kind==TEXT("store_water"))Line=Who+TEXT(" takes Hip Flask into hand");
            else if(Kind==TEXT("junk"))Line=Who+TEXT(" hocks ")+Detail;
            else if(Kind==TEXT("discard")||Kind==TEXT("reveal_discard"))Line=Who+TEXT(" discards ")+Detail;
            else if(Kind==TEXT("return"))Line=Target+TEXT(" returns to ")+(Actor==Seat?TEXT("your"):TEXT("enemy"))+TEXT(" hand");
            else if(Kind==TEXT("turn_start")) {Line=TEXT("Turn begins");Color=Aqua;}
            else if(Kind==TEXT("turn_end")) {Line=TEXT("Turn ends");Color=Muted;}
            else if(Kind==TEXT("raid_launch"))Line=Who+FString::Printf(TEXT(" launches the Stampede in slot %d"),E.value("queue_slot",1)+1);
            else if(Kind==TEXT("reshuffle"))Line=TEXT("Deck exhausted · shuffle the discard pile (once)");
            else if(Kind==TEXT("draw_game"))Line=TEXT("Game ends in a draw · deck exhausted again");
            else if(Kind==TEXT("move")||Kind==TEXT("recruit_id")||Kind==TEXT("hospital_id"))Line=Target+TEXT(" moves to column ")+FString::FromInt(E.value("column",0)+1);
            else if(Kind==TEXT("remove_ruin"))Line=Target+TEXT(" removed · its column can hold 3 crew");
            else if(Kind==TEXT("camp_advance"))Line=Source+(E.value("advance",0)==0?TEXT(" resets to the holding row"):FString::Printf(TEXT(" advances to row %d"),3-E.value("advance",0)));
            else if(Kind==TEXT("rearrange"))Line=TEXT("New formation takes effect");
            else if(Kind==TEXT("expose_all"))Line=TEXT("All cards on both sides are exposed this turn");
            else if(Kind==TEXT("reveal_person"))Line=Who+TEXT(" reveals ")+Detail+TEXT(" · enters ready");
            else if(Kind==TEXT("ready"))Line=Target+TEXT(" is ready");
            else if(Kind==TEXT("trait"))Line=Source+TEXT(" · ")+Detail;
            else if(Kind==TEXT("analysis_choice"))Line=TEXT("Revealed hock decision accepted");
            else if(Kind==TEXT("phase")||Kind==TEXT("cleanup"))Color=Muted;
            if(Line.IsEmpty())Line=Kind;
            if(E.contains("water")&&(Kind==TEXT("water")||Kind==TEXT("payment")||Kind==TEXT("cleanup")))
                Line+=FString::Printf(TEXT("  [whiskey: you %d · enemy %d]"),E["water"][Seat].get<int>(),E["water"][1-Seat].get<int>());
            TSharedRef<SHorizontalBox> Row=SNew(SHorizontalBox);
            Row->AddSlot().AutoWidth().Padding(0,0,8,0)[SNew(SBox).WidthOverride(Compact?28:22)[Label(FString::Printf(TEXT("%02d"),Count),Compact?13:10,Muted)]];
            const EOldWestHUDIcon Icon=(Kind==TEXT("damage")||Kind==TEXT("destroy")||Kind==TEXT("raid_launch"))?EOldWestHUDIcon::Attack:
                (Kind==TEXT("restore")||Kind==TEXT("ready"))?EOldWestHUDIcon::Repair:
                (Kind==TEXT("water")||Kind==TEXT("payment")||Kind==TEXT("store_water"))?EOldWestHUDIcon::Water:
                Kind==TEXT("enter")?EOldWestHUDIcon::Deploy:
                Kind.StartsWith(TEXT("event"))?EOldWestHUDIcon::Event:
                Kind.StartsWith(TEXT("turn"))?EOldWestHUDIcon::Turn:EOldWestHUDIcon::Cards;
            if(Icon==EOldWestHUDIcon::Repair||Icon==EOldWestHUDIcon::Water)Color=Aqua;
            Row->AddSlot().AutoWidth().Padding(0,2,8,0)[SNew(SOldWestHUDIcon).Kind(Icon).Color(Color).Size(Compact?20:16)];
            Row->AddSlot().FillWidth(1.f)[SNew(STextBlock).Text(FText::FromString(OldWestDisplay::Text(Line)))
                .Font(FCoreStyle::GetDefaultFontStyle("Regular",Compact?15:12)).ColorAndOpacity(Color)
                .AutoWrapText(true)];
            TSharedRef<SWidget> Entry=SNew(SBorder).BorderImage(FCoreStyle::Get().GetBrush("WhiteBrush"))
                .BorderBackgroundColor(Count%2?FLinearColor(.025f,.04f,.045f,1):FLinearColor(.035f,.05f,.055f,1)).Padding(Compact?FMargin(10,9):FMargin(6,5))[Row];
            if(Compact){HistoryRows->AddSlot().AutoHeight().Padding(0,0,0,3)[Entry];FieldHistoryRenderedSequences.Add(E.value("sequence",0));}
            else Rows->AddSlot().AutoHeight().Padding(0,0,0,2)[Entry];
        }
        if(Compact&&!Count)HistoryRows->AddSlot().AutoHeight().Padding(10)[Label(TEXT("No recorded actions for this turn."),15,Muted)];
        if(!Count)Rows->AddSlot().AutoHeight().Padding(6)[Label(TEXT("No recorded actions for this turn."),12,Muted)];
        const FString Title=FString::Printf(TEXT("%s · TURN %d · %s · %d entries"),Offset?TEXT("LAST"):TEXT("CURRENT"),Turn,Player==Seat?TEXT("YOU"):TEXT("ENEMY"),Count);
        if(!Compact)Main->AddSlot().AutoHeight()[BattleSection(Offset==0?FString(TEXT("history.current")):Offset==1?FString(TEXT("history.last")):FString::Printf(TEXT("history.older%d"),Offset),Title,Rows)];
    }
    if(Compact) {
        Main->AddSlot().FillHeight(1.f)[SNew(SScrollBox)
            .ScrollBarAlwaysVisible(true).AllowOverscroll(EAllowOverscroll::No)
            +SScrollBox::Slot()[HistoryRows]];
    }
    return Main;
}
