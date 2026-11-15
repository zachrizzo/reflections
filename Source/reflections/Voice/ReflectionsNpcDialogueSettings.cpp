#include "Voice/ReflectionsNpcDialogueSettings.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"

UReflectionsNpcDialogueSettings::UReflectionsNpcDialogueSettings()
{
    // Voice cues from the audio session (/Game/Audio/Jam is always cooked). Missing ones are skipped.
    const auto Cue = [](const TCHAR* Name) {
        return FSoftObjectPath(FString::Printf(TEXT("/Game/Audio/Jam/Voice/Cues/%s.%s"), Name, Name));
    };
    FallbackCues.Add(TEXT("Civilian_Talk"), Cue(TEXT("SCue_VO_Civilian_Talk")));
    FallbackCues.Add(TEXT("Civilian_Fear"), Cue(TEXT("SCue_VO_Civilian_Fear")));
    FallbackCues.Add(TEXT("Guard_Talk"), Cue(TEXT("SCue_VO_Guard_Talk")));
    FallbackCues.Add(TEXT("Guard_Alert"), Cue(TEXT("SCue_VO_Guard_Alert")));
    FallbackCues.Add(TEXT("Guard_Attack"), Cue(TEXT("SCue_VO_Guard_Attack")));
    FallbackCues.Add(TEXT("Soldier_Talk"), Cue(TEXT("SCue_VO_Soldier_Talk")));
    FallbackCues.Add(TEXT("Soldier_Command"), Cue(TEXT("SCue_VO_Soldier_Command")));
    FallbackCues.Add(TEXT("Tarnished_Mutter"), Cue(TEXT("SCue_VO_Tarnished_Mutter")));
    FallbackCues.Add(TEXT("Tarnish_Taunt"), Cue(TEXT("SCue_VO_Tarnish_Taunt")));
}

namespace
{
    FString GLaunchedRelayUrl;

    /** "ws://host:port" or "wss://...". An unquoted ini value is cut at "//" and arrives as "ws:": treat as unset. */
    FString ValidUrl(const FString& Raw)
    {
        FString Url = Raw.TrimStartAndEnd().TrimQuotes();
        return (Url.StartsWith(TEXT("ws://")) || Url.StartsWith(TEXT("wss://"))) && Url.Len() > 8 ? Url : FString();
    }
}

FString UReflectionsNpcDialogueSettings::ResolveRelayUrl()
{
    FString Override;
    if (FParse::Value(FCommandLine::Get(), TEXT("NpcRelayUrl="), Override))
    {
        return ValidUrl(Override);
    }
    if (!GLaunchedRelayUrl.IsEmpty()) return GLaunchedRelayUrl;
    const UReflectionsNpcDialogueSettings* Settings = GetDefault<UReflectionsNpcDialogueSettings>();
#if WITH_EDITOR
    const FString Editor = ValidUrl(Settings->EditorRelayUrl);
    if (!Editor.IsEmpty()) return Editor;
    if (!Settings->EditorRelayUrl.IsEmpty()) return TEXT("ws://127.0.0.1:8765");  // a mangled value: the dev default
#endif
    return ValidUrl(Settings->RelayUrl);
}

void UReflectionsNpcDialogueSettings::SetLaunchedRelayUrl(const FString& Url)
{
    GLaunchedRelayUrl = Url;
}

bool UReflectionsNpcDialogueSettings::IsLoopbackUrl(const FString& Url)
{
    return Url.StartsWith(TEXT("ws://127.0.0.1:")) || Url.StartsWith(TEXT("ws://localhost:")) ||
        Url.StartsWith(TEXT("ws://[::1]:"));
}
