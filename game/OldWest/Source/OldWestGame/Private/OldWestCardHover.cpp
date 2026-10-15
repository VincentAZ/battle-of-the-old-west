#include "OldWestHUD.h"
#include "OldWestDisplayNames.h"
#include "OldWestAssetHistory.h"
#include "OldWestTooltip.h"
#include "Widgets/Input/SComboButton.h"
#include "Widgets/SNullWidget.h"
#include "Core/OldWestFieldActions.h"
#include "OldWestReadiness.h"
#include "OldWestSession.h"
#include "OldWestWorldInteraction.h"
#include "OldWestMasterStyle.h"
#include "OldWestDockPanel.h"
#include "Framework/Application/SlateApplication.h"
#include "Widgets/Layout/SBox.h"
#include "Widgets/Layout/SBorder.h"
#include "Widgets/Layout/SScaleBox.h"
#include "Widgets/SBoxPanel.h"
#include "Widgets/Text/STextBlock.h"
#include "Widgets/Layout/SConstraintCanvas.h"
using J=nlohmann::ordered_json;
using namespace OldWestMasterStyle;

TSharedRef<SWidget> SOldWestHUD::AssetHistoryControl(const J& Card, bool InBattlePlan)
{
    const auto* Note=OldWestAssetHistory::ForVisibleCard(Card);
    if(!Note)return SNullWidget::NullWidget;
    const FString Title=UTF8_TO_TCHAR(Note->Title),Body=UTF8_TO_TCHAR(Note->Body);
    const FString Source=Note->Attribution ? FString(UTF8_TO_TCHAR(Note->Attribution)) : FString(UTF8_TO_TCHAR(Note->Source))+TEXT("\n")+UTF8_TO_TCHAR(Note->Url);
    const auto* Related=Note->RelatedKey?OldWestAssetHistory::ForAsset(Note->RelatedKey):nullptr;
    const auto* Wound=OldWestAssetHistory::ForVisibleWound(Card);
    auto Content=SNew(SVerticalBox);
    auto AddNote=[&Content](const FString& Heading,const FString& Text,const FString& Sources)
    {
        Content->AddSlot().AutoHeight().Padding(0,7,0,0)[SNew(STextBlock).Text(FText::FromString(Heading)).WrapTextAt(560.f)
            .Font(FCoreStyle::GetDefaultFontStyle("Bold",12)).ColorAndOpacity(Sand)];
        Content->AddSlot().AutoHeight().Padding(0,7,0,0)[SNew(STextBlock).Text(FText::FromString(Text)).WrapTextAt(560.f)
            .Font(FCoreStyle::GetDefaultFontStyle("Regular",12)).ColorAndOpacity(Sand)];
        Content->AddSlot().AutoHeight().Padding(0,7,0,0)[SNew(STextBlock).Text(FText::FromString(TEXT("Source")))
            .Font(FCoreStyle::GetDefaultFontStyle("Regular",10)).ColorAndOpacity(Muted)
            .ToolTip(OldWestTooltip(FText::FromString(Sources)))];
    };
    AddNote(Title,Body,Source);
    if(Related) AddNote(UTF8_TO_TCHAR(Related->Title),UTF8_TO_TCHAR(Related->Body),
        Related->Attribution?FString(UTF8_TO_TCHAR(Related->Attribution)):FString(UTF8_TO_TCHAR(Related->Source))+TEXT("\n")+UTF8_TO_TCHAR(Related->Url));
    if(Wound) AddNote(UTF8_TO_TCHAR(Wound->Title),UTF8_TO_TCHAR(Wound->Body),UTF8_TO_TCHAR(Wound->Attribution));
    // A local, opt-in popup. No rule command, hover expansion or artwork overlay.
    auto Link=SNew(SComboButton)
        .ButtonStyle(FCoreStyle::Get(),"NoBorder").ContentPadding(FMargin(0,3))
        .HasDownArrow(false).ToolTip(OldWestTooltip(FText::FromString(TEXT("A short historical note"))))
        .ButtonContent()[SNew(STextBlock).Text(FText::FromString(TEXT("History")))
            .Font(FCoreStyle::GetDefaultFontStyle("Regular",11)).ColorAndOpacity(Aqua)]
        .MenuContent()[SNew(SBorder).BorderImage(FCoreStyle::Get().GetBrush("WhiteBrush"))
            .BorderBackgroundColor(FLinearColor(.012f,.020f,.026f,1)).Padding(14)
            [Content]];
#if !UE_BUILD_SHIPPING
    // Both inspector variants are constructed; report the active panel only.
    if(InBattlePlan==BattlePlanOpen) {
        AssetHistoryButton=Link;
        AssetHistoryNote={{"key",Note->Key},{"title",Note->Title},{"body",Note->Body},{"source",Note->Source},{"url",Note->Url},{"attribution",std::string(TCHAR_TO_UTF8(*Source))}};
        if(Related) AssetHistoryNote["related"]={{"key",Related->Key},{"title",Related->Title},{"body",Related->Body},
            {"source",Related->Source},{"url",Related->Url},{"attribution",Related->Attribution?Related->Attribution:""}};
        if(Wound) AssetHistoryNote["wound"]={{"key",Wound->Key},{"body",Wound->Body},{"url",Wound->Url}};
    }
    StatusButtons.Emplace(TEXT("asset_history"),Link);
#endif
    return Link;
}

