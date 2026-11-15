#include "Lives/ReflectionsPeopleBook.h"

#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "Misc/FileHelper.h"
#include "Misc/PackageName.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

DEFINE_LOG_CATEGORY_STATIC(LogReflectionsPeopleBook, Log, All);

namespace
{
    const TCHAR* BookAssetPath = TEXT("/Game/Lives/DA_PeopleBook.DA_PeopleBook");

    FString Str(const TSharedPtr<FJsonObject>& O, const TCHAR* Key, const FString& Default = FString())
    {
        FString Out;
        return O.IsValid() && O->TryGetStringField(Key, Out) ? Out : Default;
    }
    FName NameField(const TSharedPtr<FJsonObject>& O, const TCHAR* Key, FName Default = NAME_None)
    {
        const FString S = Str(O, Key);
        return S.IsEmpty() ? Default : FName(*S);
    }
    float Num(const TSharedPtr<FJsonObject>& O, const TCHAR* Key, float Default)
    {
        double Out = 0.0;
        return O.IsValid() && O->TryGetNumberField(Key, Out) ? static_cast<float>(Out) : Default;
    }
    TArray<FString> StringsOf(const TArray<TSharedPtr<FJsonValue>>& Values)
    {
        TArray<FString> Out;
        for (const TSharedPtr<FJsonValue>& V : Values)
        {
            FString S;
            if (V.IsValid() && V->TryGetString(S) && !S.IsEmpty()) Out.Add(S);
        }
        return Out;
    }
    TArray<FString> Strings(const TSharedPtr<FJsonObject>& O, const TCHAR* Key)
    {
        const TArray<TSharedPtr<FJsonValue>>* Values = nullptr;
        if (O.IsValid() && O->TryGetArrayField(Key, Values)) return StringsOf(*Values);
        TArray<FString> Out;
        const FString One = Str(O, Key);  // a single string is accepted where a list is expected
        if (!One.IsEmpty()) Out.Add(One);
        return Out;
    }
    TArray<FName> Names(const TSharedPtr<FJsonObject>& O, const TCHAR* Key)
    {
        TArray<FName> Out;
        for (const FString& S : Strings(O, Key)) Out.Add(FName(*S));
        return Out;
    }
    TSharedPtr<FJsonObject> Obj(const TSharedPtr<FJsonObject>& O, const TCHAR* Key)
    {
        const TSharedPtr<FJsonObject>* Out = nullptr;
        return O.IsValid() && O->TryGetObjectField(Key, Out) ? *Out : nullptr;
    }

    /** Where a story-book activity happens. */
    FName WhereForActivity(const FString& Do)
    {
        if (Do == TEXT("home") || Do == TEXT("sleep") || Do == TEXT("hide")) return TEXT("home");
        if (Do == TEXT("work") || Do == TEXT("guard") || Do == TEXT("patrol")) return TEXT("work");
        if (Do == TEXT("chat")) return TEXT("clique");
        return TEXT("haunt");  // eat, stroll, shop, errand...
    }

    TArray<FReflectionsScheduleStep> ParseSteps(const TArray<TSharedPtr<FJsonValue>>& Values)
    {
        TArray<FReflectionsScheduleStep> Steps;
        for (const TSharedPtr<FJsonValue>& V : Values)
        {
            if (!V.IsValid()) continue;
            FReflectionsScheduleStep Step;
            const TSharedPtr<FJsonObject>* O = nullptr;
            const TArray<TSharedPtr<FJsonValue>>* Block = nullptr;
            if (V->TryGetObject(O))
            {
                // {at, do, where}
                Step.At = Num(*O, TEXT("at"), 8.0f);
                const FString Do = Str(*O, TEXT("do"), TEXT("haunt")).ToLower();
                Step.Do = FName(*Do);
                const FString Where = Str(*O, TEXT("where"));
                const FString Lower = Where.ToLower();
                if (Where.IsEmpty()) Step.Where = WhereForActivity(Do);
                else Step.Where = (Lower == TEXT("home") || Lower == TEXT("work") || Lower == TEXT("haunt") || Lower == TEXT("social") || Lower == TEXT("clique"))
                    ? FName(*Lower) : FName(*Where);
            }
            else if (V->TryGetArray(Block) && Block->Num() >= 3)
            {
                // [start, end, activity] (story book templates; a block lasts until the next one starts)
                Step.At = static_cast<float>((*Block)[0]->AsNumber());
                const FString Do = (*Block)[2]->AsString().ToLower();
                Step.Do = FName(*Do);
                Step.Where = WhereForActivity(Do);
            }
            else continue;
            Step.At = FMath::Fmod(FMath::Max(0.0f, Step.At), 24.0f);
            Steps.Add(Step);
        }
        Steps.Sort([](const FReflectionsScheduleStep& A, const FReflectionsScheduleStep& B) { return A.At < B.At; });
        return Steps;
    }

    uint32 Mix(uint32 H, uint32 Salt) { return HashCombineFast(H, Salt * 0x9E3779B9u + 0x7F4A7C15u); }

    template <typename T>
    const T& PickFrom(const TArray<T>& List, uint32 H) { return List[H % static_cast<uint32>(List.Num())]; }

    FReflectionsScheduleStep MakeStep(float At, const TCHAR* Do, const TCHAR* Where)
    {
        FReflectionsScheduleStep S;
        S.At = At;
        S.Do = FName(Do);
        S.Where = FName(Where);
        return S;
    }

    FString KeyOf(const FString& Text)
    {
        FString Out;
        for (const TCHAR C : Text.ToLower())
            Out.AppendChar(FChar::IsAlnum(C) ? C : TEXT('_'));
        while (Out.ReplaceInline(TEXT("__"), TEXT("_"))) {}
        Out.TrimCharInline(TEXT('_'), nullptr);
        return Out.IsEmpty() ? FString(TEXT("townsfolk")) : Out;
    }

    FString Capitalised(const FString& Text)
    {
        FString Out = Text.TrimStartAndEnd();
        if (Out.Len() > 0) Out[0] = FChar::ToUpper(Out[0]);
        return Out;
    }

    void ParseJobs(const TArray<TSharedPtr<FJsonValue>>& Values, TArray<FReflectionsPeopleGenerator::FJob>& Out)
    {
        for (const TSharedPtr<FJsonValue>& V : Values)
        {
            FReflectionsPeopleGenerator::FJob Job;
            const TSharedPtr<FJsonObject>* O = nullptr;
            FString S;
            if (V.IsValid() && V->TryGetObject(O))
            {
                Job.Job = NameField(*O, TEXT("job"));
                if (Job.Job.IsNone()) continue;
                Job.Title = Str(*O, TEXT("jobTitle"), Job.Job.ToString());
                Job.Weight = FMath::Max(1, static_cast<int32>(Num(*O, TEXT("weight"), 1.0f)));
                Job.Schedule = NameField(*O, TEXT("schedule"));
                Job.Side = NameField(*O, TEXT("side"));
            }
            else if (V.IsValid() && V->TryGetString(S) && !S.IsEmpty())
            {
                Job.Job = FName(*KeyOf(S));
                Job.Title = Capitalised(S);
            }
            else continue;
            Out.Add(Job);
        }
    }
}

