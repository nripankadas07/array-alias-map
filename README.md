# Array Alias Map

Explain which coordinates share storage across NumPy slices, transposes, reshapes and copies.

This is a small diagnostic for a concrete debugging task, with a Python API and a JSON command line. It uses NumPy directly and reports the installed version. It is independent of the upstream project and is not affiliated with or endorsed by its maintainers.

## Try the example

Python 3.12 or later is required. From a checkout of this repository:

```sh
python -m venv .venv
. .venv/bin/activate
python -m pip install .
array-alias-map views.json --html report.html
```

The command prints JSON and writes an offline HTML report. Open `report.html` in a browser. No account or server is required. The example is synthetic and contains no private data. See [the example guide](EXAMPLE.md) for the expected result and input contract.

On Windows, activate `.venv\Scripts\activate` instead. Linux is the tested CI platform; other operating systems are not certified.

## Scope and limits

4096 base elements, 16 views and 32 operations per view. Fixed int64 data only; no object arrays, stride tricks, reinterpret casts or arbitrary Python.

Invalid JSON, rejected options and unavailable input files return exit status 2. A completed diagnostic returns 0, including when it finds a problem; inspect the report fields for findings. Package/runtime failures may raise an exception. Do not pass private input data into a public issue or attach generated reports without reviewing their contents.

Compatibility is pinned to `numpy==2.5.4`. Other releases are not claimed compatible. The [research brief](RESEARCH.md) explains the problem evidence, alternatives and tradeoffs. No performance or adoption advantage is claimed.

## Development

```sh
python -m unittest -v test_core
python -m compileall -q array_alias_map.py
python -m pip wheel --no-deps --wheel-dir dist .
python -m pip install dist/*.whl
python check_installed_cli.py
```

CI also installs a wheel in a fresh environment and runs the command outside the checkout. [Contributing](CONTRIBUTING.md), [support](SUPPORT.md) and [security reporting](SECURITY.md) describe the maintenance scope. Original project code is MIT licensed; upstream software keeps its own license. See [attribution](ATTRIBUTION.md).
