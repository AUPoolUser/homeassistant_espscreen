# Host probe

A plugin for Tessera's own host render (`tools/render/run.py --plugin tests/fixtures/plugins/host_probe`): it writes
every moment of the plugin API to the log, so the harness can prove on the real firmware, built for this computer, that a
plugin tile is made, fed, ticked, recoloured, tapped and deleted at the right moments, and that a card, a tap action, a
bar item, the settings rows, a question to the app and the pictures on a tile (plugin API 0.10) work. It is never on a screen.

## Set up

Nothing: the render harness builds it in.