bool UReflectionsPeopleBookAsset::ImportFromFile(UReflectionsPeopleBookAsset* Asset, const FString& FilePath)
{
    if (!Asset) return false;
    FString Text;
    if (!FFileHelper::LoadFileToString(Text, *FilePath)) return false;
    FReflectionsPeopleBook Test;
    if (!Test.ParseJson(Text, FilePath)) return false;
    Asset->Modify();
    Asset->Json = Text;
    Asset->SourcePath = FilePath;
    return true;
}

const FReflectionsPerson* FReflectionsPeopleBook::FindNamed(FName Id) const
{
    return Named.FindByPredicate([Id](const FReflectionsPerson& P) { return P.Id == Id; });
}

const FReflectionsInfectionBand* FReflectionsPeopleBook::BandFor(float Fraction) const
{
    const FReflectionsInfectionBand* Best = nullptr;
    for (const FReflectionsInfectionBand& Band : InfectionBands)
        if (Fraction >= Band.From) Best = &Band;
    return Best;
}

float FReflectionsPeopleBook::StanceOpinion(const FString& InStance)
{
    const FString S = InStance.ToLower();
    if (S.IsEmpty()) return 0.0f;
    if (S.Contains(TEXT("hostile"))) return -0.4f;
    if (S.Contains(TEXT("resent")) || S.Contains(TEXT("sour")) || S.Contains(TEXT("suspicious"))) return -0.3f;
    if (S.Contains(TEXT("grudg")) || S.Contains(TEXT("grump")) || S.Contains(TEXT("guarded")) || S.Contains(TEXT("sardonic"))) return -0.1f;
    if (S.Contains(TEXT("worship")) || S.Contains(TEXT("reverent")) || S.Contains(TEXT("best friend"))) return 0.5f;
    if (S.Contains(TEXT("admir")) || S.Contains(TEXT("proud")) || S.Contains(TEXT("fond")) || S.Contains(TEXT("warm")) ||
        S.Contains(TEXT("delight")) || S.Contains(TEXT("grateful")) || S.Contains(TEXT("protective")) || S.Contains(TEXT("excited")))
        return 0.3f;
    if (S.Contains(TEXT("hope")) || S.Contains(TEXT("fascinat")) || S.Contains(TEXT("approval")) || S.Contains(TEXT("respect"))) return 0.15f;
    if (S.Contains(TEXT("wary"))) return -0.05f;
    return 0.05f;
}

FString FReflectionsPeopleBook::MarkerSide(FName Side)
{
    const FString S = Side.ToString();
    if (S.StartsWith(TEXT("Pew"))) return TEXT("Pew");
    if (S.StartsWith(TEXT("Frost"))) return TEXT("Frost");
    return TEXT("Gilt");
}

void FReflectionsPeopleBook::Load()
{
    Named.Reset();
    Schedules.Reset();
    Cliques.Reset();
    InfectionBands.Reset();
    NamedPlaces.Reset();
    StoryNames.Reset();
    Generator = FReflectionsPeopleGenerator();
    Source.Reset();
    AddBuiltIns();

    bool bLoaded = false;
#if WITH_EDITOR
    // In the editor the story file wins, so the writers' edits show on the next Play without a re-import.
    for (const FString& Rel : { FString(TEXT("ArtDirection/Story/people.json")), FString(TEXT("ArtDirection/Lives/people_stub.json")) })
    {
        const FString Path = FPaths::ConvertRelativePathToFull(FPaths::ProjectDir() / Rel);
        FString Text;
        if (FFileHelper::LoadFileToString(Text, *Path) && ParseJson(Text, Path))
        {
            bLoaded = true;
            break;
        }
    }
#endif
    if (!bLoaded && FPackageName::DoesPackageExist(TEXT("/Game/Lives/DA_PeopleBook")))
        if (const UReflectionsPeopleBookAsset* Asset = LoadObject<UReflectionsPeopleBookAsset>(nullptr, BookAssetPath))
            bLoaded = ParseJson(Asset->Json, Asset->SourcePath.IsEmpty() ? FString(BookAssetPath) : Asset->SourcePath);
    if (!bLoaded) Source = TEXT("built-in stub");
    UE_LOG(LogReflectionsPeopleBook, Log, TEXT("People book: %d named people, %d schedules, %d cliques, from %s"), Named.Num(), Schedules.Num(), Cliques.Num(), *Source);
}

