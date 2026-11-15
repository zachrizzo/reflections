#include "Quests/ReflectionsQuestPack.h"

#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "Misc/Paths.h"
#include "Engine/StaticMesh.h"
#include "Quests/ReflectionsStoryMarker.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

const FReflectionsQuestStep* FReflectionsQuestDef::FindStep(FName StepId, int32* OutIndex) const
{
    for (int32 i = 0; i < Steps.Num(); ++i)
    {
        if (Steps[i].Id == StepId)
        {
            if (OutIndex) *OutIndex = i;
            return &Steps[i];
        }
    }
    if (OutIndex) *OutIndex = INDEX_NONE;
    return nullptr;
}

namespace ReflectionsQuestJson
{
    using FObj = TSharedPtr<FJsonObject>;

    /** Field by any of several names, case-insensitive (story files use camelCase, snake_case and plain words). */
    static TSharedPtr<FJsonValue> Field(const FObj& O, std::initializer_list<const TCHAR*> Names)
    {
        if (!O.IsValid()) return nullptr;
        for (const TCHAR* Name : Names)
        {
            if (const TSharedPtr<FJsonValue>* V = O->Values.Find(Name)) return *V;
        }
        for (const TCHAR* Name : Names)
        {
            for (const TPair<FString, TSharedPtr<FJsonValue>>& Pair : O->Values)
            {
                if (Pair.Key.Equals(Name, ESearchCase::IgnoreCase) ||
                    Pair.Key.Replace(TEXT("_"), TEXT("")).Equals(FString(Name).Replace(TEXT("_"), TEXT("")), ESearchCase::IgnoreCase))
                {
                    return Pair.Value;
                }
            }
        }
        return nullptr;
    }

    static FString Str(const FObj& O, std::initializer_list<const TCHAR*> Names, const FString& Default = FString())
    {
        const TSharedPtr<FJsonValue> V = Field(O, Names);
        if (!V.IsValid() || V->IsNull()) return Default;
        if (V->Type == EJson::String) return V->AsString();
        if (V->Type == EJson::Number) return FString::SanitizeFloat(V->AsNumber());
        if (V->Type == EJson::Boolean) return V->AsBool() ? TEXT("true") : TEXT("false");
        return Default;
    }

    static FName Name(const FObj& O, std::initializer_list<const TCHAR*> Names)
    {
        const FString S = Str(O, Names).TrimStartAndEnd();
        return S.IsEmpty() ? NAME_None : FName(*S);
    }

    static FText Text(const FObj& O, std::initializer_list<const TCHAR*> Names)
    {
        return FText::FromString(Str(O, Names));
    }

    static double Num(const FObj& O, std::initializer_list<const TCHAR*> Names, double Default)
    {
        const TSharedPtr<FJsonValue> V = Field(O, Names);
        if (!V.IsValid() || V->IsNull()) return Default;
        if (V->Type == EJson::Number) return V->AsNumber();
        if (V->Type == EJson::String) { double D = Default; LexFromString(D, *V->AsString()); return D; }
        return Default;
    }

    static bool Bool(const FObj& O, std::initializer_list<const TCHAR*> Names, bool Default)
    {
        const TSharedPtr<FJsonValue> V = Field(O, Names);
        if (!V.IsValid() || V->IsNull()) return Default;
        if (V->Type == EJson::Boolean) return V->AsBool();
        if (V->Type == EJson::String) return V->AsString().ToBool();
        if (V->Type == EJson::Number) return V->AsNumber() != 0.0;
        return Default;
    }

    static TArray<TSharedPtr<FJsonValue>> Arr(const FObj& O, std::initializer_list<const TCHAR*> Names)
    {
        const TSharedPtr<FJsonValue> V = Field(O, Names);
        if (V.IsValid() && V->Type == EJson::Array) return V->AsArray();
        if (V.IsValid() && (V->Type == EJson::String || V->Type == EJson::Object)) return {V};
        return {};
    }

    /** Plain texts: an array of strings (or objects with "text"), or one string. */
    static TArray<FText> Texts(const FObj& O, std::initializer_list<const TCHAR*> Names)
    {
        TArray<FText> Out;
        for (const TSharedPtr<FJsonValue>& V : Arr(O, Names))
        {
            if (V->Type == EJson::String) Out.Add(FText::FromString(V->AsString()));
            else if (V->Type == EJson::Object) Out.Add(Text(V->AsObject(), {TEXT("text"), TEXT("line")}));
        }
        return Out;
    }

