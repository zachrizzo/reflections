#include "Digging/ReflectionsDigMesher.h"

#include "CoreMinimal.h"
#include "Digging/ReflectionsDigGrid.h"
#include "Digging/ReflectionsDigTypes.h"

namespace
{
    constexpr int32 Side = FReflectionsDigChunkSamples::Side;
    constexpr int32 ChunkCells = ReflectionsDig::ChunkCells;

    /** Cubes -1 to 31 on each axis can carry a vertex: the four cubes around every owned edge. */
    constexpr int32 CubesPerAxis = ChunkCells + 1;
    constexpr int32 FirstCube = -1;

    /** Steps in the sample arrays for +1 on X, Y and Z. */
    constexpr int32 AxisStride[3] = { 1, Side, Side * Side };

    /**
     * Corner n of a cube sits at offset (n & 1, (n >> 1) & 1, (n >> 2) & 1).
     * The cube's twelve edges as (low corner, high corner); each runs one cell along one axis.
     */
    constexpr int32 EdgeCorners[12][2] = {
        { 0, 1 }, { 2, 3 }, { 4, 5 }, { 6, 7 },
        { 0, 2 }, { 1, 3 }, { 4, 6 }, { 5, 7 },
        { 0, 4 }, { 1, 5 }, { 2, 6 }, { 3, 7 },
    };

    FVector3f CornerOffset(int32 Corner)
    {
        return FVector3f(static_cast<float>(Corner & 1), static_cast<float>((Corner >> 1) & 1), static_cast<float>((Corner >> 2) & 1));
    }

    FIntVector AxisStep(int32 Axis)
    {
        return FIntVector(Axis == 0 ? 1 : 0, Axis == 1 ? 1 : 0, Axis == 2 ? 1 : 0);
    }

    /** One BuildFromSamples call: the samples, the output and the cube-to-vertex scratch table. */
    class FChunkMesher
    {
    public:
        FChunkMesher(const FReflectionsDigChunkSamples& InSamples, FReflectionsDigMeshData& InOut)
            : Samples(InSamples)
            , Density(InSamples.Density.GetData())
            , Out(InOut)
        {
            CubeVertex.Init(INDEX_NONE, CubesPerAxis * CubesPerAxis * CubesPerAxis);
        }

        void Build()
        {
            for (int32 Z = 0; Z < ChunkCells; ++Z)
            {
                for (int32 Y = 0; Y < ChunkCells; ++Y)
                {
                    for (int32 X = 0; X < ChunkCells; ++X)
                    {
                        const int32 Index = FReflectionsDigChunkSamples::IndexOf(X, Y, Z);
                        const bool bSolid = Density[Index] > 0;
                        for (int32 Axis = 0; Axis < 3; ++Axis)
                        {
                            if ((Density[Index + AxisStride[Axis]] > 0) != bSolid)
                            {
                                EmitQuad(FIntVector(X, Y, Z), Axis, bSolid);
                            }
                        }
                    }
                }
            }
        }

    private:
        /**
         * The quad of the owned edge from Cell one step along Axis, joining the four cubes around it.
         * With U and V the next two axes in cyclic order, the cubes C00 = Cell, C10 = Cell - U,
         * C11 = Cell - U - V and C01 = Cell - V go counter-clockwise around +Axis.
         * VectorUtil::Normal(A, B, C) is the normalised (C - A) x (B - A), so a triangle (C00, C11, C10)
         * faces +Axis: that is the winding when Cell is solid (air lies along +Axis), reversed otherwise.
         */
        void EmitQuad(const FIntVector& Cell, int32 Axis, bool bStartSolid)
        {
            const FIntVector U = AxisStep((Axis + 1) % 3);
            const FIntVector V = AxisStep((Axis + 2) % 3);
            const int32 V00 = FindOrAddVertex(Cell);
            const int32 V10 = FindOrAddVertex(Cell - U);
            const int32 V11 = FindOrAddVertex(Cell - U - V);
            const int32 V01 = FindOrAddVertex(Cell - V);

            if (bStartSolid)
            {
                Out.Triangles.Append({ V00, V11, V10, V00, V01, V11 });
            }
            else
            {
                Out.Triangles.Append({ V00, V10, V11, V00, V11, V01 });
            }

            // A vertex whose gradient vanished takes the normal of the first quad that uses it: this one.
            const int32 QuadVertices[4] = { V00, V10, V11, V01 };
            for (int32 Vertex : QuadVertices)
            {
                if (Out.Normals[Vertex].IsZero())
                {
                    Out.Normals[Vertex] = QuadNormal(V00, V10, V11, V01, Axis, bStartSolid);
                }
            }
        }

