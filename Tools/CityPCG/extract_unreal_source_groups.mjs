// Experimental, read-only UE 5.9 MeshDescription group extraction.
// Loads an externally supplied, hash-pinned MIT raw-unreal 0.1.13 parser;
// its 5.9 FName patch and rendering-only stubs exist in memory only.
import fs from 'node:fs';
import { createHash } from 'node:crypto';

const expectedAsset = 'fad42a2a33c47b14298e5206fbbd3f3e60b3124ea8316f4f35077539824673f1';
const expectedPayload = '147621d39e17a2288a7559e8fa846ed07e3090e384d4855b266891d29953f83c';
const expectedParser = 'bff54c6adf1958211246cbd571ad55d70628c14bfaf74deb572d31fc4eec0d70';
const [parserPath, assetPath, payloadPath] = process.argv.slice(2);
if (!parserPath || !assetPath || !payloadPath || process.argv.length !== 5)
  throw Error('Expected raw-unreal index.js, source uasset, and verified payload paths.');
const sha = bytes => createHash('sha256').update(bytes).digest('hex');
const assert = (ok, reason) => { if (!ok) throw Error(reason); };
let parser = fs.readFileSync(parserPath, 'utf8');
assert(sha(Buffer.from(parser)) === expectedParser, 'Expected unmodified raw-unreal 0.1.13 index.js.');
const renderImport = "import { BufferGeometry, BufferAttribute, Mesh, Loader, FileLoader, MeshStandardMaterial } from 'three';";
assert(parser.startsWith(renderImport), 'Unexpected parser imports.');
parser = parser.replace(renderImport, 'class BufferGeometry {}\nclass BufferAttribute {}\nclass Mesh {}\nclass Loader {}\nclass FileLoader {}\nclass MeshStandardMaterial {}');
const functionStart = parser.indexOf('function readAttributeEntry2(reader, rawName) {');
const nameStart = parser.indexOf('    if (type.kind === "name") {', functionStart);
const nameEnd = parser.indexOf('      channel = { extent: channelExtent, values, serializedCount: count };', nameStart);
assert(functionStart >= 0 && nameStart > functionStart && nameEnd > nameStart, 'Cannot identify the 0.1.13 FName decoder.');
// Based on UE 5.9 MeshAttributeArray.h's DynamicMeshAttributesTriangleLabels
// FName serialization: count, unique strings, then optional narrow indices.
const nameDecoder = `    if (type.kind === "name") {
      const count = reader.int32(name + " FName count");
      assertUAsset(count >= 0 && count <= MAX_ATTRIBUTE_VALUES2, "INVALID_MESH_DESCRIPTION", "Invalid FName count", {count});
      const uniqueCount = count ? reader.uint32(name + " unique FName count") : 0;
      assertUAsset(uniqueCount <= count && (!count || uniqueCount > 0), "INVALID_MESH_DESCRIPTION", "Invalid unique FName count", {count, uniqueCount});
      const unique = [];
      for (let index = 0; index < uniqueCount; index += 1) unique.push(reader.fstring(name + " unique name"));
      let values;
      if (uniqueCount === 1) values = Array(count).fill(unique[0]);
      else if (uniqueCount === count) values = unique;
      else if (count === 0) values = [];
      else {
        const width = reader.uint8(name + " FName index size");
        assertUAsset(width <= 2, "INVALID_MESH_DESCRIPTION", "Invalid FName index size", {width});
        values = [];
        for (let index = 0; index < count; index += 1) {
          let nameIndex;
          if (width === 0) nameIndex = reader.uint8(name + " FName index");
          else if (width === 1) { const data = reader.raw(2, name + " FName index"); nameIndex = new DataView(data.buffer, data.byteOffset, 2).getUint16(0, true); }
          else nameIndex = reader.uint32(name + " FName index");
          assertUAsset(nameIndex < uniqueCount, "INVALID_MESH_DESCRIPTION", "Invalid FName index", {nameIndex, uniqueCount});
          values.push(unique[nameIndex]);
        }
      }
`;
parser = parser.slice(0, nameStart) + nameDecoder + parser.slice(nameEnd);
function insertBeforeInFunction(functionName, marker, text) {
  const start = parser.indexOf(functionName);
  const position = parser.indexOf(marker, start);
  assert(start >= 0 && position > start, `Could not strengthen parser: ${functionName}`);
  parser = parser.slice(0, position) + text + parser.slice(position);
}
insertBeforeInFunction('function readAttributesSet(reader)', '    attributes.set(entry.name, entry);',
  '    assertUAsset(!attributes.has(entry.name), "INVALID_MESH_DESCRIPTION", "Duplicate attribute");\n');
insertBeforeInFunction('function parseMeshDescription(input, offset = 0)', '    elements.set(name, { name, channels });',
  '    assertUAsset(!elements.has(name), "INVALID_MESH_DESCRIPTION", "Duplicate element container");\n');
