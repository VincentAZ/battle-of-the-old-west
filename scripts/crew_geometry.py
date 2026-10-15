"""Fingerprint GLB mesh positions and topology independently of names and textures."""
import hashlib
import json
from pathlib import Path
import struct


def geometry_fingerprint(path):
    raw = Path(path).read_bytes()
    magic, version, length = struct.unpack_from('<4sII', raw)
    assert magic == b'glTF' and version == 2 and length == len(raw)
    chunks = {}
    offset = 12
    while offset < length:
        size, kind = struct.unpack_from('<II', raw, offset)
        offset += 8
        chunks[kind] = raw[offset:offset + size]
        offset += size
    document = json.loads(chunks[0x4E4F534A])
    binary = chunks[0x004E4942]
    formats = {5120: 'b', 5121: 'B', 5122: 'h', 5123: 'H', 5125: 'I', 5126: 'f'}
    widths = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4}

    def values(index):
        accessor = document['accessors'][index]
        assert 'sparse' not in accessor, 'Sparse accessor requires explicit support'
        view = document['bufferViews'][accessor['bufferView']]
        assert view.get('buffer', 0) == 0
        fmt = '<' + formats[accessor['componentType']] * widths[accessor['type']]
        stride = view.get('byteStride', struct.calcsize(fmt))
        start = view.get('byteOffset', 0) + accessor.get('byteOffset', 0)
        return [struct.unpack_from(fmt, binary, start + n * stride)
                for n in range(accessor['count'])]

    digest = hashlib.sha256()
    vertices = triangles = 0
    for mesh in document['meshes']:
        for primitive in mesh['primitives']:
            assert primitive.get('mode', 4) == 4, 'Only triangle meshes are expected'
            positions = values(primitive['attributes']['POSITION'])
            indices = values(primitive['indices']) if 'indices' in primitive else [(n,) for n in range(len(positions))]
            assert len(indices) % 3 == 0
            digest.update(struct.pack('<II', len(positions), len(indices)))
            for position in positions:
                digest.update(struct.pack('<fff', *position))
            for index in indices:
                digest.update(struct.pack('<I', index[0]))
            vertices += len(positions)
            triangles += len(indices) // 3
    assert vertices and triangles
    return {'sha256': digest.hexdigest(), 'vertices': vertices, 'triangles': triangles}
