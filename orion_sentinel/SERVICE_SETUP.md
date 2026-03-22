# Orion Sentinel Auto-Start Service

This project includes a systemd installer script to start Orion Sentinel on boot.

## Install and enable at boot

Run from the repository root:

```bash
bash orion_sentinel/scripts/install_systemd_service.sh
```

The script will:

- Create `/etc/systemd/system/orion-sentinel.service`
- Enable it to run at boot
- Start it immediately

## Service management

Check status:

```bash
sudo systemctl status orion-sentinel.service
```

Restart service:

```bash
sudo systemctl restart orion-sentinel.service
```

Stop service:

```bash
sudo systemctl stop orion-sentinel.service
```

Tail logs:

```bash
sudo journalctl -u orion-sentinel.service -f
```

## Notes

- The service loads environment variables from `orion_sentinel/.env` when present.
- If `venv/bin/python` exists in the repo root, it is used automatically.
- Otherwise, the system `python3` is used.
