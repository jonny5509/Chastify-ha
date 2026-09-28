# Chastify for Home Assistant

A Home Assistant custom integration for the Chastify Developer API.

Monitor your current Chastify session, lock state, countdowns, and controls from Home Assistant.

## Features

- HACS-compatible custom integration
- Home Assistant Config Flow setup
- User-wide DEV API key authentication
- Session and lock sensors
- Refresh controls
- Freeze, unfreeze, unlock, emergency unlock, and archive
- Time adjustment services
- Custom lock logs and device commands
- Built-in Lovelace dashboard card

## Requirements

- Home Assistant
- A Chastify account
- A Chastify user-wide DEV API key
- Network access to the Chastify API
- [HACS](https://hacs.xyz/) — recommended

## Installation

### HACS

1. Open **HACS → Integrations**.
2. Search for **Chastify** and install it.
3. Restart Home Assistant.
4. Go to **Settings → Devices & services → Add Integration**.
5. Search for **Chastify** and complete setup.

If it is not listed, add `https://github.com/jonny5509/Chastify-ha` as a custom repository.

### Manual

Copy `custom_components/chastify` into `config/custom_components/`, restart Home Assistant, then add **Chastify** from **Settings → Devices & services**.

## Configuration

Setup is handled through the Home Assistant UI.

You will need your **Chastify user-wide DEV API key**. If the key becomes invalid, Home Assistant can request reauthentication.

### API key security

Treat your API key like a password. Do not share it, commit it to Git, or include it in public screenshots, logs, or configuration files.

## Entities

### Sensors

- Wearer Username
- Keyholder Username
- Lock Title
- Lock Type
- Start Date / End Date
- Time Locked / Time Remaining
- Session Role
- Task Points
- Task Points Required
- Task Points Remaining

### Binary sensors

- Frozen
- Locked
- Ready to unlock
- Task Assigned

### Buttons

- Refresh
- Refresh history
- Unlock
- Emergency unlock
- Archive
- Freeze
- Unfreeze

## Services

| Service | Purpose |
| --- | --- |
| `chastify.action` | Send a supported Chastify action |
| `chastify.apply_time` | Add or remove lock time |
| `chastify.add_time` | Add lock time |
| `chastify.remove_time` | Remove lock time |
| `chastify.freeze` | Freeze the active lock |
| `chastify.unfreeze` | Unfreeze the active lock |
| `chastify.hygienic_unlock` | Request a hygienic unlock |
| `chastify.log_custom` | Create a custom lock log |
| `chastify.device_command` | Send a documented device command |

Use only actions and commands supported by Chastify.

## Dashboard Card

A built-in Lovelace card is available at `/chastify/chastify-card.js`.

## API

The integration communicates with the Chastify user-wide DEV API.

Supported functionality includes session information, lock actions, time adjustments, freeze/unfreeze, custom logs, device commands, and hygienic unlock.

Chastify remains responsible for authentication, permissions, and server-side restrictions.

## Troubleshooting

### Authentication fails

Check your DEV API key and make sure Home Assistant can reach the Chastify API.

### Entities are unavailable

Some entities require an active Chastify session or lock.

### A service fails

Check the action or command against the supported Chastify API.

### Session is not updating

Use **Refresh** and check the Home Assistant logs if the API is unreachable.

## Development

The integration is located in `custom_components/chastify/`.

Key files include `api.py`, `config_flow.py`, `coordinator.py`, `sensor.py`, `binary_sensor.py`, `button.py`, `services.yaml`, and `www/chastify-card.js`.

GitHub Actions run Home Assistant Hassfest validation.

## Existing Installations

Update through HACS or replace the integration files, then restart Home Assistant. Reauthenticate if requested.

## Repository

[GitHub repository](https://github.com/jonny5509/Chastify-ha)

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE).