bool SOldWestHUD::CardHoverEnabled() const
{
    const auto* Settings=Preferences();
    return !Settings||Settings->Read(Owner.IsValid()?Owner->GetWorld():nullptr).CardHover;
}
FString SOldWestHUD::CardGlanceText(const J& Card) const
{
    const bool Punk=Card.value("punk",false),Ruin=Card.value("destroyed",false);
    const J* Def=Punk?nullptr:CardDefinition(Card.value("card_id",std::string()));
    FString Info=Text(Card.value("name",std::string("Punk"))).ToUpper();
    Info+=TEXT("\n")+OldWestDisplay::TypeLabel(Card.value("type",std::string("person")));
    if(Card.value("zone",std::string())=="board") {
        Info+=Ruin?TEXT(" · BURNED OUT"):Card.value("damage",0)>0?
            (Card.value("type",std::string())=="person"?TEXT(" · WOUNDED"):TEXT(" · DAMAGED")):TEXT(" · UNDAMAGED");
        if(!Ruin) {
            Info+=TEXT(" · ")+OldWestReadiness::Label(Card);
            Info+=Card.value("protected",false)?TEXT("\nGuarded by the card in front"):TEXT("\nExposed to enemy fire");
            if(Card.contains("protected_by"))for(const auto& Guard:Card["protected_by"])
                Info+=TEXT("\n  ")+Text(Guard.value("name",std::string()))+(Guard.value("damage",0)>0?TEXT(" · damaged, still covers"):TEXT(" · covers this card"));
            if(Card.value("damage",0)>0)Info+=TEXT("\nNext hit destroys this card. Still covers cards behind it.");
        }
    } else if(Def&&Def->contains("play_cost")) {
        const int32 Printed=Def->value("play_cost",0);
        const int32 Price=Card.contains("play_availability")?Card["play_availability"].value("cost",Printed):Printed;
        Info+=FString::Printf(TEXT(" · Play %d whiskey"),Price);
        if(Price!=Printed)Info+=FString::Printf(TEXT(" (printed %d)"),Printed);
    }
    if(Def&&Def->contains("event_delay"))Info+=FString::Printf(TEXT(" · Delay %d"),Def->value("event_delay",0));
    if(Punk)Info+=TEXT("\n\nDRIFTER\nCovers cards behind it. First hit destroys it.");
    const FString Trait=Def?Text(Def->value("trait",std::string())):FString();
    if(!Trait.IsEmpty())Info+=(Card.value("type",std::string())=="person"&&Card.value("damage",0)>0?TEXT("\n\nTRAIT · INACTIVE WHILE DAMAGED\n"):TEXT("\n\nTRAIT\n"))+Trait;
    if(Def&&Def->contains("effect"))Info+=TEXT("\n\nEFFECT\n")+Text((*Def)["effect"]);
    J Abilities=Card.value("public_abilities",J::array());
    if(!Card.contains("public_abilities")&&Def)Abilities=Def->value("abilities",J::array());
    for(const auto& Ability:Abilities) {
        if(Ability.contains("activation_label"))Info+=TEXT("\n\n")+Text(Ability["activation_label"])+TEXT("\n")+Text(Ability.value("effect",std::string()));
        else Info+=FString::Printf(TEXT("\n\n%d WHISKEY · %s"),Ability.value("cost",0),*Text(Ability.value("effect",std::string())));
        if(Ability.contains("granted_by"))Info+=TEXT("\nGranted by ")+Text(Ability["granted_by"]);
        for(const auto& Status:Card.value("ability_availability",J::array()))if(Status["index"]==Ability["index"]&&!Status.value("available",false))Info+=TEXT("\n")+Text(Status.value("reason",std::string()));
    }
    if(Def&&Def->contains("junk"))Info+=OldWestDisplay::Text(TEXT("\n\nJUNK · ")+Text((*Def)["junk"]));
    // Only the owning player's authorized view contains this private face.
    // The public punk identity and its granted abilities above stay unchanged.
    if(Punk&&Card.contains("private_peek")) {
        const J& Peek=Card["private_peek"];
        Info+=TEXT("\n\nWANTED POSTER BOARD · PRIVATE INSPECTION\n")+Text(Peek.value("name",std::string()));
        if(Peek.contains("flip_cost"))Info+=FString::Printf(TEXT(" · Flip %d whiskey"),Peek.value("flip_cost",0));
        Info+=TEXT("\n")+CardDescription(Peek.value("card_id",std::string()));
        Info+=TEXT("\n\n")+(Peek.value("flip_available",false)
            ?TEXT("Select this drifter or Wanted Poster Board, then choose Flip in Your Actions. It enters ready in this space.")
            :Text(Peek.value("flip_reason",std::string())));
    }
    return Info;
}
TSharedRef<SWidget> SOldWestHUD::CardInspector(const J& Card)
{
    // Preserve every rule and availability reason, but separate identity from rules.
    // Explicit wrap widths give ScaleToFit a stable desired size without a scroll box.
    auto Copy=[](const FString& Value,int32 Size,float Width,bool Bold,FLinearColor Color)->TSharedRef<SWidget> {
        return SNew(STextBlock).Text(FText::FromString(Value))
            .Font(FCoreStyle::GetDefaultFontStyle(Bold?"Bold":"Regular",Size))
            .ColorAndOpacity(Color).WrapTextAt(Width);
    };
    TArray<FString> Sections;CardGlanceText(Card).ParseIntoArray(Sections,TEXT("\n\n"),true);
    TArray<FString> Identity;Sections[0].ParseIntoArrayLines(Identity);
    auto Summary=SNew(SVerticalBox);
    Summary->AddSlot().AutoHeight()[Copy(Identity[0],17,190,true,Sand)];
    for(int32 I=1;I<Identity.Num();++I)
        Summary->AddSlot().AutoHeight().Padding(0,I==1?6:3,0,0)
            [Copy(I==1?Identity[I].Replace(TEXT(" · "),TEXT("\n")):Identity[I],11,190,false,I==1?Sand:FLinearColor(.68f,.77f,.77f,1))];
    Summary->AddSlot().AutoHeight().HAlign(HAlign_Left).Padding(0,7,0,0)[AssetHistoryControl(Card)];
    auto Rules=SNew(SVerticalBox);
    for(int32 I=1;I<Sections.Num();++I) {
        FString Heading,Body;
        if(!Sections[I].Split(TEXT("\n"),&Heading,&Body)) {
            if(!Sections[I].Split(TEXT(" · "),&Heading,&Body)){Heading=TEXT("DETAIL");Body=Sections[I];}
        } else {
            // Cost and effect can share the first line; keep the cost in its own column.
            FString Cost,Effect;
            if(Heading.Split(TEXT(" · "),&Cost,&Effect)&&Cost.EndsWith(TEXT("WHISKEY"))) {
                Heading=Cost;Body=Effect+TEXT("\n")+Body;
            }
        }
        Rules->AddSlot().AutoHeight().Padding(0,I==1?0:7,0,0)
            [SNew(SHorizontalBox)
                +SHorizontalBox::Slot().AutoWidth()[SNew(SBox).WidthOverride(104)[Copy(Heading,11,100,true,FLinearColor(1.f,.78f,.40f,1))]]
                +SHorizontalBox::Slot().AutoWidth().Padding(10,0,0,0)[Copy(Body,12,444,false,Sand)]];
    }
    auto Content=SNew(SHorizontalBox)
        +SHorizontalBox::Slot().AutoWidth()[SNew(SBox).WidthOverride(190)[Summary]]
        +SHorizontalBox::Slot().AutoWidth().Padding(14,0)[SNew(SBox).WidthOverride(1)
            [SNew(SBorder).BorderImage(FCoreStyle::Get().GetBrush("WhiteBrush")).BorderBackgroundColor(FLinearColor(.3f,.4f,.4f,.6f))]]
        +SHorizontalBox::Slot().AutoWidth()[SNew(SBox).WidthOverride(558)[Rules]];
    return SNew(SBox).WidthOverride(801).MaxDesiredHeight(264)
        [SNew(SBorder).BorderImage(FCoreStyle::Get().GetBrush("WhiteBrush")).BorderBackgroundColor(FLinearColor(.012f,.020f,.026f,.96f)).Padding(12)
            [SNew(SScaleBox).Stretch(EStretch::ScaleToFit).StretchDirection(EStretchDirection::DownOnly)
                [SNew(SBox).WidthOverride(777)[Content]]]];
}

