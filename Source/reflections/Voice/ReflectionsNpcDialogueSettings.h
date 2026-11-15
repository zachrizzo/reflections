#pragma once

#include "CoreMinimal.h"
#include "UObject/Object.h"
#include "UObject/SoftObjectPath.h"
#include "ReflectionsNpcDialogueSettings.generated.h"

/**
 * NPC talk-back configuration, read from [/Script/reflections.ReflectionsNpcDialogueSettings] in DefaultGame.ini.
 *
 * The game never holds an API key: it talks to a dialogue relay (Tools/RealtimeVoice) at RelayUrl. Editor
 * builds use EditorRelayUrl (the loopback development relay). With no URL, or when the relay cannot be
 * reached, NPCs answer with the baked voice barks in FallbackCues and nothing is shown about the failure.
 * Command-line overrides: -NpcRelayUrl=<ws(s)://...> and -NpcRelayTokenFile=<path> (loopback relays only).
 */
UCLASS(config=Game, defaultconfig)
class REFLECTIONS_API UReflectionsNpcDialogueSettings : public UObject
{
    GENERATED_BODY()
public:
    UReflectionsNpcDialogueSettings();

    /** Relay for packaged builds (wss://... for a hosted relay). Empty: baked barks only, no network use. */
    UPROPERTY(config, EditAnywhere, Category="Relay")
    FString RelayUrl;
    /** Relay for editor builds (Play in Editor). */
    UPROPERTY(config, EditAnywhere, Category="Relay")
    FString EditorRelayUrl = TEXT("ws://127.0.0.1:8765");
    /** Sent to a hosted relay. Not a secret (anything in a build can be read); it only filters stray clients. */
    UPROPERTY(config, EditAnywhere, Category="Relay")
    FString ClientKey;
    /** From pressing talk to the relay being ready; past this the NPC answers with a bark. */
    UPROPERTY(config, EditAnywhere, Category="Relay", meta=(Units="s"))
    float ConnectTimeoutSeconds = 6.0f;
    /** After a failed connection, barks only for this long before trying the relay again. */
    UPROPERTY(config, EditAnywhere, Category="Relay", meta=(Units="s"))
    float RelayRetrySeconds = 30.0f;

    UPROPERTY(config, EditAnywhere, Category="Talk", meta=(Units="cm"))
    float TalkRadius = 450.0f;
    UPROPERTY(config, EditAnywhere, Category="Talk", meta=(Units="s"))
    float MaxRecordSeconds = 15.0f;
    UPROPERTY(config, EditAnywhere, Category="Talk")
    bool bShowSubtitles = true;
    /** NPC lines are subtitled only while the speaker is this close (the conversation partner included). */
    UPROPERTY(config, EditAnywhere, Category="Talk", meta=(Units="cm"))
    float SubtitleRadius = 1500.0f;
    /** Every reply plays from the NPC's head with this attenuation (audio session's NPC voice falloff). */
    UPROPERTY(config, EditAnywhere, Category="Talk")
    FSoftObjectPath VoiceAttenuation = FSoftObjectPath(TEXT("/Game/Audio/Jam/Mix/ATT_Jam_NPCVoice.ATT_Jam_NPCVoice"));
    /** Turn the NPC to face the player while they talk (calm, alert or curious NPCs only). */
    UPROPERTY(config, EditAnywhere, Category="Talk")
    bool bFaceSpeaker = true;

    /**
     * Barks per persona group and mood when no relay answers: keys like Civilian_Talk, Civilian_Fear, Guard_Talk.
     * For *_Talk keys the NPC's own voice slot is tried first (SCue_VO_Civilian_Talk_F2), then the unslotted cue.
     */
    UPROPERTY(config, EditAnywhere, Category="Fallback")
    TMap<FName, FSoftObjectPath> FallbackCues;

    /** Start the local helper (NpcDialogueRelay.exe + keys.json under Content/<LocalRelayFolder>) with the game. */
    UPROPERTY(config, EditAnywhere, Category="Relay")
    bool bLaunchLocalRelay = true;
    /** Also start it in the editor (normally the Python relay from Tools/RealtimeVoice is used there). */
    UPROPERTY(config, EditAnywhere, Category="Relay")
    bool bLaunchLocalRelayInEditor = false;
    UPROPERTY(config, EditAnywhere, Category="Relay")
    int32 LocalRelayPort = 8765;
    UPROPERTY(config, EditAnywhere, Category="Relay")
    FString LocalRelayFolder = TEXT("NpcDialogue/Relay");

    /** -NpcRelayUrl, else the helper this game started, else EditorRelayUrl in editor builds, else RelayUrl. */
    static FString ResolveRelayUrl();
    static void SetLaunchedRelayUrl(const FString& Url);
    static bool IsLoopbackUrl(const FString& Url);
};
