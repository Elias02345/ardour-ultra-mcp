# Generic plugins

Query `list_available_plugins` with pagination and name_filter; inventory comes from Ardour's PluginManager. `instruments_only: true` narrows it to actual instrument metadata. The simulator inventory is labelled fictitious. Plugin format availability depends on the Ardour build and installed plugins: LV2/LADSPA and optional VST2/VST3/AudioUnit support must be queried, not inferred from OS.

Use inventory `plugin_id` and `format` in `add_plugin`, then retain the returned stable `processor_id`. Inspect instances through `list_track_plugins`, which distinguishes inserts from other processors. Address parameters by instance plus Ardour control parameter ordinal, never a name alone.

```json
{"track_id":"ROUTE_ID","processor_id":"PROCESSOR_ID","parameters":[{"parameter_index":0,"value":1834.5,"unit":"plugin_native"}]}
```

Read `get_plugin_parameters` before setting values. Descriptors report name, native min/max/default, current value, integer/toggle/log flags and available display formatting metadata. Not every plugin exposes Hz/ms/dB through Lua; `plugin_native` is an honest explicit unit, and normalized values are not invented. The example's value must be within the actual selected parameter's range; it does not assume that ordinal 0 is cutoff or uses Hz. Batch changes are prevalidated and compensate applied values on failure; plugin side effects are not transactional.

`set_plugin_enabled` changes activation. `list_plugin_presets` and `load_plugin_preset` use actual plugin preset labels; preset loading can affect many parameters and is not natively undoable. `remove_plugin` needs explicit destructive intent. Scanning, preset saving, processor reorder/copy, binary state export and semantic plugin profiles are not enabled. Inventory reads already known Ardour plugins; it does not force an arbitrary disk scan.

No proprietary instrument is required. Optional free plugins include Ardour bundled LV2, x42, LSP, Calf and Surge XT; check platform/build and individual licenses. A mastering or vocal-chain workflow must select actual inventory IDs and explicit parameter values rather than an assumed brand or hidden preset.
