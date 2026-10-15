using UnrealBuildTool;

public class OldWestGameEditorTarget : TargetRules
{
    public OldWestGameEditorTarget(TargetInfo Target) : base(Target)
    {
        Type = TargetType.Editor;
        DefaultBuildSettings = BuildSettingsVersion.V7;
        IncludeOrderVersion = EngineIncludeOrderVersion.Unreal5_8;
        ExtraModuleNames.Add("OldWestGame");
    }
}