    /** Lines: strings, or {"id", "speaker", "text"/"line", "delay"} objects, or one of either. */
    static TArray<FReflectionsQuestLineDef> Lines(const FObj& O, std::initializer_list<const TCHAR*> Names)
    {
        TArray<FReflectionsQuestLineDef> Out;
        for (const TSharedPtr<FJsonValue>& V : Arr(O, Names))
        {
            FReflectionsQuestLineDef L;
            if (V->Type == EJson::String)
            {
                L.Text = FText::FromString(V->AsString());
            }
            else if (V->Type == EJson::Object)
            {
                const FObj LO = V->AsObject();
                L.Id = Name(LO, {TEXT("id")});
                L.Speaker = Name(LO, {TEXT("speaker"), TEXT("who"), TEXT("by")});
                L.Text = Text(LO, {TEXT("text"), TEXT("line")});
                L.Delay = static_cast<float>(Num(LO, {TEXT("delay")}, 0.0));
            }
            if (!L.Text.IsEmpty()) Out.Add(MoveTemp(L));
        }
        return Out;
    }

    static TArray<FName> Names(const FObj& O, std::initializer_list<const TCHAR*> Keys)
    {
        TArray<FName> Out;
        for (const TSharedPtr<FJsonValue>& V : Arr(O, Keys))
        {
            if (V->Type == EJson::String && !V->AsString().IsEmpty()) Out.Add(FName(*V->AsString()));
        }
        return Out;
    }

    static EReflectionsQuestSide Side(const FString& In, EReflectionsQuestSide Default = EReflectionsQuestSide::Any)
    {
        const FString S = In.ToLower();
        if (S.IsEmpty()) return Default;
        if (S.Contains(TEXT("pewter")) || S == TEXT("gray") || S == TEXT("grey")) return EReflectionsQuestSide::Pewterside;
        if (S.Contains(TEXT("gilt")) || S == TEXT("red")) return EReflectionsQuestSide::Giltside;
        if (S.Contains(TEXT("frost")) || S == TEXT("white")) return EReflectionsQuestSide::Frostside;
        if (S == TEXT("current") || S == TEXT("here")) return EReflectionsQuestSide::Current;
        return EReflectionsQuestSide::Any;
    }

    static bool ObjectiveType(const FString& In, EReflectionsObjectiveType& Out)
    {
        FString S = In.ToLower().Replace(TEXT("_"), TEXT("")).Replace(TEXT(" "), TEXT("")).Replace(TEXT("-"), TEXT(""));
        struct FMap { const TCHAR* Key; EReflectionsObjectiveType Type; };
        static const FMap Map[] = {
            {TEXT("talkto"), EReflectionsObjectiveType::TalkTo}, {TEXT("talk"), EReflectionsObjectiveType::TalkTo}, {TEXT("speak"), EReflectionsObjectiveType::TalkTo},
            {TEXT("goto"), EReflectionsObjectiveType::GoTo}, {TEXT("go"), EReflectionsObjectiveType::GoTo}, {TEXT("reach"), EReflectionsObjectiveType::GoTo}, {TEXT("marker"), EReflectionsObjectiveType::GoTo},
            {TEXT("collect"), EReflectionsObjectiveType::Collect}, {TEXT("pickup"), EReflectionsObjectiveType::Collect}, {TEXT("find"), EReflectionsObjectiveType::Collect},
            {TEXT("deliver"), EReflectionsObjectiveType::Deliver}, {TEXT("give"), EReflectionsObjectiveType::Deliver}, {TEXT("bring"), EReflectionsObjectiveType::Deliver},
            {TEXT("defeat"), EReflectionsObjectiveType::Defeat}, {TEXT("kill"), EReflectionsObjectiveType::Defeat}, {TEXT("beat"), EReflectionsObjectiveType::Defeat},
            {TEXT("spellhit"), EReflectionsObjectiveType::SpellHit}, {TEXT("hit"), EReflectionsObjectiveType::SpellHit}, {TEXT("cast"), EReflectionsObjectiveType::SpellHit}, {TEXT("spell"), EReflectionsObjectiveType::SpellHit},
            {TEXT("worldjump"), EReflectionsObjectiveType::WorldJump}, {TEXT("jump"), EReflectionsObjectiveType::WorldJump}, {TEXT("stepthrough"), EReflectionsObjectiveType::WorldJump},
            {TEXT("protect"), EReflectionsObjectiveType::Protect}, {TEXT("defend"), EReflectionsObjectiveType::Protect}, {TEXT("hold"), EReflectionsObjectiveType::Protect},
            {TEXT("event"), EReflectionsObjectiveType::Event},
        };
        for (const FMap& M : Map)
        {
            if (S == M.Key) { Out = M.Type; return true; }
        }
        return false;
    }

