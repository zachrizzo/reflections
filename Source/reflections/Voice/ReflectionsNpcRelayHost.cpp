#include "Voice/ReflectionsNpcRelayHost.h"
#include "HAL/FileManager.h"
#include "Misc/FileHelper.h"
#include "Dom/JsonObject.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"
#include "HAL/PlatformMisc.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Misc/Guid.h"
#include "Misc/Paths.h"
#include "Voice/ReflectionsNpcDialogueSettings.h"
#include "Voice/ReflectionsRealtimeVoiceComponent.h"

namespace
{
    FString GLaunchedTokenFile;  // this game's own ready file (the helper writes its port there once listening)
    bool GLaunched = false;
    FProcHandle GProcess;
    int32 GReadyPort = 0;
    bool GReportedExit = false;
    int32 GLaunchGeneration = 0;
    // HasGeminiKey is asked every frame (the talk prompt, the Settings status): read the file at most every 2 s.
    bool GHasKeyCached = false;
    double GHasKeyCheckedAt = -1.0e9;

    FString RelayFolder()
    {
        return FPaths::ConvertRelativePathToFull(FPaths::Combine(FPaths::ProjectContentDir(),
            GetDefault<UReflectionsNpcDialogueSettings>()->LocalRelayFolder));
    }
}

void UReflectionsNpcRelayHost::Initialize(FSubsystemCollectionBase& Collection)
{
    Super::Initialize(Collection);
    if (WantsHelper()) Launch();
}

bool UReflectionsNpcRelayHost::WantsHelper()
{
    const UReflectionsNpcDialogueSettings* Settings = GetDefault<UReflectionsNpcDialogueSettings>();
#if WITH_EDITOR
    const bool bWanted = Settings->bLaunchLocalRelay && Settings->bLaunchLocalRelayInEditor;
#else
    const bool bWanted = Settings->bLaunchLocalRelay;
#endif
    return bWanted && !FParse::Param(FCommandLine::Get(), TEXT("NoNpcRelay"));
}

FString UReflectionsNpcRelayHost::GetKeysPath()
{
#if WITH_EDITOR
    // Never inside Content/ in the editor (it could be committed): Saved/ is git-ignored.
    return FPaths::ConvertRelativePathToFull(FPaths::Combine(FPaths::ProjectSavedDir(), TEXT("NpcDialogue"), TEXT("keys.json")));
#else
    return FPaths::Combine(RelayFolder(), TEXT("keys.json"));
#endif
}

bool UReflectionsNpcRelayHost::HasGeminiKey()
{
    const double Now = FPlatformTime::Seconds();
    if (Now - GHasKeyCheckedAt < 2.0) return GHasKeyCached;
    GHasKeyCheckedAt = Now;
    GHasKeyCached = false;
    FString Text;
    if (!FFileHelper::LoadFileToString(Text, *GetKeysPath())) return false;
    TSharedPtr<FJsonObject> Json;
    if (!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text), Json) || !Json.IsValid()) return false;
    FString Key;
    if (!Json->TryGetStringField(TEXT("gemini_api_key"), Key)) return false;
    Key.TrimStartAndEndInline();
    // keys.json.example's placeholder has spaces in it; a real key has none.
    GHasKeyCached = Key.Len() >= 20 && !Key.Contains(TEXT(" "));
    return GHasKeyCached;
}

bool UReflectionsNpcRelayHost::SaveGeminiKey(const FString& InKey)
{
    const FString Key = InKey.TrimStartAndEnd();
    const FString Path = GetKeysPath();
    bool bOk = true;
    if (Key.IsEmpty())
    {
        IFileManager::Get().Delete(*Path, false, true, true);
        bOk = !FPaths::FileExists(Path);
    }
    else
    {
        IFileManager::Get().MakeDirectory(*FPaths::GetPath(Path), true);
        TSharedRef<FJsonObject> Json = MakeShared<FJsonObject>();
        Json->SetStringField(TEXT("gemini_api_key"), Key);
        FString Text;
        const TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&Text);
        FJsonSerializer::Serialize(Json, Writer);
        bOk = FFileHelper::SaveStringToFile(Text, *Path, FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);
    }
    GHasKeyCheckedAt = -1.0e9;  // the Settings status and the talk prompt see it at once
    // Never the key itself.
    UE_LOG(LogReflectionsNpcDialogue, Log, TEXT("NPC dialogue key %s."), !bOk ? TEXT("could not be saved") : Key.IsEmpty() ? TEXT("removed") : TEXT("saved"));
    if (bOk && WantsHelper())
    {
        StopHelper();
        Launch();
    }
    ++GLaunchGeneration;
    return bOk;
}

int32 UReflectionsNpcRelayHost::GetLaunchGeneration()
{
    return GLaunchGeneration;
}

