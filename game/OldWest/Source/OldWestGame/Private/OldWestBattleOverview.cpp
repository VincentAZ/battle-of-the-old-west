#include "OldWestDisplayNames.h"
#include "OldWestHUD.h"
#include "OldWestDockPanel.h"
#include "Widgets/Layout/SWrapBox.h"
#include "OldWestTooltip.h"
#include "OldWestSession.h"
#include "Styling/CoreStyle.h"
#include "Widgets/SBoxPanel.h"
#include "Widgets/Layout/SBorder.h"
#include "Widgets/Layout/SBox.h"
#include "Widgets/Layout/SScrollBox.h"
#include "Widgets/Input/SButton.h"
#include "Widgets/Text/STextBlock.h"

using J = nlohmann::ordered_json;
namespace {
FString Utf(const std::string& Value) { return OldWestDisplay::Text(FString(UTF8_TO_TCHAR(Value.c_str()))); }
const FLinearColor Ivory(.90f,.89f,.83f,1.f);
const FLinearColor Muted(.48f,.57f,.60f,1.f);
const FLinearColor Friendly(.22f,.80f,.73f,1.f);
const FLinearColor Hostile(.95f,.43f,.31f,1.f);
}

void SOldWestHUD::ToggleBattleOverview() { SetBattleOverview(!OverviewOpen); }
void SOldWestHUD::SetBattleOverview(bool Open)
{
    if (!Owner.IsValid() || Owner->IsCinematicBusy() || SettingsOpen || HelpOpen || DraggedCard != INDEX_NONE) return;
    J Data;
    try { Data=J::parse(TCHAR_TO_UTF8(*Owner->GetPresentationSnapshot())); } catch (const std::exception&) { return; }
    if (!Data.contains("view") || Data["view"].value("status",std::string()) != "actions") return;
    OverviewOpen=Open;
    Owner->SetOverviewCamera(Open);
    Dirty=true;
}

FMargin SOldWestHUD::OverviewResponsePadding() const
{
    if (!OverviewOpen || !(PendingChoice || (Owner.IsValid() && Owner->HasAnalysisChoiceView())))
        return FMargin(0);
    const auto* Overview = PanelStates.Find(TEXT("overview"));
    const auto* Response = PanelStates.Find(TEXT("master"));
    if (!Overview || !Overview->IsValid() || !Response || !Response->IsValid() || (*Overview)->bCollapsed)
        return FMargin(0);
    const auto& O = **Overview;
    const auto& R = **Response;
    // These are the dock's existing default inner-content insets: 1px frame,
    // 28px title, and ContentPadding(8,6,8,22). Read saved geometry only;
    // never move, resize or overwrite the player's two panel states.
    const FSlateRect Content(O.Position.X + 9, O.Position.Y + 35,
        O.Position.X + O.Size.X - 9, O.Position.Y + O.Size.Y - 23);
    const float Right = R.Position.X + R.Size.X;
    const float Bottom = R.Position.Y + (R.bCollapsed ? SOldWestDockPanel::HeaderHeight : R.Size.Y);
    constexpr float Gap = 16.f;
    if (Right + Gap <= Content.Left || R.Position.X - Gap >= Content.Right ||
        Bottom + Gap <= Content.Top || R.Position.Y - Gap >= Content.Bottom)
        return FMargin(0);
    // Choose a single clear reading area rather than hiding a formation under
    // the response. For the default right-hand dock this is the wide left area.
    // Recompute when the player moves/resizes either saved panel.
    const FSlateRect Candidates[] = {
        FSlateRect(Content.Left, Content.Top, FMath::Min(Content.Right, float(R.Position.X) - Gap), Content.Bottom),
        FSlateRect(FMath::Max(Content.Left, Right + Gap), Content.Top, Content.Right, Content.Bottom),
        FSlateRect(Content.Left, Content.Top, Content.Right, FMath::Min(Content.Bottom, float(R.Position.Y) - Gap)),
        FSlateRect(Content.Left, FMath::Max(Content.Top, Bottom + Gap), Content.Right, Content.Bottom)};
    FSlateRect Best = Content;
    float BestArea = 0.f;
    for (const FSlateRect& Candidate : Candidates)
    {
        const float Width = FMath::Max(0.f, Candidate.Right - Candidate.Left);
        const float Height = FMath::Max(0.f, Candidate.Bottom - Candidate.Top);
        if (Width * Height > BestArea) { Best = Candidate; BestArea = Width * Height; }
    }
    // If the player deliberately covers the entire overview there is no free
    // rectangle. Keep both panels editable so the chosen layout can be moved.
    if (BestArea <= 0.f) return FMargin(0);
    return FMargin(Best.Left - Content.Left, Best.Top - Content.Top,
        Content.Right - Best.Right, Content.Bottom - Best.Bottom);
}