        /** Unit normal of the quad from solid toward air; the edge's direction when the quad is degenerate. */
        FVector3f QuadNormal(int32 V00, int32 V10, int32 V11, int32 V01, int32 Axis, bool bStartSolid) const
        {
            const float Sign = bStartSolid ? 1.0f : -1.0f;
            // For C00, C10, C11, C01 counter-clockwise around +Axis the diagonal cross product points along +Axis.
            const FVector3f Cross = (Out.Positions[V11] - Out.Positions[V00]) ^ (Out.Positions[V01] - Out.Positions[V10]);
            const float LengthSquared = Cross.SizeSquared();
            if (LengthSquared > UE_SMALL_NUMBER)
            {
                return Cross * (Sign / FMath::Sqrt(LengthSquared));
            }
            return FVector3f(AxisStep(Axis)) * Sign;
        }

        int32 FindOrAddVertex(const FIntVector& Cube)
        {
            const int32 Slot = (Cube.X - FirstCube) + ((Cube.Y - FirstCube) + (Cube.Z - FirstCube) * CubesPerAxis) * CubesPerAxis;
            int32& Vertex = CubeVertex[Slot];
            if (Vertex == INDEX_NONE)
            {
                Vertex = AddCubeVertex(Cube);
            }
            return Vertex;
        }

