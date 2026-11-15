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

private:
    bool Launch();
};