    static FReflectionsQuestReward Reward(const FObj& O)
    {
        FReflectionsQuestReward R;
        if (!O.IsValid()) return R;
        R.Coins = static_cast<int32>(Num(O, {TEXT("coins"), TEXT("shards")}, 0));
        R.CoinSide = Side(Str(O, {TEXT("coinSide"), TEXT("shardSide")}), EReflectionsQuestSide::Current);
        R.Mana = static_cast<float>(Num(O, {TEXT("mana")}, 0));
        R.Unlocks = Names(O, {TEXT("unlocks"), TEXT("unlock")});
        R.Items = Names(O, {TEXT("items"), TEXT("item")});
        const TSharedPtr<FJsonValue> Rep = Field(O, {TEXT("reputation"), TEXT("rep"), TEXT("standing")});
        if (Rep.IsValid() && Rep->Type == EJson::Object)
        {
            for (const TPair<FString, TSharedPtr<FJsonValue>>& Pair : Rep->AsObject()->Values)
            {
                FReflectionsReputationGrant G;
                G.Person = FName(*Pair.Key);
                G.Amount = static_cast<float>(Pair.Value->Type == EJson::Number ? Pair.Value->AsNumber() : 10.0);
                R.Reputation.Add(G);
            }
        }
        else if (Rep.IsValid() && Rep->Type == EJson::Array)
        {
            for (const TSharedPtr<FJsonValue>& V : Rep->AsArray())
            {
                if (V->Type != EJson::Object) continue;
                FReflectionsReputationGrant G;
                G.Person = Name(V->AsObject(), {TEXT("person"), TEXT("id")});
                G.Amount = static_cast<float>(Num(V->AsObject(), {TEXT("amount"), TEXT("value")}, 10.0));
                if (!G.Person.IsNone()) R.Reputation.Add(G);
            }
        }
        return R;
    }

    static bool Objective(const FObj& O, int32 Index, FReflectionsQuestObjective& Out, FString& Report, const FString& Where)
    {
        const FString TypeName = Str(O, {TEXT("type"), TEXT("kind")});
        if (!ObjectiveType(TypeName, Out.Type))
        {
            Report += FString::Printf(TEXT("%s: unknown objective type \"%s\"\n"), *Where, *TypeName);
            return false;
        }
        Out.Id = Name(O, {TEXT("id")});
        if (Out.Id.IsNone()) Out.Id = FName(*FString::Printf(TEXT("o%d"), Index + 1));
        Out.Text = Text(O, {TEXT("text"), TEXT("label"), TEXT("tracker")});
        Out.Target = Name(O, {TEXT("target"), TEXT("person"), TEXT("marker_target"), TEXT("event"), TEXT("kind_of")});
        if (Out.Target.IsNone())
        {
            // Type-specific aliases.
            Out.Target = Name(O, {TEXT("to"), TEXT("who"), TEXT("where"), TEXT("what"), TEXT("archetype"), TEXT("enemy")});
        }
        // "person:ada_pollard" / "marker:Spot_X" prefixes from the story generator name the same ids.
        {
            FString T = Out.Target.ToString();
            if (T.StartsWith(TEXT("person:")) || T.StartsWith(TEXT("marker:"))) Out.Target = FName(*T.Mid(T.Find(TEXT(":")) + 1));
        }
        Out.Item = Name(O, {TEXT("item")});
        if (Out.Type == EReflectionsObjectiveType::Collect && Out.Target.IsNone()) Out.Target = Out.Item;
        Out.Spell = Name(O, {TEXT("spell"), TEXT("element"), TEXT("arg"), TEXT("filter")});
        Out.Count = FMath::Max(1, static_cast<int32>(Num(O, {TEXT("count"), TEXT("amount"), TEXT("times")}, 1)));
        Out.Radius = static_cast<float>(Num(O, {TEXT("radius")}, 0));
        Out.Seconds = static_cast<float>(Num(O, {TEXT("seconds"), TEXT("duration")}, 0));
        Out.Side = Side(Str(O, {TEXT("side")}));
        Out.SpawnArchetype = Name(O, {TEXT("spawn"), TEXT("spawnArchetype")});
        Out.SpawnCount = static_cast<int32>(Num(O, {TEXT("spawnCount")}, Out.SpawnArchetype.IsNone() ? 0 : Out.Count));
        Out.Marker = Name(O, {TEXT("marker"), TEXT("at")});
        Out.bOptional = Bool(O, {TEXT("optional")}, false);
        Out.bHidden = Bool(O, {TEXT("hidden")}, false);
        Out.Hints = Texts(O, {TEXT("hints"), TEXT("hint")});
        Out.CompleteLines = Lines(O, {TEXT("completeLines"), TEXT("onComplete"), TEXT("lines")});
        Out.ProgressLines = Lines(O, {TEXT("progressLines"), TEXT("onProgress")});
        Out.GiveItems = Names(O, {TEXT("giveItems"), TEXT("items")});
        Out.SpawnMarker = Name(O, {TEXT("spawnMarker"), TEXT("spawnAt")});
        if (Out.Type == EReflectionsObjectiveType::Protect && Out.Seconds <= 0.0f) Out.Seconds = 30.0f;
        // A spell hit that only counts when it cures (the story's "burn the Tarnish out of X"): the cure event itself.
        if (Out.Type == EReflectionsObjectiveType::SpellHit && (Bool(O, {TEXT("cure")}, false) || Bool(O, {TEXT("requireInfected")}, false)))
        {
            const FName Who = Out.Target;
            const bool bAnyone = Who.IsNone() || Who == TEXT("Infected") || Who == TEXT("Tarnished") || Who == TEXT("Any") ||
                Field(O, {TEXT("fallbackTarget")}).IsValid() || AReflectionsStoryMarker::IsStoryName(Who);
            if (AReflectionsStoryMarker::IsStoryName(Who) && Out.Marker.IsNone()) Out.Marker = Who;
            Out.Type = EReflectionsObjectiveType::Event;
            Out.Target = TEXT("NpcCured");
            Out.Spell = bAnyone ? NAME_None : Who;
            if (!bAnyone && Out.Marker.IsNone()) Out.Marker = NAME_None;
        }
        if (Out.Type == EReflectionsObjectiveType::Deliver && Out.Item.IsNone())
        {
            Report += FString::Printf(TEXT("%s: deliver objective without an item\n"), *Where);
        }
        return true;
    }

