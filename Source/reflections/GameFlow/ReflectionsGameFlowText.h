#pragma once

#include "CoreMinimal.h"

/**
 * Every player-facing name the game-flow screens show (title, theme line, side names, Tarnish meter, tips, lose,
 * victory and credits text) lives in ONE String Table asset: /Game/UI/ST_GameFlowText. Edit an entry there to rename
 * something; no rebuild. A missing table or key falls back to the built-in default passed at the call site, so
 * the menus never show a missing-string marker. Keys are listed in ArtDirection/GameFlow/README.md.
 */
namespace ReflectionsFlowText
{
    /** Soft path of the table (loaded by path: /Game/UI must be cooked). */
    REFLECTIONS_API const TCHAR* TablePath();

    /** The table's text for Key, or Default when the table or key is missing. */
    REFLECTIONS_API FText Get(const TCHAR* Key, const FText& Default);

    /** A multi-line entry split into lines (credits lists). */
    REFLECTIONS_API TArray<FText> GetLines(const TCHAR* Key, const FText& Default);

    /** Drop cached lookups (after the table is edited while the game runs). */
    REFLECTIONS_API void Refresh();
}