bool FReflectionsPeopleBook::ParseJson(const FString& Text, const FString& InSource)
{
    TSharedPtr<FJsonObject> Root;
    if (!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text), Root) || !Root.IsValid())
    {
        UE_LOG(LogReflectionsPeopleBook, Warning, TEXT("People book %s is not valid JSON"), *InSource);
        return false;
    }
    // The story book has no day block: the game opens at dusk and runs one game hour per real minute.
    const bool bStoryBook = Root->HasField(TEXT("cliques")) || Root->HasField(TEXT("principals"));
    if (const TSharedPtr<FJsonObject> Day = Obj(Root, TEXT("day")))
    {
        RealMinutesPerDay = FMath::Clamp(Num(Day, TEXT("realMinutesPerDay"), RealMinutesPerDay), 1.0f, 240.0f);
        StartHour = FMath::Fmod(FMath::Max(0.0f, Num(Day, TEXT("startHour"), StartHour)), 24.0f);
    }
    else if (bStoryBook)
    {
        RealMinutesPerDay = 24.0f;
        StartHour = 18.0f;
    }

    // Schedules: {key: steps} (stub) or {templates: {key: [[start, end, activity]...]}} (story book).
    if (const TSharedPtr<FJsonObject> ScheduleObj = Obj(Root, TEXT("schedules")))
    {
        const TSharedPtr<FJsonObject> Templates = Obj(ScheduleObj, TEXT("templates"));
        for (const auto& Pair : (Templates.IsValid() ? Templates : ScheduleObj)->Values)
        {
            const TArray<TSharedPtr<FJsonValue>>* Steps = nullptr;
            if (FString(*Pair.Key).StartsWith(TEXT("_")) || !Pair.Value.IsValid() || !Pair.Value->TryGetArray(Steps)) continue;
            TArray<FReflectionsScheduleStep> Parsed = ParseSteps(*Steps);
            if (Parsed.Num() > 0) Schedules.Add(FName(*Pair.Key), MoveTemp(Parsed));
        }
    }

    // Tarnish bands.
    const TArray<TSharedPtr<FJsonValue>>* Bands = nullptr;
    if (Root->TryGetArrayField(TEXT("infection_bands"), Bands))
        for (const TSharedPtr<FJsonValue>& V : *Bands)
        {
            const TSharedPtr<FJsonObject>* O = nullptr;
            if (!V.IsValid() || !V->TryGetObject(O)) continue;
            FReflectionsInfectionBand Band;
            Band.Band = NameField(*O, TEXT("band"));
            const TArray<TSharedPtr<FJsonValue>>* Range = nullptr;
            if ((*O)->TryGetArrayField(TEXT("fraction"), Range) && Range->Num() >= 2)
            {
                Band.From = static_cast<float>((*Range)[0]->AsNumber());
                Band.To = static_cast<float>((*Range)[1]->AsNumber());
            }
            Band.StreetMood = Str(*O, TEXT("street_mood"));
            if (!Band.Band.IsNone()) InfectionBands.Add(Band);
        }
    InfectionBands.Sort([](const FReflectionsInfectionBand& A, const FReflectionsInfectionBand& B) { return A.From < B.From; });

    // Named places (story book markers), for generated townsfolk to hang out at.
    if (const TSharedPtr<FJsonObject> Markers = Obj(Root, TEXT("markers")))
    {
        if (const TSharedPtr<FJsonObject> Places = Obj(Markers, TEXT("named_places")))
            for (const auto& Pair : Places->Values) NamedPlaces.Add(FName(*Pair.Key));
        // Mk_ (story tags) -> the quest system's marker names (Spot_, Tower_, Home_).
        if (const TSharedPtr<FJsonObject> Names_ = Obj(Markers, TEXT("story_names")))
            for (const auto& Pair : Names_->Values)
            {
                FString To;
                if (Pair.Value.IsValid() && Pair.Value->TryGetString(To) && !To.IsEmpty()) StoryNames.Add(FName(*Pair.Key), FName(*To));
            }
    }

    // The player's name for persona text.
    const TArray<TSharedPtr<FJsonValue>>* Principals = nullptr;
    if (Root->TryGetArrayField(TEXT("principals"), Principals))
        for (const TSharedPtr<FJsonValue>& V : *Principals)
        {
            const TSharedPtr<FJsonObject>* O = nullptr;
            if (V.IsValid() && V->TryGetObject(O) && Str(*O, TEXT("role")).Contains(TEXT("hero")))
            {
                const FString Name = Str(*O, TEXT("name"));
                if (!Name.IsEmpty()) PlayerName = Name.Left(Name.Find(TEXT(" ")) > 0 ? Name.Find(TEXT(" ")) : Name.Len()) + TEXT(", the Silverer");
            }
        }

    // Cliques.
    const TArray<TSharedPtr<FJsonValue>>* CliqueList = nullptr;
    if (Root->TryGetArrayField(TEXT("cliques"), CliqueList))
        for (const TSharedPtr<FJsonValue>& V : *CliqueList)
        {
            const TSharedPtr<FJsonObject>* O = nullptr;
            if (!V.IsValid() || !V->TryGetObject(O)) continue;
            FReflectionsClique C;
            C.Id = NameField(*O, TEXT("id"));
            if (C.Id.IsNone()) continue;
            C.Name = Str(*O, TEXT("name"));
            C.Spot = NameField(*O, TEXT("spot"));
            if (const FName SpotStory = NameField(*O, TEXT("spot_story")); !C.Spot.IsNone() && !SpotStory.IsNone()) StoryNames.FindOrAdd(C.Spot) = SpotStory;
            C.Side = NameField(*O, TEXT("side"));
            C.Members = Names(*O, TEXT("members"));
            C.Dynamic = Str(*O, TEXT("dynamic"));
            Cliques.Add(C.Id, C);
        }

    // Generator: flat pools (stub) or per-side pools (story book).
    if (const TSharedPtr<FJsonObject> Gen = Obj(Root, TEXT("generator")))
    {
        FReflectionsPeopleGenerator G = Generator;
        auto Override = [](TArray<FString>& Into, TArray<FString> From) { if (From.Num()) Into = MoveTemp(From); };
        if (const TSharedPtr<FJsonObject> First = Obj(Gen, TEXT("firstNames")))
        {
            Override(G.Flat.FirstNamesF, Strings(First, TEXT("F")));
            Override(G.Flat.FirstNamesM, Strings(First, TEXT("M")));
        }
        Override(G.Flat.Surnames, Strings(Gen, TEXT("surnames")));
        Override(G.Quirks, Strings(Gen, TEXT("quirks")));
        Override(G.Quirks, Strings(Gen, TEXT("tics")));
        Override(G.Likes, Strings(Gen, TEXT("likes")));
        Override(G.Secrets, Strings(Gen, TEXT("secrets")));
        if (TArray<FName> H = Names(Gen, TEXT("haunts")); H.Num()) G.Flat.Haunts = H;
        if (TArray<FName> S = Names(Gen, TEXT("schedules")); S.Num()) G.Schedules = S;
        const TArray<TSharedPtr<FJsonValue>>* Range = nullptr;
        if (Gen->TryGetArrayField(TEXT("friendsPerPerson"), Range) && Range->Num() >= 2)
        {
            G.FriendsMin = FMath::Clamp(static_cast<int32>((*Range)[0]->AsNumber()), 0, 6);
            G.FriendsMax = FMath::Clamp(static_cast<int32>((*Range)[1]->AsNumber()), G.FriendsMin, 6);
        }
        // Traits: a flat list, or columns {A: [...], B: [...], C: [...]} to pick one from each.
        const TArray<TSharedPtr<FJsonValue>>* TraitList = nullptr;
        if (Gen->TryGetArrayField(TEXT("traits"), TraitList)) Override(G.Traits, StringsOf(*TraitList));
        else if (const TSharedPtr<FJsonObject> Columns = Obj(Gen, TEXT("traits")))
        {
            G.TraitColumns.Reset();
            for (const auto& Pair : Columns->Values)
            {
                const TArray<TSharedPtr<FJsonValue>>* Column = nullptr;
                if (!FString(*Pair.Key).StartsWith(TEXT("_")) && Pair.Value.IsValid() && Pair.Value->TryGetArray(Column))
                    if (TArray<FString> C = StringsOf(*Column); C.Num()) G.TraitColumns.Add(C);
            }
        }
        // Jobs: a flat list of {job, jobTitle...} or per side lists of titles.
        const TArray<TSharedPtr<FJsonValue>>* Jobs = nullptr;
        if (Gen->TryGetArrayField(TEXT("jobs"), Jobs))
        {
            TArray<FReflectionsPeopleGenerator::FJob> Parsed;
            ParseJobs(*Jobs, Parsed);
            if (Parsed.Num()) G.Flat.Jobs = Parsed;
        }
        // Per-side pools.
        const TSharedPtr<FJsonObject> NamesObj = Obj(Gen, TEXT("names"));
        const TSharedPtr<FJsonObject> JobsObj = Obj(Gen, TEXT("jobs"));
        const TSharedPtr<FJsonObject> StylesObj = Obj(Gen, TEXT("speech_styles"));
        const TSharedPtr<FJsonObject> FearsObj = Obj(Gen, TEXT("fears"));
        const TSharedPtr<FJsonObject> WantsObj = Obj(Gen, TEXT("wants"));
        TSet<FString> SideNames;
        for (const TSharedPtr<FJsonObject>& O : { NamesObj, JobsObj, StylesObj, FearsObj, WantsObj })
            if (O.IsValid()) for (const auto& Pair : O->Values) if (!FString(*Pair.Key).StartsWith(TEXT("_"))) SideNames.Add(FString(*Pair.Key));
        for (const FString& SideName : SideNames)
        {
            FReflectionsPeopleGenerator::FPools& Pools = G.Sides.FindOrAdd(FName(*SideName));
            if (const TSharedPtr<FJsonObject> N = Obj(NamesObj, *SideName))
            {
                Pools.FirstNamesF = Strings(N, TEXT("F"));
                Pools.FirstNamesM = Strings(N, TEXT("M"));
                Pools.Surnames = Strings(N, TEXT("surnames"));
            }
            const TArray<TSharedPtr<FJsonValue>>* List = nullptr;
            if (JobsObj.IsValid() && JobsObj->TryGetArrayField(SideName, List)) ParseJobs(*List, Pools.Jobs);
            if (StylesObj.IsValid()) Pools.SpeechStyles = Strings(StylesObj, *SideName);
            if (FearsObj.IsValid()) Pools.Fears = Strings(FearsObj, *SideName);
            if (WantsObj.IsValid()) Pools.Wants = Strings(WantsObj, *SideName);
            // Where people of this side hang out: the side's named public places.
            const FString Prefix = TEXT("Mk_") + MarkerSide(FName(*SideName)) + TEXT("_");
            for (const FName Place : NamedPlaces)
            {
                const FString P = Place.ToString();
                if (!P.StartsWith(Prefix)) continue;
                const FString Kind = P.RightChop(Prefix.Len());
                if (Kind.StartsWith(TEXT("Market")) || Kind.StartsWith(TEXT("Square")) || Kind.StartsWith(TEXT("Inn")) || Kind.StartsWith(TEXT("Steps")) ||
                    Kind.StartsWith(TEXT("Gate")) || Kind.StartsWith(TEXT("Lane")) || Kind.StartsWith(TEXT("Stop")))
                    Pools.Haunts.Add(Place);
            }
        }
        if (const TSharedPtr<FJsonObject> N = NamesObj)
            Override(G.NeverNames, Strings(N, TEXT("_never")));
        Generator = MoveTemp(G);
    }

    // People.
    const TArray<TSharedPtr<FJsonValue>>* People = nullptr;
    if (Root->TryGetArrayField(TEXT("people"), People))
    {
        Named.Reset();
        for (const TSharedPtr<FJsonValue>& V : *People)
        {
            const TSharedPtr<FJsonObject>* OPtr = nullptr;
            if (!V.IsValid() || !V->TryGetObject(OPtr)) continue;
            const TSharedPtr<FJsonObject>& O = *OPtr;
            FReflectionsPerson P;
            P.Id = NameField(O, TEXT("id"));
            if (P.Id.IsNone() || FindNamed(P.Id))
            {
                UE_LOG(LogReflectionsPeopleBook, Warning, TEXT("People book: skipping a person with no id or a duplicate id (%s)"), *P.Id.ToString());
                continue;
            }
            P.bNamed = true;
            P.Name = Str(O, TEXT("name"), P.Id.ToString());
            const FString Sex = Str(O, TEXT("sex")).Left(1).ToUpper();
            P.Sex = Sex == TEXT("M") ? FName(TEXT("M")) : Sex == TEXT("F") ? FName(TEXT("F")) : NAME_None;
            // Age: a band, or years (story book: age is years and age_band the band).
            P.Age = NameField(O, TEXT("age_band"));
            if (P.Age.IsNone())
            {
                double Years = 0.0;
                if (O->TryGetNumberField(TEXT("age"), Years)) P.Age = Years < 30.0 ? FName(TEXT("Young")) : Years < 65.0 ? FName(TEXT("Adult")) : FName(TEXT("Old"));
                else P.Age = NameField(O, TEXT("age"), TEXT("Adult"));
            }
            P.Side = NameField(O, TEXT("side"), TEXT("Giltside"));
            // Job: a key plus a title (stub), or one line of text (story book: "retired Silverer; sells candles").
            const FString JobText = Str(O, TEXT("job"), TEXT("townsfolk"));
            FString Title = Str(O, TEXT("jobTitle"));
            if (Title.IsEmpty())
            {
                FString Head = JobText, Tail;
                JobText.Split(TEXT(";"), &Head, &Tail);
                Title = Capitalised(Head);
            }
            P.JobTitle = Title;
            P.Job = Str(O, TEXT("jobTitle")).IsEmpty() ? FName(*KeyOf(P.JobTitle)) : FName(*JobText);
            P.Archetype = NameField(O, TEXT("archetype"));
            P.Look = Str(O, TEXT("look"));  // a string in the stub; the story book's look is an object (ignored)
            P.VoiceId = NameField(O, TEXT("voice_id"));
            P.LookRole = NameField(O, TEXT("look_role"));
            P.Home = NameField(O, TEXT("home"), FName(*(TEXT("Home_") + P.Id.ToString())));
            P.Work = NameField(O, TEXT("work"), FName(*(TEXT("Work_") + P.Job.ToString())));
            P.Haunts = Names(O, TEXT("haunts"));
            if (const TSharedPtr<FJsonObject> Markers = Obj(O, TEXT("markers")))
            {
                P.Home = NameField(Markers, TEXT("home"), P.Home);
                P.Work = NameField(Markers, TEXT("work"), P.Work);
                for (const FName H : Names(Markers, TEXT("haunt"))) P.Haunts.AddUnique(H);
                for (const FName H : Names(Markers, TEXT("haunts"))) P.Haunts.AddUnique(H);
                // The same places under the quest system's names (markers_story: Home_<id>, Spot_...).
                if (const TSharedPtr<FJsonObject> StoryMarkers = Obj(O, TEXT("markers_story")))
                {
                    // A home is the person's own (Home_<id>, a front door); the Mk_ home may be a shared generic one,
                    // so it is not a name for anybody else's door.
                    const FName StoryHome = NameField(StoryMarkers, TEXT("home"));
                    if (!StoryHome.IsNone()) P.Home = StoryHome;
                    for (const TCHAR* Key : { TEXT("work"), TEXT("haunt") })
                    {
                        const FName From = NameField(Markers, Key);
                        const FName To = NameField(StoryMarkers, Key);
                        if (!From.IsNone() && !To.IsNone()) StoryNames.FindOrAdd(From) = To;
                    }
                }
            }
            if (const TSharedPtr<FJsonObject> Pers = Obj(O, TEXT("personality")))
            {
                P.Personality.Traits = Strings(Pers, TEXT("traits"));
                P.Personality.Warmth = FMath::Clamp(Num(Pers, TEXT("warmth"), -1.0f), -1.0f, 1.0f);
                P.Personality.Courage = FMath::Clamp(Num(Pers, TEXT("courage"), -1.0f), -1.0f, 1.0f);
                P.Personality.Temper = FMath::Clamp(Num(Pers, TEXT("temper"), -1.0f), -1.0f, 1.0f);
                P.Personality.Chattiness = FMath::Clamp(Num(Pers, TEXT("chattiness"), -1.0f), -1.0f, 1.0f);
                P.SpeechStyle = Str(Pers, TEXT("speech_style"));
                P.Tics = Strings(Pers, TEXT("tics"));
                P.Quirk = P.Tics.Num() ? P.Tics[0] : FString();
                P.FavouriteWords = Strings(Pers, TEXT("favourite_words"));
                P.NeverSays = Strings(Pers, TEXT("never_says"));
            }
            else P.Personality.Traits = Strings(O, TEXT("traits"));
            if (P.SpeechStyle.IsEmpty()) P.SpeechStyle = Str(O, TEXT("speechStyle"));
            if (P.Quirk.IsEmpty()) P.Quirk = Str(O, TEXT("quirk"));
            P.Summary = Str(O, TEXT("summary"));
            // No summary in the book: the long form of the job, when it says more than the title.
            if (P.Summary.IsEmpty() && !Capitalised(JobText).Equals(P.JobTitle)) P.Summary = Capitalised(JobText) + TEXT(".");
            P.Likes = Strings(O, TEXT("likes"));
            P.Dislikes = Strings(O, TEXT("dislikes"));
            P.Fear = Str(O, TEXT("fear"));
            P.Want = Str(O, TEXT("want"));
            P.Secret = Str(O, TEXT("secret"));
            P.Knows = Strings(O, TEXT("knows"));
            if (const TSharedPtr<FJsonObject> Stance = Obj(O, TEXT("opinion_of_silverer")))
            {
                P.Stance = Str(Stance, TEXT("stance"));
                P.StanceLine = Str(Stance, TEXT("line"));
            }
            const TArray<TSharedPtr<FJsonValue>>* Family = nullptr;
            if (O->TryGetArrayField(TEXT("family"), Family))
                for (const TSharedPtr<FJsonValue>& K : *Family)
                {
                    const TSharedPtr<FJsonObject>* KO = nullptr;
                    FString KS;
                    FReflectionsKin Kin;
                    if (K.IsValid() && K->TryGetObject(KO))
                    {
                        Kin.Id = NameField(*KO, TEXT("id"));
                        Kin.Relation = Str(*KO, TEXT("relation"), TEXT("family"));
                    }
                    else if (K.IsValid() && K->TryGetString(KS))
                    {
                        Kin.Id = FName(*KS);
                        Kin.Relation = TEXT("family");
                    }
                    if (!Kin.Id.IsNone()) P.Family.Add(Kin);
                }
            P.Friends = Names(O, TEXT("friends"));
            P.Rivals = Names(O, TEXT("rivals"));
            const TArray<TSharedPtr<FJsonValue>>* Inline = nullptr;
            if (O->TryGetArrayField(TEXT("schedule"), Inline)) P.Schedule = ParseSteps(*Inline);
            else if (const TSharedPtr<FJsonObject> Sched = Obj(O, TEXT("schedule")))
            {
                P.ScheduleKey = NameField(Sched, TEXT("template"));
                const TArray<TSharedPtr<FJsonValue>>* Blocks = nullptr;
                if (Sched->TryGetArrayField(TEXT("blocks"), Blocks)) P.Schedule = ParseSteps(*Blocks);
            }
            else P.ScheduleKey = NameField(O, TEXT("schedule"));
            P.Quest = NameField(O, TEXT("quest"));
            if (const TSharedPtr<FJsonObject> Story = Obj(O, TEXT("story")))
            {
                P.Quests = Names(Story, TEXT("quests"));
                if (P.Quest.IsNone() && P.Quests.Num()) P.Quest = P.Quests[0];
            }
            P.Clique = NameField(O, TEXT("clique"));
            Named.Add(MoveTemp(P));
        }
    }

    // Derived fields: clique spots (and clique-mates' haunts), numbers from traits, relations both ways.
    for (FReflectionsPerson& A : Named)
    {
        if (const FReflectionsClique* C = Cliques.Find(A.Clique))
        {
            A.CliqueSpot = C->Spot;
            if (!C->Spot.IsNone()) A.Haunts.AddUnique(C->Spot);
        }
        // Unset personality numbers lean the way the traits and the archetype do (stable per person).
        uint32 H = GetTypeHash(A.Id.ToString());
        auto Unit = [&H]() { H = Mix(H, 0x51EDu); return 0.25f + static_cast<float>(H % 500u) / 999.0f; };
        FReflectionsPersonality& P = A.Personality;
        const FString Arch = A.Archetype.ToString();
        if (P.Warmth < 0.0f) P.Warmth = Unit();
        if (P.Courage < 0.0f) P.Courage = Arch == TEXT("Timid") ? 0.2f : (Arch == TEXT("Brave") || Arch == TEXT("Guard") || Arch == TEXT("Soldier")) ? 0.8f : Unit();
        if (P.Temper < 0.0f) P.Temper = Unit() * 0.8f;
        if (P.Chattiness < 0.0f) P.Chattiness = Unit();
        for (const FString& Trait : P.Traits)
        {
            const FString T = Trait.ToLower();
            if (T.Contains(TEXT("kind")) || T.Contains(TEXT("warm")) || T.Contains(TEXT("gentle")) || T.Contains(TEXT("generous")) || T.Contains(TEXT("loyal"))) P.Warmth = FMath::Max(P.Warmth, 0.7f);
            if (T.Contains(TEXT("cold")) || T.Contains(TEXT("suspicious")) || T.Contains(TEXT("unsentimental"))) P.Warmth = FMath::Min(P.Warmth, 0.35f);
            if (T.Contains(TEXT("brave")) || T.Contains(TEXT("bold")) || T.Contains(TEXT("stubborn")) || T.Contains(TEXT("fierce"))) P.Courage = FMath::Max(P.Courage, 0.7f);
            if (T.Contains(TEXT("timid")) || T.Contains(TEXT("nervous")) || T.Contains(TEXT("anxious")) || T.Contains(TEXT("fearful"))) P.Courage = FMath::Min(P.Courage, 0.3f);
            if (T.Contains(TEXT("hot")) || T.Contains(TEXT("bitter")) || T.Contains(TEXT("prickly")) || T.Contains(TEXT("grumbl")) || T.Contains(TEXT("sharp"))) P.Temper = FMath::Max(P.Temper, 0.65f);
            if (T.Contains(TEXT("gossip")) || T.Contains(TEXT("chatty")) || T.Contains(TEXT("nosy")) || T.Contains(TEXT("sociable")) || T.Contains(TEXT("loud"))) P.Chattiness = FMath::Max(P.Chattiness, 0.75f);
            if (T.Contains(TEXT("quiet")) || T.Contains(TEXT("shy")) || T.Contains(TEXT("gruff")) || T.Contains(TEXT("guarded"))) P.Chattiness = FMath::Min(P.Chattiness, 0.3f);
        }
        if (A.Haunts.Num() == 0)
            if (const FReflectionsPeopleGenerator::FPools* Pools = Generator.Sides.Find(A.Side))
                if (Pools->Haunts.Num()) A.Haunts.Add(PickFrom(Pools->Haunts, H));
    }
    for (FReflectionsPerson& A : Named)
    {
        for (const FReflectionsKin& Kin : A.Family)
            for (FReflectionsPerson& B : Named)
                if (B.Id == Kin.Id && !B.Family.ContainsByPredicate([&A](const FReflectionsKin& K) { return K.Id == A.Id; }))
                {
                    FReflectionsKin Back;
                    Back.Id = A.Id;
                    Back.Relation = TEXT("family");
                    B.Family.Add(Back);
                }
        for (const FName Friend : A.Friends)
            for (FReflectionsPerson& B : Named)
                if (B.Id == Friend) B.Friends.AddUnique(A.Id);
    }
    Source = InSource;
    return true;
}