    static FReflectionsQuestChoice Choice(const FObj& O, int32 Index)
    {
        FReflectionsQuestChoice C;
        C.Id = Name(O, {TEXT("id")});
        if (C.Id.IsNone()) C.Id = FName(*FString::Printf(TEXT("c%d"), Index + 1));
        C.Text = Text(O, {TEXT("text"), TEXT("label"), TEXT("option")});
        const TSharedPtr<FJsonValue> Resp = Field(O, {TEXT("response"), TEXT("reply"), TEXT("answer")});
        if (Resp.IsValid() && Resp->Type == EJson::Object)
        {
            C.Response = Text(Resp->AsObject(), {TEXT("text"), TEXT("line")});
            C.ResponseId = Name(Resp->AsObject(), {TEXT("id")});
        }
        else
        {
            C.Response = Text(O, {TEXT("response"), TEXT("reply"), TEXT("answer")});
            C.ResponseId = Name(O, {TEXT("responseId")});
        }
        C.NextStep = Name(O, {TEXT("next"), TEXT("nextStep"), TEXT("goto")});
        const TSharedPtr<FJsonValue> R = Field(O, {TEXT("reward"), TEXT("rewards")});
        if (R.IsValid() && R->Type == EJson::Object) C.Reward = Reward(R->AsObject());
        C.Journal = Text(O, {TEXT("journal"), TEXT("log")});
        return C;
    }

