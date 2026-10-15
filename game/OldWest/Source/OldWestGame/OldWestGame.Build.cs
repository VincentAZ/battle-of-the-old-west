using UnrealBuildTool;

public class OldWestGame : ModuleRules
{
    public OldWestGame(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.NoPCHs;
        bUseUnity = false;
        bEnableExceptions = true;
        PublicDependencyModuleNames.AddRange(new[] { "Core", "CoreUObject", "Engine", "InputCore" });
        PrivateDependencyModuleNames.AddRange(new[] { "Slate", "SlateCore", "UMG", "LevelSequence", "MovieScene", "CinematicCamera", "AudioMixer", "Sockets", "ApplicationCore", "PhysicsCore", "RenderCore", "RHI" });
        RuntimeDependencies.Add("$(ProjectDir)/Content/Data/cards.json", StagedFileType.UFS);
        RuntimeDependencies.Add("$(ProjectDir)/Content/Data/rules-help.json", StagedFileType.UFS);
        RuntimeDependencies.Add("$(ProjectDir)/Content/Data/scientist-presentation.json", StagedFileType.UFS);
        if (Target.Platform == UnrealTargetPlatform.Win64)
            PublicSystemLibraries.AddRange(new[] { "Advapi32.lib", "Crypt32.lib" });
    }
}