FName FReflectionsPeopleBook::ScheduleForJob(const FString& JobTitle) const
{
    // Which day a generated job keeps: the story book's templates when it has them, else the built-in days.
    const FString J = JobTitle.ToLower();
    struct FRule { const TCHAR* Words; const TCHAR* Template; const TCHAR* BuiltIn; };
    static const FRule Rules[] = {
        { TEXT("soldier|captain|trooper|man-at-arms|men-at-arms|lancer|pikeman|sentry|shieldman|swordsman"), TEXT("soldier_watch"), TEXT("soldier_watch") },
        { TEXT("guard|watch|constable|sergeant"), TEXT("watch_day"), TEXT("guard_watch") },
        { TEXT("conductor|cab"), TEXT("conductor"), TEXT("day_worker") },
        { TEXT("laundry"), TEXT("laundry"), TEXT("day_worker") },
        { TEXT("nurse|healer|doctor"), TEXT("healer"), TEXT("day_worker") },
        { TEXT("innkeeper|tea-stall|tavern"), TEXT("innkeeper"), TEXT("day_worker") },
        { TEXT("musician|dancer|performer|singer|drummer"), TEXT("performer"), TEXT("idler") },
        { TEXT("scholar|student|apprentice|bookbinder|clerk"), TEXT("scholar"), TEXT("day_worker") },
        { TEXT("dock|labour|sweep|porter|ice|hauler"), TEXT("labourer"), TEXT("early_riser") },
        { TEXT("lamplighter|bell"), TEXT("lamplighter"), TEXT("night_owl") },
        { TEXT("pensioner|elder"), TEXT("elder_doorstep"), TEXT("idler") },
        { TEXT("maker|blower|tailor|gilder|seamstress|smith|carver"), TEXT("craft"), TEXT("day_worker") },
        { TEXT("seller|trader|vendor|baker|fishmonger|keeper|merchant"), TEXT("trader"), TEXT("early_riser") },
    };
    for (const FRule& Rule : Rules)
    {
        TArray<FString> Words;
        FString(Rule.Words).ParseIntoArray(Words, TEXT("|"));
        for (const FString& W : Words)
            if (J.Contains(W))
                return Schedules.Contains(FName(Rule.Template)) ? FName(Rule.Template) : FName(Rule.BuiltIn);
    }
    if (Schedules.Contains(FName(TEXT("errand")))) return TEXT("errand");
    return Generator.Schedules.Num() ? Generator.Schedules[GetTypeHash(J) % static_cast<uint32>(Generator.Schedules.Num())] : FName(TEXT("day_worker"));
}

