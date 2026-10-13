# Builds: one line for everything that builds

Tessera Screen Manager builds one firmware at a time. Everything that builds a screen's firmware waits its turn in one
line: a firmware update (one screen, Update all, the nightly round), a plugin build, New screen, and Firmware & USB with
its YAML check. Nothing is refused because something else builds. It waits, and the editor says what it waits for.

The line is `screen_manager/app/build_queue.py` (`BuildQueue`). The Manager holds one (`manager.build_queue`), and it is
the only thing that starts an ESPHome job (`Firmware.start`).

## What a build is

A build is what was asked for one profile, with the steps of its kind:

| Kind (`by`) | Who asks | Its steps |
|---|---|---|
| `update` | Update, Update all, the nightly round, Reinstall from dev | `Updater.update_one`: install (over the bridge on a board with 4 MB when it must), wait for the screen to report the firmware, settle |
| `plugins` | Plugins page, a screen's Plugins tab | install the screen's firmware with its plugins file, then settle the plugins (`Plugins._built`) |
| `install` | New screen, Firmware & USB | one ESPHome action: build, install or download |
| `check` | Override YAML, Firmware & USB | `esphome config` |

A build keeps the slot until all of its steps are done. ESPHome is idle between two steps of an update (while the screen
restarts, or between the bridge and the firmware), and no other build starts in that gap.

## The order

- As asked, one after the other.
- What a person follows on the page goes first: New screen, Firmware & USB and the YAML check (`attended`) go before
  the updates and plugin builds that wait. They never stop the build that runs.
- A build that runs is never stopped for another.

## One build per screen

What is asked for a profile that already waits joins that build (`Build.join`):

- A plugin asked while the screen's plugin build waits builds once, with everything asked for it.
- A plugin build and an update of the same screen are one build. An update builds the screen's plugins file too, so the
  build becomes the update and settles the plugins once the screen's firmware went on (`installed`).
- An update asked again while it waits or runs stays the one update it is.
- What is asked while the screen's own build runs waits for a build after it. That build may have read its YAML
  already.

What a person follows (`attended`) never joins and is never joined. The same request twice (a second click) waits once.

## Rounds

Update all and the nightly round are a `Round`: one build that fails leaves the builds of its round that still wait out
(`skipped`), so a bad build never reaches the next screen. Builds asked apart, such as another screen's Update or a
plugin build, stay in the line. Between two updates of one round there is a pause (`Updater.pause_seconds`).

## Following a build

Every build has an id. The firmware answer (`GET api/firmware`) holds the line under `builds`: what runs, what waits in
order (with its turn, `place`, and the profile it waits for, `after`) and the last builds that ended (`ENDED`, newest
first), with how each ended (`success`, `failed`, `skipped`, `interrupted`), its `reason` and the memory it had. The log
of one build, also after the next one started, is `GET api/firmware/builds/{id}/log`.

`Manager.builds` gives the editor one record per screen (`id`, `by`, `state`, `place`, `phase`, `plugins`, `stage`) in
the live inventory. A YAML check builds nothing and has no record there.

In the editor, the builds store (`web/src/stores/builds.ts`) is the one place that reads both. `useLineBuild` (in
`composables/useFirmwareJob.ts`) follows one build by its id: New screen, Firmware & USB and the YAML check use it.
Never follow a build by "the firmware job that runs now": the next build starts at once, and its job is another one.

## Adding a kind of build

1. Give its steps as a coroutine that takes the build and returns `'success'`, `'failed'` or `'skipped'`. Every ESPHome
   action in it goes through `BuildQueue.step`.
2. Add it with `BuildQueue.add(by, file, run, ...)`, or `attended(request)` for one ESPHome action a person follows.
   Name its kind in `KINDS`, `Manager.builds` and the editor's `Build` type.
3. What must happen once it ended, whatever the outcome, goes in `build.ends`.
4. Test it in `tests/test_build_queue.py`.
