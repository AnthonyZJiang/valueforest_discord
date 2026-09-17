# systemd service

This directory contains a systemd unit that starts the Value Forest Discord bot
at boot and restarts it after failures.

## Configure

Before installing the unit, edit `value-forest-bot.service` and set:

- `User` to the Linux user that owns and runs the bot.
- `WorkingDirectory` to the bot repository's absolute path.
- `ExecStart` to the absolute path of `autostart.sh`.

The configured user must have access to the repository, its `.venv`, and any
credentials required by the bot. Because `autostart.sh` runs `git pull`, Git
authentication must also work non-interactively for that user.

## Install

From the repository root, run:

```bash
sudo cp systemd/value-forest-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now value-forest-bot.service
```

Do not also start the bot through cron, or two instances may run.

## Manage

Show the current status and logs

```bash
sudo systemctl status value-forest-bot.service
sudo journalctl -u value-forest-bot.service -f
```

Restart or stop the bot

```bash
sudo systemctl restart value-forest-bot.service
sudo systemctl stop value-forest-bot.service
```

## Troubleshooting

- `status=217/USER` means the account specified by `User=` does not exist.
  Check it with `id <username>`.
- A missing `.venv` means `WorkingDirectory` is incorrect or the virtual
  environment has not been created there.
- Git failures at startup usually mean the service user lacks repository
  permissions, SSH keys, or saved HTTPS credentials.
- Use `sudo journalctl -u value-forest-bot.service -n 100 --no-pager` to inspect
  recent startup errors.
