#pragma once

#include "CoreMinimal.h"

/**
 * Every player-visible villain string, in one place (ReflectionsVillainText.cpp). IP rename rows V1-V3
 * (ArtDirection/Submission/rename-table.md): the villain is "the Tarnish", called "it"; hosts are "tarnished";
 * never "London". Side names (Frostside...) come from the world-jump config, passed in as Side.
 */
namespace ReflectionsVillainText
{
    FText BossName();
    FText BossSubtitle(const FText& WhiteSide);
    FText FirstHost();
    FText Rift(const FText& Side);
    FText Cured();
    FText MirrorWholeTitle();
    FText MirrorWholeSubtitle(const FText& WhiteSide);
    FText Hint();
    FText Resist();
    FText PhaseTwo();
    FText Unmade();
    FText VictoryTitle();
    FText VictorySubtitle();
    FText FinalPrompt(bool bGamepad, const FText& Status);
    FText Recharging(float Seconds);
    FText NeedMana(int32 Mana);
    FText Ready();
    /** Fallback side names when no world-jump config is loaded. */
    FText FallbackSide(int32 Index);
}
