# Installation (end users)

aTrain is published as a packaged desktop app and can also be installed from
source with pip.

> Setting up aTrain for **development**? See
> [CONTRIBUTING.md](../CONTRIBUTING.md), which uses the
> [uv](https://docs.astral.sh/uv/) workflow. Building a **standalone
> executable** is also covered there.

## Packaged apps (recommended)

- **Windows:** [Microsoft Store](https://apps.microsoft.com/detail/9N15Q44SZNS2?mode=direct)
- **Linux:** [Flathub](https://flathub.org/apps/io.github.juergenfleiss.aTrain)
  (see also the [Linux installation guide](installation-linux.md) for a manual
  command-line setup)

Additional download types are listed on the
[university download page](https://business-analytics.uni-graz.at/de/forschung/atrain/download/).

Rolling aTrain out to managed machines? See
[Windows deployment](deployment-windows.md).

Removing aTrain again: see [Uninstalling aTrain](uninstall.md).

How release builds are signed: see the [Code signing policy](code-signing-policy.md). How to check a downloaded release: see [Verifying a release](verifying-releases.md).

## Install from source with pip

You need **Python ≥ 3.11**.

Set up and activate a virtual environment:

```bash
python -m venv venv
# Windows
.\venv\Scripts\activate
# macOS / Linux
source venv/bin/activate
```

Install aTrain with the GUI extras (needed for `aTrain start`, the desktop /
browser app):

```bash
pip install "aTrain[gui] @ git+https://github.com/aTrainTranscription/aTrain.git"
```

On **Windows**, prepend the PyTorch CUDA index so pip pulls the CUDA torch
wheel:

```bash
pip install "aTrain[gui] @ git+https://github.com/aTrainTranscription/aTrain.git" \
    --extra-index-url https://download.pytorch.org/whl/cu128
```

On **Linux** the PyPI torch wheel already bundles CUDA. **macOS** is CPU-only.
NVIDIA CUDA GPU support currently covers Windows and Debian-based Linux.

Download the models for transcription and speaker detection. This only has to be
done once:

```bash
aTrain init
```

Start aTrain:

```bash
aTrain start
```

### Uninstalling a pip installation

| Location                                                                 | Contents                                       | Removed by uninstall | Personal data |
| ------------------------------------------------------------------------ | ---------------------------------------------- | -------------------- | ------------- |
| the virtual environment you created (`venv`, `atrain_venv`, ...)         | aTrain and its dependencies, several GB        | when you delete it   | no            |
| `~/Documents/aTrain/models/`                                             | downloaded models, several GB                  | no                   | no            |
| `~/Documents/aTrain/transcriptions/`                                     | one folder per transcription: text, `metadata.txt`, `log.txt` | no    | **yes**       |
| `~/Documents/aTrain/settings/`                                           | the options last used in the app               | no                   | no            |
| `~/.cache/matplotlib/` and `~/.config/matplotlib/` (Linux), `~/.matplotlib/` (macOS), `%LOCALAPPDATA%\matplotlib\` (Windows) | font cache of a library aTrain loads; harmless | no | no |
| pip's download cache (`pip cache dir`)                                   | downloaded wheels, including torch             | no                   | no            |
| the system temp directory                                                | one folder per start in native mode; the OS cleans it | no             | no            |

`~/Documents/aTrain` moves to the path in `ATRAIN_USER_DIR` when that is set.

**Remove the application:** deactivate the environment and delete its folder.
That removes aTrain and everything installed with it. `pip uninstall aTrain`
only makes sense in an environment shared with other software. System packages
installed for the manual Linux setup (ffmpeg, build tools) are shared with
other software; leave them.

**Remove the user data.** This deletes all transcripts:

```bash
rm -rf ~/Documents/aTrain        # macOS, Linux
```

```powershell
Remove-Item -Recurse -Force "$env:USERPROFILE\Documents\aTrain"
```

## Command-line / headless usage

For headless transcription pipelines, aTrain also exposes a CLI (`aTrain_core
transcribe`). See the "Headless / CLI Usage" section in the
[README](../README.md#headless--cli-usage).