        /**
         * The vertex of a cube with both solid and non-solid corners: the mean of the 0.5-level crossings
         * on its sign-changing edges, strictly inside the cube. Everything is computed relative to the cube from its own samples, so
         * a neighbouring chunk computes the same vertex for the same cube bit for bit. Leaves the normal
         * zero when the gradient vanishes; EmitQuad then fills it in.
         */
        int32 AddCubeVertex(const FIntVector& Cube)
        {
            const int32 BaseIndex = FReflectionsDigChunkSamples::IndexOf(Cube.X, Cube.Y, Cube.Z);
            int32 CornerIndex[8];
            float CornerDensity[8];
            for (int32 Corner = 0; Corner < 8; ++Corner)
            {
                CornerIndex[Corner] = BaseIndex
                    + (Corner & 1) * AxisStride[0]
                    + ((Corner >> 1) & 1) * AxisStride[1]
                    + ((Corner >> 2) & 1) * AxisStride[2];
                CornerDensity[Corner] = Density[CornerIndex[Corner]];
            }

            FVector3f CrossingSum = FVector3f::ZeroVector;
            int32 CrossingCount = 0;
            for (const int32 (&Edge)[2] : EdgeCorners)
            {
                const bool bFirstSolid = CornerDensity[Edge[0]] > 0.0f;
                if (bFirstSolid == (CornerDensity[Edge[1]] > 0.0f))
                {
                    continue;
                }
                // The surface is the 0.5 density level: from the solid corner (density at least 1) to the
                // other (at most 0), t = (DSolid - 0.5) / (DSolid - DAir) is strictly between 0 and 1.
                const int32 SolidCorner = bFirstSolid ? Edge[0] : Edge[1];
                const int32 AirCorner = bFirstSolid ? Edge[1] : Edge[0];
                const float DSolid = CornerDensity[SolidCorner];
                const float T = (DSolid - 0.5f) / (DSolid - CornerDensity[AirCorner]);
                const FVector3f PSolid = CornerOffset(SolidCorner);
                CrossingSum += PSolid + (CornerOffset(AirCorner) - PSolid) * T;
                ++CrossingCount;
            }
            // Only cubes around a sign-changing edge get here, so CrossingCount is at least 1.
            const FVector3f Offset = CrossingSum / static_cast<float>(CrossingCount);

            // Central-difference gradient at each corner, trilinearly interpolated at the vertex.
            FVector3f Gradient = FVector3f::ZeroVector;
            for (int32 Corner = 0; Corner < 8; ++Corner)
            {
                const int32 Index = CornerIndex[Corner];
                const FVector3f CornerGradient(
                    static_cast<float>(Density[Index + AxisStride[0]] - Density[Index - AxisStride[0]]),
                    static_cast<float>(Density[Index + AxisStride[1]] - Density[Index - AxisStride[1]]),
                    static_cast<float>(Density[Index + AxisStride[2]] - Density[Index - AxisStride[2]]));
                const float Weight = ((Corner & 1) ? Offset.X : 1.0f - Offset.X)
                    * (((Corner >> 1) & 1) ? Offset.Y : 1.0f - Offset.Y)
                    * (((Corner >> 2) & 1) ? Offset.Z : 1.0f - Offset.Z);
                Gradient += CornerGradient * Weight;
            }
            const float GradientLengthSquared = Gradient.SizeSquared();
            const FVector3f Normal = GradientLengthSquared > UE_SMALL_NUMBER
                ? Gradient * (-1.0f / FMath::Sqrt(GradientLengthSquared))
                : FVector3f::ZeroVector;

            // Material of the densest solid corner; ties go to the lowest corner index.
            int32 MaterialCorner = INDEX_NONE;
            for (int32 Corner = 0; Corner < 8; ++Corner)
            {
                if (CornerDensity[Corner] > 0.0f && (MaterialCorner == INDEX_NONE || CornerDensity[Corner] > CornerDensity[MaterialCorner]))
                {
                    MaterialCorner = Corner;
                }
            }
            // A cube with a sign change has a solid corner, so MaterialCorner is set.
            const uint8 Material = Samples.Material[CornerIndex[MaterialCorner]];

            // The cube's corner is a whole multiple of 50 cm, exact in float in either chunk that holds it.
            const FVector3f CubeOriginCm = Samples.LocalOriginCm + FVector3f(Cube) * ReflectionsDig::CellSizeCm;
            Out.Positions.Add(CubeOriginCm + Offset * ReflectionsDig::CellSizeCm);
            Out.Normals.Add(Normal);
            return Out.Materials.Add(Material);
        }

        const FReflectionsDigChunkSamples& Samples;
        const int8* Density;
        FReflectionsDigMeshData& Out;
        /** Vertex index of each cube -1 to 31 on every axis, INDEX_NONE until a quad needs it. */
        TArray<int32> CubeVertex;
    };
}

void FReflectionsDigMeshData::Reset()
{
    Positions.Reset();
    Normals.Reset();
    Triangles.Reset();
    Materials.Reset();
}

bool FReflectionsDigMeshData::IsEmpty() const
{
    return Triangles.IsEmpty();
}

void ReflectionsDigMesher::BuildFromSamples(const FReflectionsDigChunkSamples& Samples, FReflectionsDigMeshData& Out)
{
    Out.Reset();
    constexpr int32 NumSamples = Side * Side * Side;
    if (!ensureMsgf(Samples.Density.Num() == NumSamples && Samples.Material.Num() == NumSamples,
        TEXT("Dig mesher: a chunk sample copy needs %d densities and materials, got %d and %d"),
        NumSamples, Samples.Density.Num(), Samples.Material.Num()))
    {
        return;
    }
    FChunkMesher Mesher(Samples, Out);
    Mesher.Build();
}

void ReflectionsDigMesher::BuildChunk(const FReflectionsDigGrid& Grid, FIntVector Chunk, FReflectionsDigMeshData& Out)
{
    FReflectionsDigChunkSamples Samples;
    Grid.CopyChunkSamples(Chunk, Samples);
    BuildFromSamples(Samples, Out);
}
