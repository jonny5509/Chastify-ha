# Chastify for Home Assistant

A Home Assistant custom integration for the Chastify Developer API.

Connect Chastify to Home Assistant to monitor your current session, lock state, countdowns, and controls through a simple Config Flow setup.

## Features

- HACS-compatible custom integration
- Home Assistant Config Flow setup
- User-wide DEV API key authentication
- Session and lock sensors
- Local countdown information
- Refresh controls
- Freeze, unfreeze, unlock, emergency unlock, and archive controls
- Time adjustment services
- Custom lock logs
- Device commands
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
2. Search for **Chastify**.
3. Install the integration.
4. Restart Home Assistant.
5. Go to **Settings → Devices & services → Add Integration**.
6. Search for **Chastify** and complete setup.

If it is not listed, add this repository as a custom repository:

`https://github.com/jonny5509/Chastify-ha`

### Manual

1. Download or clone this repository.
2. Copy `custom_components/chastify` to your Home Assistant `config/custom_components/` directory.
3. Restart Home Assistant.
4. Add **Chastify** from **Settings → Devices & services**.

## Configuration

Setup is handled through the Home Assistant UI.

You will need your **Chastify user-wide DEV API key**. The key is validated before the integration is added.

If the key becomes invalid, Home Assistant can request reauthentication.

### API key security

Treat your API key like a password. Do not share it, commit it to Git, or include it in public screenshots, logs, or configuration files.

## Entities

### Sensors

- Wearer Username
- Keyholder Username
- Lock Title
- Lock Type
- Start Date
- End Date
- Time Locked
- Time Remaining
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

Entity availability depends on the current Chastify session and API response.

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

A built-in Lovelace card is included at:

`/chastify/chastify-card.js`

It can be used to build a Chastify-focused dashboard.

## API

The integration communicates with the Chastify user-wide DEV API.

Current functionality includes:

- Session information
- Lock actions
- Time adjustments
- Freeze and unfreeze
- Custom logs
- Device commands
- Hygienic unlock

Chastify remains responsible for authentication, permissions, and server-side restrictions.

## Troubleshooting

### Authentication fails

Check your DEV API key, confirm it is user-wide, and make sure Home Assistant can reach the Chastify API.

### Entities are unavailable

Some entities require an active Chastify session or lock.

### A service fails

Check the action, command, endpoint, and parameters against the supported Chastify API.

### Session is not updating

Use **Refresh** and check the Home Assistant logs if the API is unreachable.

## Development

The integration is located in:

`custom_components/chastify/`

Key files include:

- `api.py` — Chastify API client
- `config_flow.py` — setup and reauthentication
- `coordinator.py` — API polling
- `sensor.py` — sensors
- `binary_sensor.py` — binary sensors
- `button.py` — controls
- `services.yaml` — services
- `www/chastify-card.js` — dashboard card

GitHub Actions run Home Assistant Hassfest validation.

## Existing Installations

After updating:

1. Update through HACS or replace the integration files.
2. Restart Home Assistant.
3. Reauthenticate if requested.

## Repository

[GitHub repository](https://github.com/jonny5509/Chastify-ha)

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE).
