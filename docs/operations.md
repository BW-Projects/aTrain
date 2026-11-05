# Operations

For administrators who run aTrain and need to know what it records.

## Event log

aTrain writes security-relevant events to one log file per user. Nothing sends
this file anywhere.

| Install             | File                                                                                  |
| ------------------- | ------------------------------------------------------------------------------------- |
| Windows (MSIX)      | `%LOCALAPPDATA%\Packages\<PackageFamilyName>\LocalCache\Local\aTrain\Logs\atrain.log` |
| Windows from source | `%LOCALAPPDATA%\aTrain\Logs\atrain.log`                                               |
| Linux (Flatpak)     | `~/.var/app/io.github.juergenfleiss.aTrain/.local/state/aTrain/log/atrain.log`        |
| Linux from source   | `~/.local/state/aTrain/log/atrain.log`                                                |
| macOS               | `~/Library/Logs/aTrain/atrain.log`                                                    |

Windows redirects what the MSIX writes under `%LOCALAPPDATA%` into the package
folder, so the file does not appear at the plain path. Uninstalling the MSIX
deletes the log with that folder.

The app writes this log. The `aTrain_core` command line does not.

### Format

One line per event: time with UTC offset, level, event name, then `key=value`
fields. Unhandled exceptions add a traceback below their line.

```
2026-11-05 08:48:19+0100 INFO file_accepted file='Interview.mp3' size=29106
2026-11-05 08:48:19+0100 INFO transcription_started file_id='2611050848-Intervi' model='large-v3-turbo' device='gpu'
2026-11-05 08:48:37+0100 INFO transcription_finished file_id='2611050848-Intervi'
2026-11-05 08:49:22+0100 INFO transcript_deleted file_id='2611050848-Intervi'
```

### Events

| Event                                                                                            | Fields                                 |
| ------------------------------------------------------------------------------------------------ | -------------------------------------- |
| `server_started`, `server_stopped`                                                               | version, native, host, port (at start) |
| `file_accepted`, `file_rejected`                                                                 | file name, size, reason if rejected    |
| `transcription_started`, `transcription_finished`, `transcription_stopped`, `transcription_failed` | file id, model, device, error          |
| `model_download_started`, `model_download_finished`, `model_download_stopped`, `model_download_failed` | model, URL, checksum result, error     |
| `model_download_by_transcription`                                                                | model and URL of a model that a transcription is about to fetch |
| `model_already_complete`                                                                         | model; a click on "Download" fetched nothing |
| `transcript_deleted`                                                                             | file id, or `all` for **Delete All**   |
| `unhandled_exception`                                                                            | error, traceback                       |

### Personal data

The log holds file names and the file ids derived from them, and file names
often contain the name of the interviewee. The log keeps them after a
transcript is deleted, also with **Delete All**. To remove them, delete the log
files. Transcript text and the initial prompt are not logged. Error messages
and tracebacks can contain file paths.

### Retention

The file rotates at 1 MB. aTrain keeps `atrain.log` and up to four older files
(`atrain.log.1` to `atrain.log.4`) and deletes anything older, whatever its age.

Run one instance per user. Two running instances write to the same file and
rotation then fails from time to time. aTrain keeps running and the lines stay
intact, but events can get lost.