void SOldWestHUD::UpdateWorldHover(double Time)
{
    const FVector2D Cursor=FSlateApplication::Get().GetCursorPos();
    const bool Allowed=CardHoverEnabled()&&Owner.IsValid()&&(DraggedCard==INDEX_NONE||DraggedCard==-3002||DraggedCard==-4000||oldwest::IsWaterBundle(DraggedCard))&&!CameraDrag.IsValid()
        &&!PanelGestureActive()&&!OverviewOpen&&!SettingsOpen&&!HelpOpen&&SceneControlsVisible();
    if(!Allowed) {HoveredWorldCard=INDEX_NONE;WorldHoverVisible=false;WorldHoverText.Reset();return;}
    if(Time<NextHoverCheck)return;
    NextHoverCheck=Time+.08;
    float X=0,Y=0;
    J Card=nullptr;
    int32 Pick=INDEX_NONE;
    // The same non-interactive glance is used for panel cards and world actors.
    for(const auto& Entry:CardHoverTargets) if(const auto Widget=Entry.Value.Pin())
        if(Widget->IsHovered()) {Card=Entry.Key;Pick=Card.value("id",INDEX_NONE);break;}
    if(Card.is_null()&&OverBattlefield(Cursor)) {
        const FVector2D Local=GetCachedGeometry().AbsoluteToLocal(Cursor);
        for(const auto& Label:BattlefieldLabels()) {
            if(Label.value("decorative",false))continue;
            const auto& Rect=Label["rect"];
            if(Local.X>=Rect[0].get<double>()&&Local.X<=Rect[2].get<double>()&&Local.Y>=Rect[1].get<double>()&&Local.Y<=Rect[3].get<double>()) {Pick=Label["id"];break;}
        }
        if(Pick==INDEX_NONE)Pick=Owner->GetMousePosition(X,Y)?OldWestWorldInteraction::PickVisibleUnitAtScreen(Owner.Get(),FVector2D(X,Y)):INDEX_NONE;
        try {
            const J Data=J::parse(TCHAR_TO_UTF8(*Owner->GetPresentationSnapshot()));
            if(Data.contains("view"))
            {
                for(const auto& Player:Data["view"]["players"])
                {
                    for(const auto& Column:Player["columns"])for(const auto& Candidate:Column)if(Candidate.value("id",0)==Pick)Card=Candidate;
                    for(const auto& Candidate:Player["queue"])if(!Candidate.is_null()&&Candidate.value("id",0)==Pick)Card=Candidate;
                }
                for(const auto& Candidate:Data["view"]["players"][Data.value("seat",0)]["hand"])
                    if(Candidate.value("id",0)==Pick)Card=Candidate;
            }
        }catch(const std::exception&){}
    }
    const int32 Valid=Card.is_null()?INDEX_NONE:Pick;
    if(Valid!=HoveredWorldCard) {HoveredWorldCard=Valid;HoverSince=Time;}
    WorldHoverVisible=Valid!=INDEX_NONE&&Time-HoverSince>=.4;
    WorldHoverText=Card.is_null()?FString():CardGlanceText(Card);
    if(!Card.is_null()&&Card.value("zone",std::string())=="board") {
        WorldHoverText=Text(Card.value("name",std::string("Punk"))).ToUpper();
        for(const auto& Ability:Card.value("public_abilities",J::array())) {
            WorldHoverText+=FString::Printf(TEXT("\n\n%d WHISKEY\n"),Ability.value("cost",0))+Text(Ability.value("effect",std::string()));
            if(Ability.contains("activation_label"))WorldHoverText+=TEXT("\n")+Text(Ability["activation_label"]);
            for(const auto& Status:Card.value("ability_availability",J::array()))
                if(Status["index"]==Ability["index"]&&!Status.value("available",false))
                    WorldHoverText+=TEXT("\n")+Text(Status.value("reason",std::string()));
        }
        if(Card.value("public_abilities",J::array()).empty())WorldHoverText=CardGlanceText(Card);
    }
    if(HoverCanvas.IsValid()) {
        const FGeometry& G=HoverCanvas->GetCachedGeometry();
        const FVector2D P=G.AbsoluteToLocal(Cursor), Bounds=G.GetLocalSize();
        const double Height=WorldHoverBox.IsValid()?FMath::Max(100.,double(WorldHoverBox->GetDesiredSize().Y)):200.;
        constexpr double Width=304.;
        double Left=P.X+18+Width<=Bounds.X?P.X+18:P.X-Width-18;
        // Panel card glances sit alongside the dock, leaving every formation
        // card visible. World glances continue to follow the hovered actor.
        for(const auto& Panel:DockPanels)if(Panel.IsValid()&&Panel->IsHovered()) {
            const auto& PG=Panel->GetCachedGeometry();
            const auto Min=G.AbsoluteToLocal(PG.LocalToAbsolute(FVector2D::ZeroVector));
            const auto Max=G.AbsoluteToLocal(PG.LocalToAbsolute(PG.GetLocalSize()));
            if(Min.X>=Width+12)Left=Min.X-Width-12;
            else if(Max.X+Width+12<=Bounds.X)Left=Max.X+12;
            break;
        }
        const double Top=P.Y+20+Height<=Bounds.Y?P.Y+20:P.Y-Height-18;
        WorldHoverPosition=FVector2D(FMath::Clamp(Left,0.,FMath::Max(0.,Bounds.X-Width)),
            FMath::Clamp(Top,0.,FMath::Max(0.,Bounds.Y-Height)));
    }
}
