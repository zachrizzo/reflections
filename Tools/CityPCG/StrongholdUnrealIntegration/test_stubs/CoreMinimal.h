#pragma once

// Small test doubles for the API surface used by the adapter. They are not
// Unreal and are never included in an Unreal target.
#include <algorithm>
#include <cctype>
#include <cstdint>
#include <string>
#include <utility>
#include <vector>

using int32 = std::int32_t;
using uint8 = std::uint8_t;
using TCHAR = char;
#define TEXT(Text) Text

enum class ESearchCase { CaseSensitive };

struct FString
{
    std::string Value;
    FString() = default;
    FString(const char* In) : Value(In) {}
    explicit FString(std::string In) : Value(std::move(In)) {}
    bool Equals(const char* Other, ESearchCase) const { return Value == Other; }
    bool operator==(const FString& Other) const { return Value == Other.Value; }
};

struct FName
{
    std::string Value;
    FName() = default;
    FName(const char* In) : Value(In)
    {
        std::transform(Value.begin(), Value.end(), Value.begin(),
                       [](unsigned char C) { return static_cast<char>(std::tolower(C)); });
    }
    bool operator==(const FName& Other) const { return Value == Other.Value; }
};

struct FDateTime
{
    std::int64_t Ticks = 0;
    FDateTime() = default;
    explicit FDateTime(std::int64_t In) : Ticks(In) {}
    std::int64_t GetTicks() const { return Ticks; }
    bool operator!=(const FDateTime& Other) const { return Ticks != Other.Ticks; }
};

template <typename T> class TArray
{
public:
    int32 Num() const { return static_cast<int32>(Values.size()); }
    T& AddDefaulted_GetRef() { Values.emplace_back(); return Values.back(); }
    void Reset() { Values.clear(); }
    void Append(const T* Data, int32 Count) { Values.insert(Values.end(), Data, Data + Count); }
    const T* GetData() const { return Values.data(); }
    T& operator[](int32 Index) { return Values[static_cast<std::size_t>(Index)]; }
    const T& operator[](int32 Index) const { return Values[static_cast<std::size_t>(Index)]; }
    bool operator!=(const TArray& Other) const { return Values != Other.Values; }
    auto begin() { return Values.begin(); }
    auto end() { return Values.end(); }
    auto begin() const { return Values.begin(); }
    auto end() const { return Values.end(); }
private:
    std::vector<T> Values;
};

inline int GFakeIsValidCalls = 0;
template <typename T> bool IsValid(T* Object) { ++GFakeIsValidCalls; return Object != nullptr; }
inline bool GFakeGameThread = true;
inline bool IsInGameThread() { return GFakeGameThread; }
template <typename T> T&& MoveTemp(T& Value) { return std::move(Value); }