FReflectionsPerson FReflectionsPeopleBook::Generate(FName Id, FName Sex, FName Age, FName Side, int32 Salt) const
{
    const FReflectionsPeopleGenerator& G = Generator;
    uint32 H = Mix(GetTypeHash(Id.ToString()), static_cast<uint32>(Salt));
    auto Next = [&H]() { H = Mix(H, 0xB5297A4Du); return H; };

    FReflectionsPerson P;
    P.Id = Id;
    P.bNamed = false;
    P.Side = !Side.IsNone() ? Side : FName(TEXT("Giltside"));
    const FReflectionsPeopleGenerator::FPools* SidePools = G.Sides.Find(P.Side);
    // Each pool from the side when it has one, else the flat pool.
    auto Pool = [&](auto Member) -> const auto& { return (SidePools && (SidePools->*Member).Num()) ? SidePools->*Member : G.Flat.*Member; };

    P.Sex = !Sex.IsNone() ? Sex : ((Next() & 1u) ? FName(TEXT("F")) : FName(TEXT("M")));
    const TArray<FString>& Firsts = P.Sex == TEXT("F") ? Pool(&FReflectionsPeopleGenerator::FPools::FirstNamesF) : Pool(&FReflectionsPeopleGenerator::FPools::FirstNamesM);
    const TArray<FString>& Lasts = Pool(&FReflectionsPeopleGenerator::FPools::Surnames);
    for (int32 Try = 0; Try < 8; ++Try)
    {
        const FString First = Firsts.Num() ? PickFrom(Firsts, Next()) : FString(TEXT("Ash"));
        const FString Last = Lasts.Num() ? PickFrom(Lasts, Next()) : FString(TEXT("Penn"));
        P.Name = First + TEXT(" ") + Last;
        if (!G.NeverNames.ContainsByPredicate([&](const FString& Never) { return First == Never || Last == Never; }) && !FindNamed(FName(*P.Name)) &&
            !Named.ContainsByPredicate([&P](const FReflectionsPerson& N) { return N.Name == P.Name; }))
            break;
    }
    static const FName Ages[] = { TEXT("Young"), TEXT("Adult"), TEXT("Adult"), TEXT("Adult"), TEXT("Old") };
    P.Age = !Age.IsNone() ? Age : Ages[Next() % 5];

    const TArray<FReflectionsPeopleGenerator::FJob>& Jobs = Pool(&FReflectionsPeopleGenerator::FPools::Jobs);
    int32 TotalWeight = 0;
    for (const auto& Job : Jobs)
    {
        // Generated townsfolk are civilians: soldiers and casters come from the squads.
        const FString T = Job.Title.ToLower();
        if (!T.Contains(TEXT("soldier")) && !T.Contains(TEXT("caster")) && !T.Contains(TEXT("captain"))) TotalWeight += Job.Weight;
    }
    const FReflectionsPeopleGenerator::FJob* Job = nullptr;
    if (TotalWeight > 0)
    {
        int32 Roll = static_cast<int32>(Next() % static_cast<uint32>(TotalWeight));
        for (const auto& J : Jobs)
        {
            const FString T = J.Title.ToLower();
            if (T.Contains(TEXT("soldier")) || T.Contains(TEXT("caster")) || T.Contains(TEXT("captain"))) continue;
            if ((Roll -= J.Weight) < 0) { Job = &J; break; }
        }
    }
    P.Job = Job ? Job->Job : FName(TEXT("townsfolk"));
    P.JobTitle = Job ? Job->Title : TEXT("Townsperson");
    P.ScheduleKey = Job && !Job->Schedule.IsNone() ? Job->Schedule : ScheduleForJob(P.JobTitle);

    // Places: their own home; work and haunts at the side's generic markers and named places.
    const FString S = MarkerSide(P.Side);
    P.Home = FName(*(TEXT("Home_") + Id.ToString()));
    const FString J = P.JobTitle.ToLower();
    const TCHAR* WorkKind = TEXT("Square");
    if (J.Contains(TEXT("guard")) || J.Contains(TEXT("watch")) || J.Contains(TEXT("constable"))) WorkKind = TEXT("Gate");
    else if (J.Contains(TEXT("inn")) || J.Contains(TEXT("tea"))) WorkKind = TEXT("Inn");
    else if (J.Contains(TEXT("laundry"))) WorkKind = TEXT("Laundry");
    else if (J.Contains(TEXT("nurse")) || J.Contains(TEXT("healer"))) WorkKind = TEXT("Infirmary");
    else if (J.Contains(TEXT("conductor")) || J.Contains(TEXT("cab"))) WorkKind = TEXT("Stop");
    else if (J.Contains(TEXT("maker")) || J.Contains(TEXT("blower")) || J.Contains(TEXT("tailor")) || J.Contains(TEXT("gilder")) || J.Contains(TEXT("binder")) || J.Contains(TEXT("seamstress")))
        WorkKind = TEXT("Workshop");
    else if (J.Contains(TEXT("sell")) || J.Contains(TEXT("trader")) || J.Contains(TEXT("vendor")) || J.Contains(TEXT("baker")) || J.Contains(TEXT("monger")) || J.Contains(TEXT("keeper")))
        WorkKind = TEXT("Market");
    P.Work = G.Sides.Num() ? FName(*FString::Printf(TEXT("Mk_%s_%s"), *S, WorkKind)) : FName(*(TEXT("Work_") + P.Job.ToString()));
    const TArray<FName>& Haunts = Pool(&FReflectionsPeopleGenerator::FPools::Haunts);
    if (Haunts.Num())
    {
        P.Haunts.Add(PickFrom(Haunts, Next()));
        const FName Second = PickFrom(Haunts, Next());
        if (Second != P.Haunts[0]) P.Haunts.Add(Second);
    }

    // Personality: one trait per column (story book) or two or three distinct ones, numbers leaning the same way.
    if (G.TraitColumns.Num())
        for (const TArray<FString>& Column : G.TraitColumns) P.Personality.Traits.Add(PickFrom(Column, Next()));
    else if (G.Traits.Num())
    {
        const int32 Count = 2 + static_cast<int32>(Next() % 2u);
        for (int32 Tries = 0; P.Personality.Traits.Num() < Count && Tries < 12; ++Tries)
            P.Personality.Traits.AddUnique(PickFrom(G.Traits, Next()));
    }
    auto Unit = [&Next]() { return static_cast<float>(Next() % 1000u) / 999.0f; };
    P.Personality.Warmth = Unit();
    P.Personality.Courage = Unit();
    P.Personality.Temper = Unit() * 0.8f;
    P.Personality.Chattiness = Unit();
    for (const FString& Trait : P.Personality.Traits)
    {
        const FString T = Trait.ToLower();
        if (T.Contains(TEXT("kind")) || T.Contains(TEXT("warm")) || T.Contains(TEXT("gentle")) || T.Contains(TEXT("generous"))) P.Personality.Warmth = FMath::Max(P.Personality.Warmth, 0.7f);
        if (T.Contains(TEXT("suspicious")) || T.Contains(TEXT("greedy"))) P.Personality.Warmth = FMath::Min(P.Personality.Warmth, 0.35f);
        if (T.Contains(TEXT("brave")) || T.Contains(TEXT("bold")) || T.Contains(TEXT("stubborn")) || T.Contains(TEXT("calm"))) P.Personality.Courage = FMath::Max(P.Personality.Courage, 0.65f);
        if (T.Contains(TEXT("timid")) || T.Contains(TEXT("nervous")) || T.Contains(TEXT("anxious"))) P.Personality.Courage = FMath::Min(P.Personality.Courage, 0.3f);
        if (T.Contains(TEXT("hot")) || T.Contains(TEXT("bitter")) || T.Contains(TEXT("prickly")) || T.Contains(TEXT("gloomy"))) P.Personality.Temper = FMath::Max(P.Personality.Temper, 0.65f);
        if (T.Contains(TEXT("gossip")) || T.Contains(TEXT("chatty")) || T.Contains(TEXT("nosy"))) P.Personality.Chattiness = FMath::Max(P.Personality.Chattiness, 0.75f);
        if (T.Contains(TEXT("quiet")) || T.Contains(TEXT("shy")) || T.Contains(TEXT("gruff"))) P.Personality.Chattiness = FMath::Min(P.Personality.Chattiness, 0.3f);
    }
    if (G.Quirks.Num()) P.Quirk = PickFrom(G.Quirks, Next());
    if (const TArray<FString>& Styles = Pool(&FReflectionsPeopleGenerator::FPools::SpeechStyles); Styles.Num()) P.SpeechStyle = PickFrom(Styles, Next());
    if (G.Likes.Num()) P.Likes.Add(PickFrom(G.Likes, Next()));
    if (const TArray<FString>& Fears = Pool(&FReflectionsPeopleGenerator::FPools::Fears); Fears.Num()) P.Fear = PickFrom(Fears, Next());
    if (const TArray<FString>& Wants = Pool(&FReflectionsPeopleGenerator::FPools::Wants); Wants.Num()) P.Want = PickFrom(Wants, Next());
    if (G.Secrets.Num()) P.Secret = PickFrom(G.Secrets, Next());
    P.Summary = FString::Printf(TEXT("A %s %s of %s."), *P.Age.ToString().ToLower(), *P.JobTitle.ToLower(), *P.Side.ToString());
    return P;
}