    static bool Quest(const FObj& O, FReflectionsQuestDef& Q, FString& Report)
    {
        Q.Id = Name(O, {TEXT("id"), TEXT("quest_id")});
        if (Q.Id.IsNone())
        {
            Report += TEXT("quest without an id skipped\n");
            return false;
        }
        Q.Title = Text(O, {TEXT("title"), TEXT("name")});
        Q.Summary = Text(O, {TEXT("summary"), TEXT("description"), TEXT("blurb")});
        Q.bMain = Bool(O, {TEXT("main"), TEXT("isMain")}, false);
        Q.Giver = Name(O, {TEXT("giver"), TEXT("questGiver"), TEXT("from")});
        Q.Side = Side(Str(O, {TEXT("side")}));
        Q.bAutoStart = Bool(O, {TEXT("autoStart"), TEXT("auto")}, Q.bMain || Q.Giver.IsNone());
        Q.RequiresQuests = Names(O, {TEXT("requires"), TEXT("requiresQuests"), TEXT("after")});
        Q.RequiresUnlocks = Names(O, {TEXT("requiresUnlocks"), TEXT("requiresFlags")});
        Q.bTurnIn = Bool(O, {TEXT("turnIn"), TEXT("returnToGiver")}, !Q.Giver.IsNone());
        Q.OfferLines = Lines(O, {TEXT("offer"), TEXT("offerLines")});
        Q.AcceptLines = Lines(O, {TEXT("accept"), TEXT("acceptLines")});
        Q.WantedLines = Lines(O, {TEXT("offerIfWanted"), TEXT("wantedLines")});
        Q.DeclineLines = Lines(O, {TEXT("decline"), TEXT("declineLines")});
        Q.ReminderLines = Lines(O, {TEXT("reminder"), TEXT("reminderLines"), TEXT("progress")});
        Q.TurnInLines = Lines(O, {TEXT("turnInLines"), TEXT("complete"), TEXT("completeLines"), TEXT("thanks")});
        Q.AfterLines = Lines(O, {TEXT("afterLines"), TEXT("after"), TEXT("afterLine")});
        Q.StartsTarnished = Names(O, {TEXT("startsTarnished")});
        Q.FailLines = Lines(O, {TEXT("failLines"), TEXT("fail")});
        Q.FailIfDies = Name(O, {TEXT("failIfDies")});
        const TSharedPtr<FJsonValue> R = Field(O, {TEXT("reward"), TEXT("rewards")});
        if (R.IsValid() && R->Type == EJson::Object) Q.Reward = Reward(R->AsObject());
        Q.SortOrder = static_cast<int32>(Num(O, {TEXT("sort"), TEXT("order"), TEXT("sortOrder")}, Q.bMain ? 0 : 100));
        Q.bTest = Bool(O, {TEXT("test")}, false);

        const TArray<TSharedPtr<FJsonValue>> Steps = Arr(O, {TEXT("steps"), TEXT("stages")});
        for (int32 s = 0; s < Steps.Num(); ++s)
        {
            if (Steps[s]->Type != EJson::Object) continue;
            const FObj S = Steps[s]->AsObject();
            FReflectionsQuestStep Step;
            Step.Id = Name(S, {TEXT("id")});
            if (Step.Id.IsNone()) Step.Id = FName(*FString::Printf(TEXT("s%d"), s + 1));
            Step.Title = Text(S, {TEXT("title"), TEXT("name")});
            Step.Description = Text(S, {TEXT("description"), TEXT("journal"), TEXT("text")});
            Step.bAnyObjective = Bool(S, {TEXT("anyObjective"), TEXT("any")}, false);
            Step.ChoicePerson = Name(S, {TEXT("choicePerson"), TEXT("askedBy")});
            Step.Lines = Lines(S, {TEXT("lines"), TEXT("dialogue"), TEXT("say")});
            Step.Speaker = Name(S, {TEXT("speaker"), TEXT("by")});
            Step.CompleteLines = Lines(S, {TEXT("completeLines"), TEXT("onComplete")});
            Step.Cutscene = Name(S, {TEXT("cutscene")});
            Step.TimeoutSeconds = static_cast<float>(Num(S, {TEXT("timeout"), TEXT("timeoutSeconds")}, 0.0));
            for (const TSharedPtr<FJsonValue>& TV : Arr(S, {TEXT("talk")}))
            {
                if (TV->Type != EJson::Object) continue;
                FReflectionsQuestTalk T;
                T.Person = Name(TV->AsObject(), {TEXT("person"), TEXT("id")});
                T.Lines = Lines(TV->AsObject(), {TEXT("lines")});
                if (!T.Person.IsNone()) Step.Talk.Add(MoveTemp(T));
            }
            Step.NextStep = Name(S, {TEXT("next"), TEXT("nextStep")});
            Step.IfKilledNext = Name(S, {TEXT("ifKilledNext"), TEXT("ifKilled")});
            Step.bPlayVoiceCue = Bool(S, {TEXT("voiceCue")}, true);
            const TSharedPtr<FJsonValue> SR = Field(S, {TEXT("reward"), TEXT("rewards")});
            if (SR.IsValid() && SR->Type == EJson::Object) Step.Reward = Reward(SR->AsObject());
            Step.CutsceneOnComplete = Name(S, {TEXT("cutsceneOnComplete")});
            Step.bOrdered = Bool(S, {TEXT("ordered")}, false);
            Step.GiveItems = Names(S, {TEXT("giveItems")});
            const TSharedPtr<FJsonValue> StepRewardDone = Field(S, {TEXT("rewardOnComplete")});
            if (StepRewardDone.IsValid() && StepRewardDone->Type == EJson::Object) Step.Reward = Reward(StepRewardDone->AsObject());
            Step.CompleteLines.Append(Lines(S, {TEXT("linesOnComplete")}));
            const FName StepFailIfDies = Name(S, {TEXT("failIfDies")});
            if (!StepFailIfDies.IsNone() && Q.FailIfDies.IsNone()) Q.FailIfDies = StepFailIfDies;
            const TSharedPtr<FJsonValue> OptionalTalk = Field(S, {TEXT("optionalTalk")});
            if (OptionalTalk.IsValid() && OptionalTalk->Type == EJson::Object)
            {
                for (const TPair<FString, TSharedPtr<FJsonValue>>& Pair : OptionalTalk->AsObject()->Values)
                {
                    FReflectionsQuestTalk T;
                    T.Person = FName(*Pair.Key);
                    TSharedRef<FJsonObject> Wrap = MakeShared<FJsonObject>();
                    Wrap->SetField(TEXT("lines"), Pair.Value);
                    T.Lines = Lines(Wrap, {TEXT("lines")});
                    Step.Talk.Add(MoveTemp(T));
                }
            }
            const FString Where = FString::Printf(TEXT("%s/%s"), *Q.Id.ToString(), *Step.Id.ToString());
            const TArray<TSharedPtr<FJsonValue>> Objectives = Arr(S, {TEXT("objectives"), TEXT("goals"), TEXT("tasks")});
            for (int32 o = 0; o < Objectives.Num(); ++o)
            {
                if (Objectives[o]->Type != EJson::Object) continue;
                FReflectionsQuestObjective Objective;
                if (ReflectionsQuestJson::Objective(Objectives[o]->AsObject(), o, Objective, Report, Where))
                {
                    Step.Objectives.Add(MoveTemp(Objective));
                }
            }
            // Story layouts: lines said "on complete" / "on arrive", lines per objective, progress lines per count.
            const FString LinesOn = Str(S, {TEXT("linesOn"), TEXT("linesAt")}).ToLower();
            const int32 TalkIndex = Step.Objectives.IndexOfByPredicate([&Step](const FReflectionsQuestObjective& O)
            {
                return O.Type == EReflectionsObjectiveType::TalkTo && (Step.Speaker.IsNone() || O.Target == Step.Speaker);
            });
            if (LinesOn == TEXT("complete") || LinesOn == TEXT("arrive") || LinesOn == TEXT("end"))
            {
                Step.CompleteLines.Insert(Step.Lines, 0);
                Step.Lines.Reset();
            }
            else if (LinesOn.IsEmpty() && TalkIndex != INDEX_NONE && !Step.Lines.IsEmpty())
            {
                // Lines at a "talk to X" step are what X says when spoken to.
                Step.Objectives[TalkIndex].CompleteLines.Insert(Step.Lines, 0);
                Step.Lines.Reset();
            }
            const TSharedPtr<FJsonValue> PerObjective = Field(S, {TEXT("linesOnObjective")});
            if (PerObjective.IsValid() && PerObjective->Type == EJson::Object)
            {
                for (const TPair<FString, TSharedPtr<FJsonValue>>& Pair : PerObjective->AsObject()->Values)
                {
                    const int32 Index = FCString::Atoi(*Pair.Key);
                    if (!Step.Objectives.IsValidIndex(Index)) continue;
                    TSharedRef<FJsonObject> Wrap = MakeShared<FJsonObject>();
                    Wrap->SetField(TEXT("lines"), Pair.Value);
                    Step.Objectives[Index].CompleteLines.Append(Lines(Wrap, {TEXT("lines")}));
                }
            }
            const TSharedPtr<FJsonValue> ItemsPerObjective = Field(S, {TEXT("giveItemsOnObjective")});
            if (ItemsPerObjective.IsValid() && ItemsPerObjective->Type == EJson::Object)
            {
                for (const TPair<FString, TSharedPtr<FJsonValue>>& Pair : ItemsPerObjective->AsObject()->Values)
                {
                    const int32 Index = FCString::Atoi(*Pair.Key);
                    if (!Step.Objectives.IsValidIndex(Index)) continue;
                    TSharedRef<FJsonObject> Wrap = MakeShared<FJsonObject>();
                    Wrap->SetField(TEXT("items"), Pair.Value);
                    Step.Objectives[Index].GiveItems.Append(Names(Wrap, {TEXT("items")}));
                }
            }
            const TSharedPtr<FJsonValue> StepProgress = Field(S, {TEXT("progressLines")});
            if (StepProgress.IsValid() && StepProgress->Type == EJson::Object && !Step.Objectives.IsEmpty())
            {
                int32 Counter = Step.Objectives.IndexOfByPredicate([](const FReflectionsQuestObjective& O) { return O.Count > 1; });
                if (Counter == INDEX_NONE) Counter = 0;
                for (const TPair<FString, TSharedPtr<FJsonValue>>& Pair : StepProgress->AsObject()->Values)
                {
                    const int32 At = FCString::Atoi(*Pair.Key);
                    if (At < 1) continue;
                    TSharedRef<FJsonObject> Wrap = MakeShared<FJsonObject>();
                    Wrap->SetField(TEXT("lines"), Pair.Value);
                    TArray<FReflectionsQuestLineDef> L = Lines(Wrap, {TEXT("lines")});
                    TArray<FReflectionsQuestLineDef>& Target = Step.Objectives[Counter].ProgressLines;
                    if (Target.Num() < At) Target.SetNum(At);
                    if (!L.IsEmpty()) Target[At - 1] = L[0];
                }
            }
            const TArray<TSharedPtr<FJsonValue>> Choices = Arr(S, {TEXT("choices"), TEXT("options")});
            for (int32 c = 0; c < Choices.Num(); ++c)
            {
                if (Choices[c]->Type == EJson::Object) Step.Choices.Add(Choice(Choices[c]->AsObject(), c));
            }
            if (Step.Objectives.IsEmpty() && Step.Choices.IsEmpty() && Step.Cutscene.IsNone() && Step.TimeoutSeconds <= 0.0f && Step.GiveItems.IsEmpty() && Step.Reward.IsEmpty())
            {
                Report += FString::Printf(TEXT("%s: step has no objectives or choices (it completes at once)\n"), *Where);
            }
            Q.Steps.Add(MoveTemp(Step));
        }
        if (Q.Steps.IsEmpty())
        {
            Report += FString::Printf(TEXT("%s: quest has no steps\n"), *Q.Id.ToString());
        }
        return true;
    }

