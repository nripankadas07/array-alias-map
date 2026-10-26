"""Explain aliasing in bounded, declarative NumPy view pipelines."""
from itertools import combinations
import numpy as np


def analyze(spec):
    shape = spec.get('shape', [])
    if not isinstance(shape, list) or not 1 <= len(shape) <= 4 or any(type(n) is not int or not 1 <= n <= 64 for n in shape):
        raise ValueError('shape requires one to four integer dimensions in 1..64')
    size = int(np.prod(shape))
    if size > 4096:
        raise ValueError('base array exceeds 4096 elements')
    views = spec.get('views', [])
    if not isinstance(views, list) or len(views) > 16:
        raise ValueError('at most 16 views are supported')
    base = np.arange(size, dtype=np.int64).reshape(shape)
    arrays = {'base': base}
    origins = {'base': 'allocated'}
    for v in views:
        if not isinstance(v, dict):
            raise ValueError('views must contain objects')
        name = v.get('name')
        if not isinstance(name, str) or not name.isidentifier() or name in arrays:
            raise ValueError('view names must be unique identifiers')
        if v.get('source', 'base') not in arrays:
            raise ValueError('source must name an earlier view')
        a = arrays[v.get('source', 'base')]
        operations = v.get('operations', [])
        if not isinstance(operations, list) or len(operations) > 32:
            raise ValueError('at most 32 operations per view')
        for op in operations:
            if not isinstance(op, dict):
                raise ValueError('operations must contain objects')
            kind = op.get('op')
            if kind == 'slice':
                axes = op.get('axes', [])
                if not isinstance(axes, list) or len(axes) != a.ndim:
                    raise ValueError('slice needs one [start, stop, step] per axis')
                parts = []
                for x in axes:
                    if not isinstance(x, list) or len(x) != 3 or any(z is not None and type(z) is not int for z in x) or x[2] == 0:
                        raise ValueError('invalid slice')
                    parts.append(slice(*x))
                a = a[tuple(parts)]
            elif kind == 'transpose':
                axes = op.get('axes')
                if not isinstance(axes, list) or sorted(axes) != list(range(a.ndim)):
                    raise ValueError('transpose axes must be a permutation')
                a = a.transpose(axes)
            elif kind == 'copy':
                a = a.copy()
            elif kind == 'reshape':
                dims = op.get('shape')
                if not isinstance(dims, list) or not 1 <= len(dims) <= 4 or any(type(z) is not int or not 1 <= z <= 4096 for z in dims) or int(np.prod(dims)) != a.size:
                    raise ValueError('reshape must preserve element count')
                a = a.reshape(dims)
            else:
                raise ValueError('supported operations: slice, transpose, copy, reshape')
        arrays[name] = a
        origins[name] = v.get('source', 'base')
    # Address differences are used internally only; reports never leak raw pointers.
    def positions(a):
        start = a.__array_interface__['data'][0]
        out = {}
        for coord in np.ndindex(a.shape):
            addr = start + sum(i * s for i, s in zip(coord, a.strides))
            out.setdefault(addr, []).append(list(coord))
        return out
    maps = {name: positions(a) for name, a in arrays.items()}
    edges = []
    for left, right in combinations(arrays, 2):
        shared = sorted(maps[left].keys() & maps[right].keys())
        actual = bool(np.shares_memory(arrays[left], arrays[right]))
        if actual != bool(shared):
            raise RuntimeError('enumerated alias map disagrees with NumPy')
        witness = None
        if shared:
            p = shared[0]
            witness = {'left_coordinate': maps[left][p][0], 'right_coordinate': maps[right][p][0]}
        edges.append({'left': left, 'right': right, 'shared_elements': len(shared), 'shares_memory': actual, 'witness': witness})
    mutation = spec.get('mutation')
    propagation = []
    if mutation is not None:
        name, coord = mutation.get('view'), mutation.get('coordinate')
        if name not in arrays or not isinstance(coord, list) or len(coord) != arrays[name].ndim or any(type(i) is not int or not 0 <= i < n for i, n in zip(coord, arrays[name].shape)):
            raise ValueError('mutation needs an in-bounds coordinate and existing view')
        a = arrays[name]
        address = a.__array_interface__['data'][0] + sum(i * s for i, s in zip(coord, a.strides))
        # Identify all affected coordinates without changing arrays or input data.
        propagation = [{'view': key, 'coordinates': m[address]} for key, m in maps.items() if address in m]
    return {'numpy_version': np.__version__, 'limit_elements': 4096,
            'arrays': [{'name': key, 'source': origins[key], 'shape': list(a.shape), 'strides_bytes': list(a.strides), 'size': a.size, 'shares_base': bool(np.shares_memory(base, a))} for key, a in arrays.items()],
            'overlaps': edges, 'mutation_propagation': propagation}


import argparse
import html
import json
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser(description='Explain which coordinates share storage across NumPy slices, transposes, reshapes and copies.')
    parser.add_argument('input', type=Path, help='JSON scenario, at most 1 MiB')
    parser.add_argument('--html', type=Path, help='write an escaped, offline report')

    args = parser.parse_args()
    try:
        with args.input.open('rb') as handle:
            raw = handle.read(1048577)
        if len(raw) > 1048576:
            raise ValueError('input exceeds 1 MiB')
        spec = json.loads(raw)
        if not isinstance(spec, dict):
            raise ValueError('input must be a JSON object')
        result = analyze(spec)

        output = json.dumps(result, indent=2, allow_nan=False)
        if args.html:
            def show(value):
                if isinstance(value, dict):
                    return '<dl>' + ''.join('<dt>' + html.escape(str(k)) + '</dt><dd>' + show(v) + '</dd>' for k, v in value.items()) + '</dl>'
                if isinstance(value, list):
                    return '<ol>' + ''.join('<li>' + show(v) + '</li>' for v in value) + '</ol>'
                return '<span>' + html.escape(str(value)) + '</span>'
            page = '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>' + 'Array Alias Map' + '</title><style>body{max-width:1000px;margin:40px auto;padding:0 20px;font:16px/1.5 system-ui;color:#16324f;background:#f8fafc}h1{font-size:30px}dl{display:grid;grid-template-columns:minmax(150px,1fr) 3fr;gap:5px 20px}dt{font-weight:600;overflow-wrap:anywhere}dd{margin:0;overflow-wrap:anywhere}ol{padding-left:25px}li{padding:10px;border-bottom:1px solid #cbd5e1}span{white-space:pre-wrap}@media(max-width:600px){dl{display:block}dd{margin-bottom:15px}}</style><h1>' + 'Array Alias Map' + '</h1><p>Local diagnostic report. Review the documented scope before acting on a finding.</p>' + show(result) + '</html>'
            args.html.write_text(page, encoding='utf-8')
        print(output)
        return 0
    except (ValueError, TypeError, KeyError, OSError, OverflowError) as error:
        print('error: ' + str(error), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
