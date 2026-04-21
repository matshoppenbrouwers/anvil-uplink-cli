# Hypotheses — anvil-uplink-cli v0.1.0 verification

Each hypothesis is phrased to be falsifiable by a single probe.

| # | Hypothesis | Kill-probe |
|---|---|---|
| H1 | All 8 commands from the plan's v1 scope table exist as Typer subcommands and appear in `--help` | `anvil-bridge --help` contains `init`, `doctor`, `call`, `query`, `tables`, `row`, `run`, `repl` |
| H2 | `--version` prints `anvil-bridge 0.1.0` and exits 0 | `anvil-bridge --version` stdout + exit code |
| H3 | `call`'s arg parser auto-coerces bare `42` to int, `true` to bool, everything else to str | unit test already covers this; re-assert via `test_args.py` |
| H4 | `_runner.run_or_exit` maps every `anvil.server` exception in the plan to its documented exit code | `test_errors.py` parameterized across 9 classes |
| H5 | Config round-trip: write profile via `save_config`, read via `load_config`, keys match | `test_config.py::test_config_roundtrip` |
| H6 | Key resolution order is explicit > env > keyring > env-var > file | `test_config.py` resolve_key tests |
| H7 | Serializer converts Row / Media / datetime / portable class / nested dicts to JSON-safe | `test_serialize.py` (21 tests) |
| H8 | Review Warning 1 (serialize-after-disconnect in query/row/call) is fixed: `to_jsonable` sits inside `with uplink(...)` | grep probe |
| H9 | Review Warning 2 (`run.py` docstring claims `anvil.server` but ns only has `anvil`) is fixed: `server` key in namespace | grep probe + functional probe |
| H10 | `init --non-interactive` without `--profile` refuses when profiles already exist | CLI probe |
| H11 | `ValueError` (bad `--kwarg`/`--filter`) exits with EXIT_USAGE=2, not EXIT_UNEXPECTED=1 | CLI probe with malformed `--kwarg` |
| H12 | Help flag `-h` and `--help` are both accepted | `anvil-bridge -h` exit 0 |
| H13 | `run` executes a script and propagates its exit code via SystemExit | CLI probe with `sys.exit(5)` script |
| H14 | Unknown profile surfaces as ConfigError / exit 41 | `anvil-bridge doctor --profile does-not-exist` |
| H15 | `query --limit 0` returns empty list (the zero-limit edge case reviewer flagged as correct) | unit-level probe |
| H16 | Every out-of-scope feature in the plan (daemon mode, MCP server, PyPI publication, Windows exe, log tailing, Client Uplink auto-fallback) is genuinely absent — not half-built | grep probe |