    static bool ReadRoot(const FString& Json, TSharedPtr<FJsonValue>& Out, FString& Report)
    {
        const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Json);
        if (!FJsonSerializer::Deserialize(Reader, Out) || !Out.IsValid())
        {
            Report += FString::Printf(TEXT("JSON error: %s\n"), *Reader->GetErrorMessage());
            return false;
        }
        return true;
    }
}

bool UReflectionsQuestPack::ParseQuests(const FString& Json, TArray<FReflectionsQuestDef>& OutQuests, FString& OutReport)
{
    using namespace ReflectionsQuestJson;
    TSharedPtr<FJsonValue> Root;
    if (!ReadRoot(Json, Root, OutReport)) return false;
    TArray<TSharedPtr<FJsonValue>> List;
    if (Root->Type == EJson::Array) List = Root->AsArray();
    else if (Root->Type == EJson::Object)
    {
        List = Arr(Root->AsObject(), {TEXT("quests")});
        if (List.IsEmpty() && Field(Root->AsObject(), {TEXT("steps")}).IsValid()) List.Add(Root);
        // {"main": {...}, "side": [...]} layouts.
        if (List.IsEmpty())
        {
            for (const TPair<FString, TSharedPtr<FJsonValue>>& Pair : Root->AsObject()->Values)
            {
                if (Pair.Value->Type == EJson::Array) List.Append(Pair.Value->AsArray());
                else if (Pair.Value->Type == EJson::Object && Field(Pair.Value->AsObject(), {TEXT("steps")}).IsValid()) List.Add(Pair.Value);
            }
        }
    }
    int32 Added = 0;
    for (const TSharedPtr<FJsonValue>& V : List)
    {
        if (!V.IsValid() || V->Type != EJson::Object) continue;
        FReflectionsQuestDef Q;
        if (Quest(V->AsObject(), Q, OutReport))
        {
            OutQuests.RemoveAll([&Q](const FReflectionsQuestDef& E) { return E.Id == Q.Id; });
            OutQuests.Add(MoveTemp(Q));
            ++Added;
        }
    }
    OutReport += FString::Printf(TEXT("%d quests parsed\n"), Added);
    return Added > 0;
}

