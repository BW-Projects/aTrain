# Run aTrain as Linux Service

Install uv as root.

```bash
sudo -i
# install script from uv docs.
```

Clone or extract aTrain to `/opt/`.

```bash
sudo -i
cd /opt
git clone https://github.com/aTrainTranscription/aTrain.git
cd aTrain
uv sync --extra gui
logout
```

Create aTrain folder in `/srv`.

```bash
sudo -i
cd /srv
mkdir aTrain
logout
```

Place the following file as `aTrain.service` at `/etc/systemd/system`.

```ini
[Unit]
Description=Runs aTrain as a service
After=network.target
Wants=network-online.target

[Service]
Restart=always
Type=simple
ExecStart=/opt/aTrain/.venv/bin/aTrain start --no-native --no-show
Environment='ATRAIN_USER_DIR=/srv/aTrain'
Environment='WAKEPY_FAKE_SUCCESS=yes'
Environment='HF_TOKEN=<your-token>'

[Install]
WantedBy=multi-user.target
```

```bash
sudo nano /etc/systemd/system/aTrain.service
# paste
# CTRL + X, CTRL + Y, Enter
```

Append `--host` and `--port` in the 'ExecStart' line to configure those settings.

A Hugging Face token is required to successfully download the speaker detection model. If the download fails, remove the `/srv/aTrain/models/speaker-detection` folder, check the token, and if you have accepted the terms on Hugging Face, retry. After the first successful transcription with speaker detection, that environment variable can be removed.

Enable and run the service

```bash
sudo systemctl enable --now aTrain.service
```

Check if it works

```bash
# try to access in the browser

# check service status
sudo systemctl status aTrain.service

# see aTrain output
sudo journalctl -e -u aTrain.service
```

You can put this behind a reverse proxy, but prefix-path is currently not supported.

## Uninstalling

The service runs as root, and all users of the web interface share one data
folder.

| Location                              | Contents                                                     | Personal data      |
| ------------------------------------- | ------------------------------------------------------------ | ------------------ |
| `/etc/systemd/system/aTrain.service`  | unit file; may hold a Hugging Face token in clear text       | the token          |
| `/opt/aTrain/`                        | checkout and virtual environment                             | no                 |
| `/srv/aTrain/`                        | models, settings and the transcriptions of every user        | **yes**            |
| systemd journal (`journalctl -u aTrain.service`) | service output, can include names of processed files | file names   |
| `/root/.cache/`                       | uv and library caches; harmless                              | no                 |

```bash
sudo systemctl disable --now aTrain.service
sudo rm /etc/systemd/system/aTrain.service
sudo systemctl daemon-reload
sudo rm -rf /opt/aTrain          # the application
sudo rm -rf /srv/aTrain          # models, settings and ALL transcripts
```

Revoke the Hugging Face token on huggingface.co if it was created for this
machine. The journal follows the system's log retention settings; nothing in
it is needed after the service is gone.
