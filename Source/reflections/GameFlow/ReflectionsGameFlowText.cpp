#include "GameFlow/ReflectionsGameFlowText.h"

#include "HAL/PlatformTime.h"
#include "Internationalization/StringTable.h"
#include "Internationalization/StringTableCore.h"
#include "UObject/UObjectGlobals.h"

namespace ReflectionsFlowText
{
    namespace
    {
        struct FState
        {
            TWeakObjectPtr<UStringTable> Table;
            double NextLoadAttempt = 0.0;
            TMap<FString, FText> Cache;
        };

        FState& State()
        {
            static FState Instance;
            return Instance;
        }

        UStringTable* FindTable()
        {
            FState& S = State();
            if (S.Table.IsValid())
            {
                return S.Table.Get();
            }
            const double Now = FPlatformTime::Seconds();
            if (Now < S.NextLoadAttempt)
            {
                return nullptr;
            }
            S.NextLoadAttempt = Now + 10.0;  // a missing table costs one load attempt every 10 s
            UStringTable* Loaded = LoadObject<UStringTable>(nullptr, TablePath(), nullptr, LOAD_NoWarn | LOAD_Quiet);
            if (Loaded)
            {
                // Rooted: FText::FromStringTable resolves through the registered table at draw time.
                Loaded->AddToRoot();
                S.Table = Loaded;
                S.Cache.Reset();
            }
            return Loaded;
        }
    }

    const TCHAR* TablePath()
    {
        return TEXT("/Game/UI/ST_GameFlowText.ST_GameFlowText");
    }

    FText Get(const TCHAR* Key, const FText& Default)
    {
        FState& S = State();
        if (const FText* Hit = S.Cache.Find(Key))
        {
            return *Hit;
        }
        UStringTable* Table = FindTable();
        if (!Table)
        {
            // Cache the fallback too, so a missing table never means a load attempt from inside Slate paint
            // (Refresh() clears this after the table is created).
            S.Cache.Add(Key, Default);
            return Default;
        }
        FText Result = Default;
        FString Source;
        if (Table->GetStringTable()->GetSourceString(FTextKey(Key), Source) && !Source.IsEmpty())
        {
            Result = FText::FromStringTable(Table->GetStringTableId(), Key);
        }
        S.Cache.Add(Key, Result);
        return Result;
    }

    TArray<FText> GetLines(const TCHAR* Key, const FText& Default)
    {
        TArray<FString> Parts;
        Get(Key, Default).ToString().ParseIntoArrayLines(Parts, true);
        TArray<FText> Lines;
        for (const FString& Part : Parts)
        {
            Lines.Add(FText::FromString(Part.TrimStartAndEnd()));
        }
        return Lines;
    }

    void Refresh()
    {
        State().Cache.Reset();
        State().NextLoadAttempt = 0.0;
    }
}