bool UReflectionsQuestPack::ParsePeople(const FString& Json, TArray<FReflectionsQuestPerson>& OutPeople, FString& OutReport)
{
    using namespace ReflectionsQuestJson;
    TSharedPtr<FJsonValue> Root;
    if (!ReadRoot(Json, Root, OutReport)) return false;
    TArray<TPair<FString, FObj>> Entries;
    if (Root->Type == EJson::Array)
    {
        for (const TSharedPtr<FJsonValue>& V : Root->AsArray()) if (V->Type == EJson::Object) Entries.Add({FString(), V->AsObject()});
    }
    else if (Root->Type == EJson::Object)
    {
        const TArray<TSharedPtr<FJsonValue>> List = Arr(Root->AsObject(), {TEXT("people"), TEXT("cast"), TEXT("characters")});
        if (!List.IsEmpty())
        {
            for (const TSharedPtr<FJsonValue>& V : List) if (V->Type == EJson::Object) Entries.Add({FString(), V->AsObject()});
        }
        else
        {
            for (const TPair<FString, TSharedPtr<FJsonValue>>& Pair : Root->AsObject()->Values)
            {
                if (Pair.Value->Type == EJson::Object) Entries.Add({Pair.Key, Pair.Value->AsObject()});
            }
        }
    }
    int32 Added = 0;
    for (const TPair<FString, FObj>& Entry : Entries)
    {
        const FObj& O = Entry.Value;
        FReflectionsQuestPerson P;
        P.Id = Name(O, {TEXT("id"), TEXT("personId")});
        if (P.Id.IsNone() && !Entry.Key.IsEmpty()) P.Id = FName(*Entry.Key);
        if (P.Id.IsNone()) continue;
        P.DisplayName = Text(O, {TEXT("name"), TEXT("displayName"), TEXT("fullName")});
        if (P.DisplayName.IsEmpty()) P.DisplayName = FText::FromName(P.Id);
        P.Title = Text(O, {TEXT("job"), TEXT("title"), TEXT("occupation")});
        if (!P.Title.IsEmpty())
        {
            // "retired Silverer; sells candles" -> "Retired Silverer"
            FString T = P.Title.ToString();
            int32 Cut = INDEX_NONE;
            if (T.FindChar(TEXT(';'), Cut)) T = T.Left(Cut);
            if (T.Len() > 0) T[0] = FChar::ToUpper(T[0]);
            P.Title = FText::FromString(T.TrimStartAndEnd());
        }
        P.Side = Side(Str(O, {TEXT("side"), TEXT("home_side")}), EReflectionsQuestSide::Giltside);
        FString Role = Str(O, {TEXT("archetype"), TEXT("role")});
        if (Role.IsEmpty()) Role = TEXT("Civilian");
        P.Archetype = FName(*Role);
        P.Sex = Name(O, {TEXT("sex"), TEXT("gender")});
        const FString Look = Str(O, {TEXT("look"), TEXT("lookClass"), TEXT("blueprint")});
        if (Look.StartsWith(TEXT("/"))) P.Look = FSoftClassPath(Look.EndsWith(TEXT("_C")) ? Look : Look + TEXT(".") + FPaths::GetBaseFilename(Look) + TEXT("_C"));
        P.IdleLines = Texts(O, {TEXT("idleLines"), TEXT("greetings")});
        const TSharedPtr<FJsonValue> Barks = Field(O, {TEXT("barks")});
        if (Barks.IsValid() && Barks->Type == EJson::Object)
        {
            for (const TCHAR* Key : {TEXT("greet"), TEXT("idle"), TEXT("farewell")})
            {
                const FString B = Str(Barks->AsObject(), {Key});
                if (!B.IsEmpty()) P.IdleLines.Add(FText::FromString(B));
            }
        }
        const TSharedPtr<FJsonValue> Markers = Field(O, {TEXT("markers")});
        if (Markers.IsValid() && Markers->Type == EJson::Object)
        {
            P.SpawnMarker = Name(Markers->AsObject(), {TEXT("work"), TEXT("haunt"), TEXT("home")});
        }
        OutPeople.RemoveAll([&P](const FReflectionsQuestPerson& E) { return E.Id == P.Id; });
        OutPeople.Add(MoveTemp(P));
        ++Added;
    }
    OutReport += FString::Printf(TEXT("%d people parsed\n"), Added);
    return Added > 0;
}