TArray<FReflectionsScheduleStep> FReflectionsPeopleBook::ResolveSchedule(const FReflectionsPerson& Person) const
{
    if (Person.Schedule.Num() > 0) return Person.Schedule;
    if (const TArray<FReflectionsScheduleStep>* Steps = Schedules.Find(Person.ScheduleKey)) return *Steps;
    for (const FReflectionsPeopleGenerator::FJob& Job : Generator.Flat.Jobs)
        if (Job.Job == Person.Job)
            if (const TArray<FReflectionsScheduleStep>* Steps = Schedules.Find(Job.Schedule)) return *Steps;
    // A soldier of the town (Captain Brask's men): barracks, patrol, the inn.
    if (Person.Archetype == TEXT("Soldier") || Person.Archetype == TEXT("SoldierCaster") || Person.LookRole == TEXT("Soldier"))
        if (const TArray<FReflectionsScheduleStep>* Steps = Schedules.Find(FName(TEXT("soldier_watch")))) return *Steps;
    if (const TArray<FReflectionsScheduleStep>* Steps = Schedules.Find(ScheduleForJob(Person.JobTitle))) return *Steps;
    return Schedules.FindChecked(FName(TEXT("day_worker")));
}

void FReflectionsPeopleBook::AddBuiltIns()
{
    // Built-in day templates, used whenever the book names none. Hours are in-game.
    Schedules.Add(FName(TEXT("day_worker")), TArray<FReflectionsScheduleStep>{
        MakeStep(6.5f, TEXT("wake"), TEXT("home")), MakeStep(8.0f, TEXT("work"), TEXT("work")),
        MakeStep(12.0f, TEXT("eat"), TEXT("haunt")), MakeStep(13.0f, TEXT("work"), TEXT("work")),
        MakeStep(17.5f, TEXT("social"), TEXT("social")), MakeStep(20.5f, TEXT("home"), TEXT("home")),
        MakeStep(22.0f, TEXT("sleep"), TEXT("home")) });
    Schedules.Add(FName(TEXT("early_riser")), TArray<FReflectionsScheduleStep>{
        MakeStep(5.0f, TEXT("work"), TEXT("work")), MakeStep(11.0f, TEXT("eat"), TEXT("haunt")),
        MakeStep(12.0f, TEXT("work"), TEXT("work")), MakeStep(15.0f, TEXT("errand"), TEXT("haunt")),
        MakeStep(17.0f, TEXT("social"), TEXT("social")), MakeStep(19.5f, TEXT("home"), TEXT("home")),
        MakeStep(21.0f, TEXT("sleep"), TEXT("home")) });
    Schedules.Add(FName(TEXT("night_owl")), TArray<FReflectionsScheduleStep>{
        MakeStep(2.0f, TEXT("sleep"), TEXT("home")), MakeStep(10.0f, TEXT("wake"), TEXT("home")),
        MakeStep(11.0f, TEXT("haunt"), TEXT("haunt")), MakeStep(14.0f, TEXT("work"), TEXT("work")),
        MakeStep(19.0f, TEXT("social"), TEXT("social")), MakeStep(23.0f, TEXT("haunt"), TEXT("haunt")) });
    Schedules.Add(FName(TEXT("idler")), TArray<FReflectionsScheduleStep>{
        MakeStep(8.0f, TEXT("wake"), TEXT("home")), MakeStep(9.0f, TEXT("haunt"), TEXT("haunt")),
        MakeStep(12.0f, TEXT("social"), TEXT("social")), MakeStep(15.0f, TEXT("errand"), TEXT("haunt")),
        MakeStep(18.0f, TEXT("social"), TEXT("social")), MakeStep(21.0f, TEXT("home"), TEXT("home")),
        MakeStep(22.5f, TEXT("sleep"), TEXT("home")) });
    Schedules.Add(FName(TEXT("guard_watch")), TArray<FReflectionsScheduleStep>{
        MakeStep(6.0f, TEXT("patrol"), TEXT("work")), MakeStep(10.0f, TEXT("patrol"), TEXT("haunt")),
        MakeStep(13.0f, TEXT("eat"), TEXT("haunt")), MakeStep(14.0f, TEXT("patrol"), TEXT("work")),
        MakeStep(18.0f, TEXT("social"), TEXT("social")), MakeStep(21.0f, TEXT("sleep"), TEXT("home")) });
    // Soldiers of a side: up in the barracks, patrol (between their post and a haunt), the inn at midday and evening.
    // A book template of the same name replaces it.
    if (!Schedules.Contains(FName(TEXT("soldier_watch"))))
        Schedules.Add(FName(TEXT("soldier_watch")), TArray<FReflectionsScheduleStep>{
            MakeStep(6.0f, TEXT("wake"), TEXT("barracks")), MakeStep(7.0f, TEXT("patrol"), TEXT("work")),
            MakeStep(12.0f, TEXT("eat"), TEXT("tavern")), MakeStep(13.0f, TEXT("patrol"), TEXT("work")),
            MakeStep(17.0f, TEXT("guard"), TEXT("work")), MakeStep(19.0f, TEXT("social"), TEXT("tavern")),
            MakeStep(22.0f, TEXT("home"), TEXT("barracks")), MakeStep(22.5f, TEXT("sleep"), TEXT("barracks")) });

    // Built-in generator (used only without a book): original, period-flavoured names.
    FReflectionsPeopleGenerator::FPools& F = Generator.Flat;
    F.FirstNamesF = { TEXT("Ada"), TEXT("Bess"), TEXT("Clemency"), TEXT("Dora"), TEXT("Edith"), TEXT("Florrie"),
        TEXT("Greta"), TEXT("Hester"), TEXT("Ivy"), TEXT("Jessamy"), TEXT("Kit"), TEXT("Lettice"), TEXT("Maud"), TEXT("Nell"),
        TEXT("Orla"), TEXT("Prue"), TEXT("Rosalind"), TEXT("Sybil"), TEXT("Tamsin"), TEXT("Una"), TEXT("Verity"), TEXT("Winifred") };
    F.FirstNamesM = { TEXT("Abel"), TEXT("Barnaby"), TEXT("Cuthbert"), TEXT("Dunstan"), TEXT("Elias"), TEXT("Fenwick"),
        TEXT("Gideon"), TEXT("Hal"), TEXT("Ivo"), TEXT("Jago"), TEXT("Kester"), TEXT("Lemuel"), TEXT("Moss"), TEXT("Ned"),
        TEXT("Osric"), TEXT("Piers"), TEXT("Quill"), TEXT("Rowan"), TEXT("Silas"), TEXT("Tobiah"), TEXT("Wat"), TEXT("Zeb") };
    F.Surnames = { TEXT("Ashdown"), TEXT("Blackwell"), TEXT("Cobb"), TEXT("Dimmock"), TEXT("Embry"), TEXT("Fairlie"),
        TEXT("Gristle"), TEXT("Harrowgate"), TEXT("Inchbald"), TEXT("Jessop"), TEXT("Kettering"), TEXT("Larkin"), TEXT("Mudge"),
        TEXT("Nettleford"), TEXT("Oakhurst"), TEXT("Pellow"), TEXT("Quarrie"), TEXT("Rook"), TEXT("Sallow"), TEXT("Thimble"),
        TEXT("Underwood"), TEXT("Vane"), TEXT("Wicklow"), TEXT("Yarrow") };
    F.Jobs = {
        { TEXT("porter"), TEXT("Porter"), 3, TEXT("early_riser"), NAME_None },
        { TEXT("baker"), TEXT("Baker"), 2, TEXT("early_riser"), NAME_None },
        { TEXT("clerk"), TEXT("Clerk"), 2, TEXT("day_worker"), NAME_None },
        { TEXT("seamstress"), TEXT("Seamstress"), 2, TEXT("day_worker"), NAME_None },
        { TEXT("lamplighter"), TEXT("Lamplighter"), 1, TEXT("night_owl"), NAME_None },
        { TEXT("street_vendor"), TEXT("Street vendor"), 3, TEXT("day_worker"), NAME_None },
        { TEXT("watchman"), TEXT("Watchman"), 1, TEXT("guard_watch"), NAME_None },
        { TEXT("idler"), TEXT("Idler"), 1, TEXT("idler"), NAME_None } };
    F.SpeechStyles = { TEXT("short, blunt sentences"), TEXT("rambling, with lots of 'and then'"), TEXT("formal and a bit stiff"),
        TEXT("teasing"), TEXT("whispers like everything is a secret"), TEXT("loud, cheerful, too familiar"), TEXT("slow and careful"),
        TEXT("answers questions with questions") };
    F.Fears = { TEXT("fire"), TEXT("the Tarnish"), TEXT("deep water"), TEXT("guards"), TEXT("spells"), TEXT("being forgotten") };
    F.Haunts = { TEXT("Haunt_Market"), TEXT("Haunt_Tavern"), TEXT("Haunt_Bridge"), TEXT("Haunt_Square") };
    Generator.Traits = { TEXT("warm"), TEXT("nosy"), TEXT("timid"), TEXT("stubborn"), TEXT("cheerful"), TEXT("gruff"),
        TEXT("superstitious"), TEXT("proud"), TEXT("gossipy"), TEXT("kind"), TEXT("suspicious"), TEXT("dreamy"), TEXT("brave"),
        TEXT("anxious"), TEXT("bitter"), TEXT("dry-witted"), TEXT("pious"), TEXT("greedy"), TEXT("quiet"), TEXT("hot-headed") };
    Generator.Quirks = { TEXT("hums when nervous"), TEXT("counts coins out loud"), TEXT("never finishes a sentence about the weather"),
        TEXT("names every pigeon"), TEXT("taps the nearest wall for luck"), TEXT("quotes their late mother"),
        TEXT("always smells of smoke"), TEXT("whistles one tune, badly"), TEXT("calls everyone by the wrong name"),
        TEXT("collects buttons"), TEXT("squints at spells like they owe them money"), TEXT("keeps a pebble from the river in one pocket") };
    Generator.Likes = { TEXT("hot bread"), TEXT("river fog"), TEXT("songs at the inn"), TEXT("a good argument"), TEXT("cats"),
        TEXT("quiet mornings"), TEXT("gossip"), TEXT("market days") };
    Generator.Schedules = { TEXT("day_worker"), TEXT("early_riser"), TEXT("idler") };
}