TSharedRef<SWidget> SOldWestHUD::BattleOverview(const J& Data)
{
    const J& View=Data["view"];
    const int32 Seat=Data.value("seat",0);
    TSharedRef<SVerticalBox> Sheet=SNew(SVerticalBox);
    Sheet->AddSlot().AutoHeight().Padding(0,0,0,4)
        [Label(TEXT("Both outfits · all public abilities · highlighted abilities are available"),16,Muted)];
    for (int32 Row=0;Row<2;++Row)
    {
        const int32 Side=Row==0?1-Seat:Seat;
        const bool Own=Side==Seat;
        const J& Player=View["players"][Side];
        const FLinearColor Accent=Own?Friendly:Hostile;
        FString Queue;
        for(int32 Slot=0;Slot<3;++Slot) if(!Player["queue"][Slot].is_null())
        {
            if(!Queue.IsEmpty()) Queue+=TEXT("  ·  ");
            Queue+=FString::Printf(TEXT("%d: %s"),Slot+1,*Utf(Player["queue"][Slot].value("name",std::string("Event"))));
        }
        FString Heading=Own?TEXT("YOUR CREW"):TEXT("ENEMY CREW");
        Heading+=FString::Printf(TEXT("   %d whiskey   ·   %d cards"),Player.value("water",0),Player.value("hand_count",0));
        if(!Queue.IsEmpty()) Heading+=TEXT("   |   INCOMING ")+Queue;
        Sheet->AddSlot().AutoHeight().Padding(0,Row?8:0,0,4)[Label(Heading,18,Accent)];
        TSharedRef<SHorizontalBox> Lanes=SNew(SHorizontalBox);
        for(int32 Column=0;Column<3;++Column)
        {
            TSharedRef<SVerticalBox> Formation=SNew(SVerticalBox);
            Formation->AddSlot().AutoHeight().Padding(0,0,0,4)[Label(FString::Printf(TEXT("FORMATION %d · front to rear"),Column+1),14,Muted)];
            for(const auto& Card:Player["columns"][Column])
            {
                const int32 Id=Card.value("id",0);
                const bool Punk=Card.value("punk",false),Ruin=Card.value("destroyed",false);
                const J* Def=Punk?nullptr:CardDefinition(Card.value("card_id",std::string()));
                TSharedRef<SVerticalBox> Entry=SNew(SVerticalBox);
                FString State=Card.value("type",std::string())=="camp"?TEXT("Holding · "):TEXT("Crew member · ");
                State+=Ruin?TEXT("Burned-out"):Card.value("damage",0)>0?TEXT("! DAMAGED"):Card.value("ready",false)?TEXT("Ready"):TEXT("Spent");
                if(!Ruin) State+=Card.value("protected",false)?TEXT(" · Covered"):TEXT(" · Exposed");
                TSharedRef<SWrapBox> Title=SNew(SWrapBox).UseAllottedSize(true).InnerSlotPadding(FVector2D(8,0));
                Title->AddSlot().VAlign(VAlign_Center)
                    [Label(Utf(Card.value("name",std::string("Punk"))),18,Ruin?Muted:Ivory)];
                Title->AddSlot().VAlign(VAlign_Center)
                    [Label(State,13,Ruin?Muted:Accent)];
                Entry->AddSlot().AutoHeight()[Title];
                J Abilities=Card.value("public_abilities",J::array());
                if(!Card.contains("public_abilities")&&Def) Abilities=Def->value("abilities",J::array());
                for(size_t Index=0;Index<Abilities.size();++Index)
                {
                    const J& Ability=Abilities[Index];
                    J Command=nullptr;
                    const int32 AbilityIndex=Ability.value("index",int32(Index));
                    if(Own&&!Ruin) for(const auto& Action:Data["actions"])
                    {
                        const J& Candidate=Action["command"];
                        if(Candidate.value("type",std::string())=="activate"&&Candidate.value("source",0)==Id
                            &&Candidate.value("ability",-1)==AbilityIndex) {Command=Candidate;break;}
                    }
                    FString Effect=FString::Printf(TEXT("%d whiskey  ·  %s"),Ability.value("cost",0),*Utf(Ability.value("effect",std::string())));
                    if(Ability.contains("granted_by")) Effect+=TEXT("  [")+Utf(Ability["granted_by"])+TEXT("]");
                    if(!Command.is_null())
                        Entry->AddSlot().AutoHeight().Padding(0,1)
                            [SNew(SButton).ContentPadding(FMargin(6,3))
                                .ToolTip(OldWestTooltip(FText::FromString(TEXT("Use this ability"))))
                                .OnClicked_Lambda([this,Command](){PlayUiSound(false);SetBattleOverview(false);Send(Command);return FReply::Handled();})
                                [Label(Effect,16,Friendly)]];
                    else Entry->AddSlot().AutoHeight().Padding(0,1)[Label(Effect,16,Ruin?Muted:Ivory)];
                }
                FString Trait=Punk?TEXT("Shields the cards behind it. Destroyed by its first hit."):Def?Utf(Def->value("trait",std::string())):FString();
                if(!Trait.IsEmpty()) Entry->AddSlot().AutoHeight().Padding(0,2)[Label(Trait,16,Muted)];
                if(Abilities.empty()&&Trait.IsEmpty()) Entry->AddSlot().AutoHeight()[Label(TEXT("No activated ability"),16,Muted)];
                TSharedRef<SWidget> Tile=SNew(SBorder).BorderImage(FCoreStyle::Get().GetBrush("WhiteBrush"))
                    .BorderBackgroundColor(!Ruin&&Card.value("damage",0)>0?FLinearColor(.28f,.075f,.035f,.98f):FLinearColor(.025f,.037f,.043f,.97f)).Padding(FMargin(9,4))[Entry];
                Formation->AddSlot().AutoHeight().Padding(0,0,0,4)[Tile];
#if !UE_BUILD_SHIPPING
                OverviewCards.Emplace(FString::FromInt(Id),Tile);
#endif
            }
            Lanes->AddSlot().FillWidth(1.f).Padding(Column?8:0,0,Column==2?0:8,0)[Formation];
        }
        Sheet->AddSlot().AutoHeight()[Lanes];
    }
    return SNew(SBorder).BorderImage(FCoreStyle::Get().GetBrush("NoBrush"))
        .Padding_Lambda([this]() { return OverviewResponsePadding(); })
        [SNew(SScrollBox)+SScrollBox::Slot()[Sheet]];
}
