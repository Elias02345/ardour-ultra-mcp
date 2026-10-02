# Local audio analysis and iteration

Install `[analysis]`. Explicit --media-root/--export-root permissions are required. The tools accept exact files, not directory browsing. Supported decoded containers include WAV/AIFF/FLAC/OGG/CAF where libsndfile supports the actual codec. Unicode and spaces are allowed. Default deny paths outside approved resolved roots; symlink escape is rejected.

`analyze_audio_file` runs NumPy/SciPy/SoundFile/pyloudnorm outside Ardour on a Python worker thread. Work is serialized and bounded to mono/stereo, max_seconds (default inspect schema) and 32 million decoded scalar values. Larger files fail with an actionable error rather than silently truncate. Metrics:

* Global sample peak/RMS in dBFS and crest factor in dB.
* Gated integrated LUFS for audio at least 400ms; silence/too-short values return null with warning.
* **Estimated** true peak in dBTP using fourfold polyphase oversampling; not BS.1770 conformance-certified.
* Welch spectral band fractions and spectral centroid in Hz. Bands above the file's Nyquist frequency are omitted; a partially available band ends at Nyquist.
* Stereo phase correlation, mid/side RMS relationship, channel/DC statistics.
* Silence duration using nonoverlapping 20ms blocks with every channel sample peak below -60dBFS.
* Count of sample values at or above full scale. This is evidence of full-scale samples, not proof of every audible distortion event.

No professional-quality score, invented musical mood, LRA/dynamic-range certification, reliable transient/tempo/pitch estimator, or cloud generation is exposed. Crest factor is not advertised as a full dynamic-range standard.

`compare_audio_files` analyzes both and returns second-minus-first changes for comparable metrics. Compare the same range/channel layout to make useful mix decisions.

The primitives for a feedback loop are `render_range`, `analyze_audio_file`, `compare_audio_files`, precise parameter edits and current-state queries. Rendering is experimental preset-based master export into a new empty directory. render_and_analyze combines a single-file export and analysis, preserving export paths and reporting the stage if analysis fails. It preflights analysis dependencies before rendering and supports dry_run; it is not an atomic disk transaction. No hidden mastering presets. Inspect successful export files, analyze, change explicit values, render into another new directory and compare. See final gap analysis before relying on unattended complete production.

For gain comparisons, select a verified preset with normalization disabled. Ardour SimpleExport defaults to its CD preset, whose shipped format enables peak normalization; that can mask a master-gain change. The source-verified bundled WAV @ session-rate preset ID is `75969a1c-3133-4694-864b-a1fa50e43348`. Pass it as preset_id and let preflight confirm availability. User-modified presets can differ; bound SimpleExport does not expose their full settings, so this is not an automatic guarantee about an edited preset. Export results report the requested ID, actual decoded file metadata and an explicit preset-settings warning.
