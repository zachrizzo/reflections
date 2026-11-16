#pragma once

#include "CoreMinimal.h"
#include "HAL/PlatformProcess.h"
#include "Subsystems/GameInstanceSubsystem.h"
#include "ReflectionsNpcRelayHost.generated.h"

/**
 * Starts the NPC dialogue relay as a local helper process (NpcDialogueRelay.exe, staged loose next to the game's
 * content) and stops it when the game exits. The game itself never holds an API key: the helper reads keys.json
 * from its own folder. No helper or no keys.json: nothing is started and NPCs answer with baked lines.
 * Editor builds use the Python relay (Tools/RealtimeVoice) unless bLaunchLocalRelayInEditor is set.
 */
UCLASS()
class REFLECTIONS_API UReflectionsNpcRelayHost : public UGameInstanceSubsystem
{
    GENERATED_BODY()
public:
    virtual void Initialize(FSubsystemCollectionBase& Collection) override;
    virtual void Deinitialize() override;

    /** True once the helper is listening (it writes this game's ready file with its port then), false if it died. */
    static bool IsLaunchedRelayReady();
    /** True while a helper was started by this game and is still starting or running. */
    static bool IsLaunchedRelayRunning();

    /** keys.json: next to the helper in a packaged game; Saved/NpcDialogue in the editor (never Content/: git). */
    static FString GetKeysPath();
    /** keys.json holds a gemini_api_key that looks real (the key itself is never logged or shown). */
    static bool HasGeminiKey();
    /** Writes keys.json with the player's key (empty: removes it) and restarts the helper: live talk, no game restart. */
    static bool SaveGeminiKey(const FString& Key);
    /** Goes up each time the helper is (re)started, so the voice system reconnects to it. */
    static int32 GetLaunchGeneration();

private:
    static bool Launch();
    static bool WantsHelper();
    static void StopHelper();
};
