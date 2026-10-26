import unittest
import numpy as np
from array_alias_map import analyze


class Views(unittest.TestCase):
    def test_reverse_transpose_witness_and_copy(self):
        result = analyze({'shape': [3, 4], 'views': [
            {'name': 'reverse', 'operations': [{'op': 'slice', 'axes': [[None, None, -1], [None, None, 2]]}]},
            {'name': 'transposed', 'source': 'reverse', 'operations': [{'op': 'transpose', 'axes': [1, 0]}]},
            {'name': 'detached', 'source': 'transposed', 'operations': [{'op': 'copy'}]}],
            'mutation': {'view': 'transposed', 'coordinate': [1, 0]}})
        changed = {x['view']: x['coordinates'] for x in result['mutation_propagation']}
        self.assertEqual(changed, {'base': [[2, 2]], 'reverse': [[0, 1]], 'transposed': [[1, 0]]})
        self.assertFalse(next(x for x in result['arrays'] if x['name'] == 'detached')['shares_base'])

    def test_empty_and_disjoint(self):
        r = analyze({'shape': [8], 'views': [
            {'name': 'even', 'operations': [{'op': 'slice', 'axes': [[0, None, 2]]}]},
            {'name': 'odd', 'operations': [{'op': 'slice', 'axes': [[1, None, 2]]}]},
            {'name': 'empty', 'operations': [{'op': 'slice', 'axes': [[0, 0, 1]]}]}]})
        self.assertFalse(next(x for x in r['overlaps'] if x['left'] == 'even' and x['right'] == 'odd')['shares_memory'])
        self.assertEqual(next(x for x in r['arrays'] if x['name'] == 'empty')['size'], 0)

    def test_mutation_oracle(self):
        # Independent actual writes confirm coordinate propagation for many slices.
        for step in [-3, -1, 1, 2, 3]:
            for start in [None, 0, 1, 5]:
                a = np.arange(30).reshape(5, 6)
                view = a[slice(start, None, step), ::2].T
                if not view.size:
                    continue
                coord = [0, 0]
                r = analyze({'shape': [5, 6], 'views': [{'name': 'v', 'operations': [{'op': 'slice', 'axes': [[start, None, step], [None, None, 2]]}, {'op': 'transpose', 'axes': [1, 0]}]}], 'mutation': {'view': 'v', 'coordinate': coord}})
                view[tuple(coord)] = -999
                got = next(x['coordinates'] for x in r['mutation_propagation'] if x['view'] == 'base')
                self.assertEqual(got, np.argwhere(a == -999).tolist())

    def test_reject_unsafe_or_unbounded(self):
        for spec in [{'shape': [64, 64, 64]}, {'shape': [4], 'views': [{'name': 'x', 'operations': [{'op': 'as_strided'}]}]}, {'shape': [4], 'mutation': {'view': 'base', 'coordinate': [-1]}}]:
            with self.assertRaises(ValueError):
                analyze(spec)


if __name__ == '__main__':
    unittest.main()
