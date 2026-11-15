#include "Villain/ReflectionsVillainText.h"

#define LOCTEXT_NAMESPACE "ReflectionsVillain"

FText ReflectionsVillainText::BossName() { return LOCTEXT("BossName", "The Tarnish"); }

FText ReflectionsVillainText::BossSubtitle(const FText& WhiteSide)
{
    return FText::Format(LOCTEXT("BossSubtitle", "It rises from the cracked glass of {0}"), WhiteSide);
}

FText ReflectionsVillainText::FirstHost() { return LOCTEXT("FirstHost", "The Tarnish has taken a face. Watch for the burning eyes."); }

FText ReflectionsVillainText::Rift(const FText& Side)
{
    return FText::Format(LOCTEXT("Rift", "Someone tarnished slipped through into {0}."), Side);
}

FText ReflectionsVillainText::Cured() { return LOCTEXT("Cured", "The tarnish burns out of them."); }

FText ReflectionsVillainText::MirrorWholeTitle() { return LOCTEXT("BookTitle", "The Mirror Is Whole"); }

FText ReflectionsVillainText::MirrorWholeSubtitle(const FText& WhiteSide)
{
    return FText::Format(LOCTEXT("BookSubtitle", "The Final Spell is yours. The Tarnish waits at the top of {0}'s tower."), WhiteSide);
}

FText ReflectionsVillainText::Hint() { return LOCTEXT("Hint", "Ordinary spells barely touch it. Only the Final Spell can burn it out."); }

FText ReflectionsVillainText::Resist() { return LOCTEXT("Resist", "Your spell barely touches it. Use the Final Spell."); }

FText ReflectionsVillainText::PhaseTwo() { return LOCTEXT("PhaseTwo", "It tears loose from its shroud. Faster now."); }

FText ReflectionsVillainText::Unmade() { return LOCTEXT("Unmade", "The Final Spell burns the Tarnish out."); }

FText ReflectionsVillainText::VictoryTitle() { return LOCTEXT("Victory", "Victory"); }

FText ReflectionsVillainText::VictorySubtitle() { return LOCTEXT("VictorySub", "The Tarnish is burned out. Lanthorne is itself again."); }

FText ReflectionsVillainText::FinalPrompt(bool bGamepad, const FText& Status)
{
    const FText Key = bGamepad ? LOCTEXT("PadKey", "X") : LOCTEXT("KeyboardKey", "F");
    return FText::Format(LOCTEXT("FinalPrompt", "FINAL SPELL  [{0}]   {1}"), Key, Status);
}

FText ReflectionsVillainText::Recharging(float Seconds)
{
    FNumberFormattingOptions Format;
    Format.MinimumFractionalDigits = 1;
    Format.MaximumFractionalDigits = 1;
    return FText::Format(LOCTEXT("Recharging", "recharging {0}s"), FText::AsNumber(Seconds, &Format));
}

FText ReflectionsVillainText::NeedMana(int32 Mana) { return FText::Format(LOCTEXT("NeedMana", "needs {0} mana"), FText::AsNumber(Mana)); }

FText ReflectionsVillainText::Ready() { return LOCTEXT("Ready", "ready"); }

FText ReflectionsVillainText::FallbackSide(int32 Index)
{
    switch (Index)
    {
    case 0: return LOCTEXT("Gray", "Pewterside");
    case 1: return LOCTEXT("Red", "Giltside");
    default: return LOCTEXT("White", "Frostside");
    }
}

#undef LOCTEXT_NAMESPACE