void UReflectionsQuestPack::ParseItems(const FString& Json, TArray<FReflectionsQuestItemDef>& OutItems)
{
    using namespace ReflectionsQuestJson;
    TSharedPtr<FJsonValue> Root;
    FString Ignore;
    if (!ReadRoot(Json, Root, Ignore) || Root->Type != EJson::Object) return;
    for (const TSharedPtr<FJsonValue>& V : Arr(Root->AsObject(), {TEXT("items")}))
    {
        if (V->Type != EJson::Object) continue;
        FReflectionsQuestItemDef Item;
        Item.Id = Name(V->AsObject(), {TEXT("id")});
        Item.Name = Text(V->AsObject(), {TEXT("name"), TEXT("title")});
        const FString MeshPath = Str(V->AsObject(), {TEXT("mesh")});
        if (MeshPath.StartsWith(TEXT("/")))
        {
            Item.Mesh = TSoftObjectPtr<UStaticMesh>(FSoftObjectPath(MeshPath.Contains(TEXT(".")) ? MeshPath : MeshPath + TEXT(".") + FPaths::GetBaseFilename(MeshPath)));
        }
        Item.MeshScale = static_cast<float>(Num(V->AsObject(), {TEXT("meshScale"), TEXT("scale")}, 1.0));
        if (Item.Id.IsNone()) continue;
        OutItems.RemoveAll([&Item](const FReflectionsQuestItemDef& E) { return E.Id == Item.Id; });
        OutItems.Add(Item);
    }
}

void UReflectionsQuestPack::ParseMarkerAliases(const FString& Json, TMap<FName, FName>& OutAliases)
{
    using namespace ReflectionsQuestJson;
    TSharedPtr<FJsonValue> Root;
    FString Ignore;
    if (!ReadRoot(Json, Root, Ignore) || Root->Type != EJson::Object) return;
    const TSharedPtr<FJsonValue> Markers = Field(Root->AsObject(), {TEXT("markers")});
    const TSharedPtr<FJsonValue> Names = Markers.IsValid() && Markers->Type == EJson::Object ? Field(Markers->AsObject(), {TEXT("story_names")}) : nullptr;
    if (!Names.IsValid() || Names->Type != EJson::Object) return;
    for (const TPair<FString, TSharedPtr<FJsonValue>>& Pair : Names->AsObject()->Values)
    {
        if (Pair.Value->Type == EJson::String && !Pair.Value->AsString().IsEmpty())
        {
            OutAliases.Add(FName(*Pair.Value->AsString()), FName(*Pair.Key));
        }
    }
}

bool UReflectionsQuestPack::ImportJson()
{
    FString Report;
    bool bOk = true;
    if (!SourceJson.IsEmpty())
    {
        TArray<FReflectionsQuestDef> Parsed;
        if (ParseQuests(SourceJson, Parsed, Report)) Quests = MoveTemp(Parsed);
        else bOk = false;
        Items.Reset();
        ParseItems(SourceJson, Items);
    }
    if (!PeopleJson.IsEmpty())
    {
        MarkerAliases.Reset();
        ParseMarkerAliases(PeopleJson, MarkerAliases);
    }
    if (!PeopleJson.IsEmpty())
    {
        TArray<FReflectionsQuestPerson> Parsed;
        if (ParsePeople(PeopleJson, Parsed, Report)) People = MoveTemp(Parsed);
        else bOk = false;
    }
    ImportReport = Report;
    Modify();
    return bOk;
}
