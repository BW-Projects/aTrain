# Operations

For administrators who run aTrain and need to know what it records.

## Event log

aTrain writes security-relevant events to a log in each user's profile. Nothing
sends this log anywhere. This is not a debug log. Each transcription keeps its own
`log.txt` with its steps. A debug mode is planned in
[#121](https://github.com/aTrainTranscription/aTrain/issues/121).

| Install             | File                                                                                  |
| ------------------- | ------------------------------------------------------------------------------------- |
| Windows (MSIX)      | `%LOCALAPPDATA%\Packages\<PackageFamilyName>\LocalCache\Local\aTrain\Logs\atrain.log` |
| Windows from source | `%LOCALAPPDATA%\aTrain\Logs\atrain.log`                                               |
| Linux (Flatpak)     | `~/.var/app/io.github.juergenfleiss.aTrain/.local/state/aTrain/log/atrain.log`        |
| Linux from source   | `~/.local/state/aTrain/log/atrain.log`                                                |
| macOS               | `~/Library/Logs/aTrain/atrain.log`                                                    |

Windows redirects what the MSIX writes under `%LOCALAPPDATA%` into the package
folder, so the file does not appear at the plain path. Uninstalling the MSIX
deletes the log with that folder. Microsoft
[documents one exception](https://learn.microsoft.com/en-us/windows/msix/desktop/desktop-to-uwp-behind-the-scenes):
a file that already exists under AppData, for example from a run from source, is
written in place and stays after uninstalling.

`aTrain start` and `aTrain init` write this log. The `aTrain_core` command line
does not.

### Format

One line per event: time with UTC offset, level, event name, then `key=value`
fields. Unhandled exceptions add an indented traceback below their line.

```
2026-11-12 10:03:10+0100 INFO server_started version='1.5.0' native=True host='127.0.0.1' port=None allow_any_host=False
2026-11-12 10:04:16+0100 INFO file_accepted file_id='2611121004' extension='.mp3' size=29106
2026-11-12 10:04:16+0100 INFO transcription_started file_id='2611121004' model='tiny' device='cpu'
2026-11-12 10:04:27+0100 INFO transcription_finished file_id='2611121004'
2026-11-12 10:04:30+0100 INFO transcript_deleted file_id='2611121004'
2026-11-12 10:04:35+0100 INFO server_stopped
```

### Events

| Event                             | Fields and meaning                                                                         |
| --------------------------------- | ------------------------------------------------------------------------------------------ |
| `server_started`                  | version, native, host, port, allow_any_host; `port=None` means 8080 in browser mode and a free port in the native window |
| `server_stopped`                  |                                                                                            |
| `server_failed`                   | exit code; the server did not start, for example because the port is taken                 |
| `file_accepted`                   | file id, extension, size                                                                   |
| `file_rejected`                   | extension, size, reason                                                                    |
| `transcription_started`           | file id, model, device; logged when the file goes to the worker process                    |
| `transcription_finished`          | file id                                                                                    |
| `transcription_stopped`           | file id                                                                                    |
| `transcription_failed`            | file id, error                                                                             |
| `model_download_started`          | model, URL; a download from the Models page or by `aTrain init`                            |
| `model_download_finished`         | model, `checksum='ok'`                                                                     |
| `model_download_stopped`          | model                                                                                      |
| `model_download_failed`           | model, error, `checksum='failed'` if the files did not match their checksums               |
| `model_download_by_transcription` | model, URL; a model is missing and the transcription that follows will fetch it            |
| `model_download_incomplete`       | model, `checksum='failed'` if the files did not match their checksums                      |
| `transcript_deleted`              | file id, or `all` for **Delete All**                                                       |
| `unhandled_exception`             | error, traceback                                                                           |

The file id in the log is the timestamp part of the transcription's id:
`2611121004` for the folder `2611121004-Intervi`. Transcriptions started in the
same minute share it. A folder that aTrain did not name is logged as `other`.

If the worker never runs, for example after a stop during the upload,
`transcription_stopped` follows `transcription_started`. aTrain removes the
folder of a stopped transcription, so `transcript_deleted` follows as well.
`transcription_stopped` and `model_download_stopped` also stand for a worker
process that died, for example for lack of memory. aTrain cannot tell that from
the stop button.

After `model_download_by_transcription`, aTrain logs one end event for the model
when the transcription is over: `model_download_finished` if the model is
complete, `model_download_incomplete` if it is not. aTrain cannot see whether the
download began. The `transcription_` event next to it says how the run ended.

### Personal data

The events hold no file names. The file id is logged without the part that comes
from the file name. In error messages the name and the path of the recording are
replaced by `<file>`. Tracebacks of unhandled exceptions can still contain file
paths. To remove them, delete the log files. Transcript text and the initial
prompt are not logged.

### Retention

The file rotates at 1 MB. aTrain keeps `atrain.log` and up to four older files
(`atrain.log.1` to `atrain.log.4`) and deletes anything older. There is no limit
by age.

Run one instance per user. Do not run `aTrain init` while the app is open. Two
running instances write to the same file. On Windows the rotation then fails
while the other instance holds the file open. Once the file is full, new events
are lost until one instance ends. aTrain keeps running and the lines stay intact.
