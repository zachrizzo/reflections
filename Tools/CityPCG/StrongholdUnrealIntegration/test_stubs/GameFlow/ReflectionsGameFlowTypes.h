#pragma once
#include "CoreMinimal.h"

struct FReflectionsSaveBlob
{
    FName System;
    TArray<uint8> Data;
};

struct FReflectionsCheckpoint
{
    bool bValid = false;
    FString MapPath;
    FDateTime SavedAt;
    TArray<FReflectionsSaveBlob> SystemData;
    int32 Sentinel = 0;
};