bool UReflectionsNpcRelayHost::Launch()
{
    if (GLaunched) return true;  // one helper per game process
    const UReflectionsNpcDialogueSettings* Settings = GetDefault<UReflectionsNpcDialogueSettings>();
    const FString Folder = RelayFolder();
    const FString Exe = FPaths::Combine(Folder, TEXT("NpcDialogueRelay.exe"));
    const FString Keys = GetKeysPath();
    if (!FPaths::FileExists(Exe))
    {
        UE_LOG(LogReflectionsNpcDialogue, Log, TEXT("No NPC dialogue helper at %s; NPCs use baked lines."), *Exe);
        return false;
    }
    if (!FPaths::FileExists(Keys))
    {
        UE_LOG(LogReflectionsNpcDialogue, Log, TEXT("No keys.json for the NPC dialogue helper (add a Gemini API key in Settings); NPCs use baked lines."));
        return false;
    }
    // A fresh token per run, handed to the helper through the environment it inherits; the voice component reads it too.
    const FString Token = FGuid::NewGuid().ToString(EGuidFormats::Digits) + FGuid::NewGuid().ToString(EGuidFormats::Digits);
    FPlatformMisc::SetEnvironmentVar(TEXT("REFLECTIONS_VOICE_LOCAL_TOKEN"), *Token);
    const FString DataDir = FPaths::ConvertRelativePathToFull(FPaths::Combine(FPaths::ProjectSavedDir(), TEXT("NpcDialogue")));
    IFileManager::Get().MakeDirectory(*DataDir, true);
    // Per game process, so a second copy of the game never deletes this one's file.
    GLaunchedTokenFile = FPaths::Combine(DataDir, FString::Printf(TEXT("relay-%u.ready"), FPlatformProcess::GetCurrentProcessId()));
    IFileManager::Get().Delete(*GLaunchedTokenFile, false, true, true);
    GReadyPort = 0;
    GReportedExit = false;
    const int32 Port = Settings->LocalRelayPort;
    // The helper takes the first free port of Port..Port+10 (another program or game copy may hold Port).
    const FString Args = FString::Printf(TEXT("--port %d --port-fallbacks 10 --ready-file \"%s\" --data-dir \"%s\" --seed-dir \"%s\" --keys \"%s\" --parent-pid %u"),
        Port, *GLaunchedTokenFile, *DataDir, *FPaths::Combine(Folder, TEXT("seed")), *Keys, FPlatformProcess::GetCurrentProcessId());
    uint32 ProcessId = 0;
    GProcess = FPlatformProcess::CreateProc(*Exe, *Args, /*bLaunchDetached*/ false, /*bLaunchHidden*/ true,
        /*bLaunchReallyHidden*/ true, &ProcessId, /*PriorityModifier*/ 0, *Folder, nullptr, nullptr);
    if (!GProcess.IsValid())
    {
        UE_LOG(LogReflectionsNpcDialogue, Warning, TEXT("Could not start the NPC dialogue helper; NPCs use baked lines."));
        return false;
    }
    GLaunched = true;
    UReflectionsNpcDialogueSettings::SetLaunchedRelayUrl(FString::Printf(TEXT("ws://127.0.0.1:%d"), Port));
    UE_LOG(LogReflectionsNpcDialogue, Log, TEXT("Started the NPC dialogue helper (pid %u, port %d)."), ProcessId, Port);
    return true;
}

bool UReflectionsNpcRelayHost::IsLaunchedRelayRunning()
{
    return GLaunched;
}

bool UReflectionsNpcRelayHost::IsLaunchedRelayReady()
{
    if (!GLaunched) return false;
    if (GProcess.IsValid() && !FPlatformProcess::IsProcRunning(GProcess))
    {
        if (!GReportedExit)
        {
            GReportedExit = true;
            int32 Code = 0;
            FPlatformProcess::GetProcReturnCode(GProcess, &Code);
            UE_LOG(LogReflectionsNpcDialogue, Warning, TEXT("The NPC dialogue helper exited (code %d); NPCs use baked lines. See Saved/NpcDialogue/relay.log."), Code);
        }
        return false;
    }
    if (GReadyPort > 0) return true;
    FString Text;
    if (!FFileHelper::LoadFileToString(Text, *GLaunchedTokenFile)) return false;
    const int32 Port = FCString::Atoi(*Text.TrimStartAndEnd());
    if (Port <= 0 || Port > 65535) return false;
    GReadyPort = Port;
    UReflectionsNpcDialogueSettings::SetLaunchedRelayUrl(FString::Printf(TEXT("ws://127.0.0.1:%d"), Port));
    UE_LOG(LogReflectionsNpcDialogue, Log, TEXT("NPC dialogue helper listening on port %d."), Port);
    return true;
}

void UReflectionsNpcRelayHost::Deinitialize()
{
    StopHelper();
    Super::Deinitialize();
}

void UReflectionsNpcRelayHost::StopHelper()
{
    if (GProcess.IsValid())
    {
        if (FPlatformProcess::IsProcRunning(GProcess)) FPlatformProcess::TerminateProc(GProcess, true);
        FPlatformProcess::CloseProc(GProcess);
        GProcess = FProcHandle();
        UE_LOG(LogReflectionsNpcDialogue, Log, TEXT("Stopped the NPC dialogue helper."));
    }
    if (GLaunched)
    {
        GLaunched = false;
        GReadyPort = 0;
        UReflectionsNpcDialogueSettings::SetLaunchedRelayUrl(FString());
        IFileManager::Get().Delete(*GLaunchedTokenFile, false, true, true);
    }
}
