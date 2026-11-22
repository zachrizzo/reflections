# Spike logs

The measurement lines of every log that `../SpikeResults.md` names. The full logs stay on the machine that ran them
(`.superpowers/logs/` of the digging worktree) and are not committed.

Each file holds the log's first and last line and every line that contains `DIGSPIKE `, the command line, the web
browser lines and the test results. That is what `Tools/Digging/summarize_spike_log.py` reads:

```
python Tools/Digging/summarize_spike_log.py ArtDirection/Digging/SpikeLogs/test-111229.digspike.log
```

One figure differs from the full log: the run length. The script takes it from the first and last timestamped line,
and these files do not keep the lines around them.

| Files | What they are |
|---|---|
| `test-090807`, `test-091247`, `test-091739` | The three runs before the navigation fix (embedded web browser on) |
| `test-111229`, `test-111733`, `test-112230`, `test-112757` | The four runs the results tables use (after the fix, browser off) |
| `test-101716` | Traced run of the busy-chunk test alone, before the fix |
| `test-110014` | Traced run of the whole suite after the fix, browser on |
| `test-113818` | Traced run of the whole suite after the fix, browser off |

The profiler traces themselves (three `.utrace` files, 51 to 430 MB) are not kept in the repository.
