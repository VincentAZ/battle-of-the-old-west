using UnrealBuildTool;

public class OldWestGameTarget : TargetRules
{
    public OldWestGameTarget(TargetInfo Target) : base(Target)
    {
        Type = TargetType.Game;
        DefaultBuildSettings = BuildSettingsVersion.V7;
        IncludeOrderVersion = EngineIncludeOrderVersion.Unreal5_8;
        ExtraModuleNames.Add("OldWestGame");
    }
}