const { parseMeshDescription } = await import('data:text/javascript;base64,' + Buffer.from(parser).toString('base64'));
const asset = fs.readFileSync(assetPath);
const payload = fs.readFileSync(payloadPath);
assert(sha(asset) === expectedAsset && sha(payload) === expectedPayload, 'Asset or payload SHA-256 changed.');
const mesh = parseMeshDescription(payload);
assert(mesh.byteLength === payload.length && mesh.trailingBytes === 0, 'Incomplete payload parse.');
const expectedNames = ['Vertices','VertexInstances','UVs','Edges','Triangles','Polygons','PolygonGroups'];
assert(mesh.elements.size === expectedNames.length && expectedNames.every(name => mesh.elements.has(name)), 'Unexpected element schema.');
function element(name) {
  const item = mesh.elements.get(name);
  assert(item.channels.length === 1, `${name} channel count changed`);
  const channel = item.channels[0];
  const ids = channel.allocation.validIds;
  assert(ids.length === channel.allocation.numBits && ids.every((id, i) => id === i), `${name} contains ID gaps`);
  return channel;
}
function attribute(elementName, attributeName, type, extent, ctor) {
  const item = element(elementName).attributeSet.attributes.get(attributeName);
  assert(item && item.type === type && item.extent === extent && item.channels.length === 1,
    `${elementName}.${attributeName} has unexpected type/extent/channels`);
  const value = item.channels[0].values;
  assert(value instanceof ctor && item.numElements === element(elementName).allocation.numBits &&
    value.length === item.numElements * extent * item.components, `${elementName}.${attributeName} has unexpected length`);
  return value;
}
const positions = attribute('Vertices','Position','FVector3f',1,Float32Array);
const instanceVertex = attribute('VertexInstances','VertexIndex','int32',1,Int32Array);
const triangleInstances = attribute('Triangles','VertexInstanceIndex','int32',3,Int32Array);
const triangleGroup = attribute('Triangles','PolygonGroupIndex','int32',1,Int32Array);
const trianglePolygon = attribute('Triangles','PolygonIndex','int32',1,Int32Array);
const polygonGroup = attribute('Polygons','PolygonGroupIndex','int32',1,Int32Array);
const names = attribute('PolygonGroups','ImportedMaterialSlotName','FName',1,Array);
assert(names.length > 0 && names.every(name => typeof name === 'string' && name.length) &&
  new Set(names).size === names.length, 'Polygon-group slot names are empty or ambiguous.');
const sections = names.map((slot, index) => ({section: index, slot, triangles: []}));
const seen = new Map();
const scale = Math.fround(.01);
function vertex(index) {
  assert(Number.isInteger(index) && index >= 0 && index < positions.length / 3, 'Invalid vertex index.');
  const p = [positions[index * 3], positions[index * 3 + 2], positions[index * 3 + 1]];
  const b = Buffer.allocUnsafe(12);
  p.forEach((x, i) => {
    const v = Math.fround(x * scale);
    assert(Number.isFinite(v), 'Non-finite vertex.');
    b.writeFloatLE(v === 0 ? 0 : v, i * 4);
  });
  return b;
}
for (let t = 0; t < triangleGroup.length; ++t) {
  const group = triangleGroup[t], poly = trianglePolygon[t];
  assert(group >= 0 && group < sections.length && poly >= 0 && poly < polygonGroup.length &&
    polygonGroup[poly] === group, 'Triangle polygon/group link is inconsistent.');
  const points = [0,1,2].map(c => {
    const instance = triangleInstances[t * 3 + c];
    assert(instance >= 0 && instance < instanceVertex.length, 'Invalid vertex-instance index.');
    return vertex(instanceVertex[instance]);
  });
  assert(!points[0].equals(points[1]) && !points[1].equals(points[2]) && !points[2].equals(points[0]), 'Degenerate triangle.');
  const rotations = [Buffer.concat(points), Buffer.concat([points[1],points[2],points[0]]),
                     Buffer.concat([points[2],points[0],points[1]])];
  rotations.sort(Buffer.compare);
  const key = rotations[0].toString('hex');
  assert(!seen.has(key) || seen.get(key) === group, 'Signed triangle belongs to multiple source groups.');
  seen.set(key, group);
  sections[group].triangles.push(key);
}
assert(sections.every(row => row.triangles.length > 0), 'Source contains an empty polygon group.');
assert(sha(fs.readFileSync(assetPath)) === expectedAsset && sha(fs.readFileSync(payloadPath)) === expectedPayload,
  'Asset or payload changed during extraction.');
console.log(JSON.stringify({asset_sha256: expectedAsset, payload_sha256: expectedPayload, parser_sha256: expectedParser,
  consumed: mesh.byteLength, trailing: mesh.trailingBytes, sections}));
