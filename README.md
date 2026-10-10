# Chastify for Home Assistant

[![Version](https://img.shields.io/github/v/release/jonny5509/Chastify-ha?display_name=tag&sort=semver)](https://github.com/jonny5509/Chastify-ha/releases/latest)
[![HACS](https://img.shields.io/badge/HACS-Custom%20Integration-41BDF5.svg)](https://hacs.xyz/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

A Home Assistant custom integration for the **Chastify Developer API**.

Chastify brings session status, lock information, countdowns, supported lock actions, time adjustments, custom logs, and device commands into Home Assistant through a native Config Flow integration.

## ✨ Features

- 🧩 Home Assistant Config Flow setup
- 🔑 User-wide DEV API key authentication
- 🔒 Session and lock sensors
- ⏱️ Lock countdown information
- 🎛️ Refresh and supported lock-control buttons
- ❄️ Freeze and unfreeze support
- 🩹 Hygienic unlock (where permitted by Chastify)
- ➕➖ Time adjustment services
- 📝 Custom lock logs
- 🔔 Custom Chastify notifications
- 🩺 API health sensors and session-change events
- 🎯 Optional explicit lock ID for multi-lock accounts
- 📱 Supported device commands
- 🖥️ Built-in Lovelace dashboard card
- 📦 HACS-compatible installation

## 📋 Requirements

- Home Assistant with support for custom integrations
- A Chastify account
- A Chastify user-wide DEV API key
- Network access to the Chastify API
- [HACS](https://hacs.xyz/) — recommended

## 🚀 Installation

### HACS

1. Open **HACS → Integrations**.
2. Search for **Chastify** and select **Download**.
3. Restart Home Assistant.
4. Open **Settings → Devices & services**.
5. Select **Add Integration**.
6. Search for **Chastify** and complete setup.

If it is not yet listed in HACS, add this repository as a custom repository:

`https://github.com/jonny5509/Chastify-ha`

### Manual installation

1. Download or clone this repository.
2. Copy `custom_components/chastify` to your Home Assistant `config/custom_components/` directory.
3. Restart Home Assistant.
4. Open **Settings → Devices & services → Add Integration**.
5. Search for **Chastify** and complete setup.

## ⚙️ Configuration

Configuration is performed through the Home Assistant UI.

You will need a **Chastify user-wide DEV API key**. If the key becomes invalid, Home Assistant can request reauthentication. If your account has multiple active locks, enter the exact 24-character lock ID to pin requests to one lock; leave it blank to use Chastify's automatic selection.

### 🔑 API key security

Treat your API key like a password.

- Never commit it to Git.
- Do not publish it in screenshots, logs, or support requests.
- Rotate the key if you believe it has been exposed.

## 📊 Entities

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
- Last successful update
- Last API error

### Binary sensors

- Frozen
- Locked
- Ready to unlock
- Task Assigned

### Buttons

- Refresh
- Hygienic unlock
- Add 1 day / Add 1 hour
- Subtract 1 day / Subtract 1 hour
- Freeze
- Unfreeze

## 🛠️ Services

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
| `chastify.notification` | Request a custom notification for wearer, keyholder, or both |
| `chastify.device_command` | Send a documented device command |

Use only actions and commands supported by the Chastify API and your account.

## 🖥️ Lovelace dashboard card

A bundled Lovelace card is available at:

`/chastify/chastify-card.js`

The card provides a responsive Home Assistant dashboard interface for Chastify session and lock information. The integration does not expose a historical-session endpoint, so it does not advertise a separate history-refresh button.

## 🌐 API

The integration communicates with the Chastify user-wide DEV API.

Supported functionality includes session information, lock actions, time adjustments, freeze/unfreeze, custom logs and notifications, device commands, and hygienic unlock. API reads retry limited 429 responses with backoff; mutation requests are not blindly retried. Custom notification acceptance does not guarantee delivery or that a recipient read it.

Chastify remains responsible for authentication, permissions, validation, and server-side restrictions.

## 🧰 Troubleshooting

### Authentication fails

Verify your DEV API key and make sure Home Assistant can reach the Chastify API.

### Entities are unavailable

Some entities require an active Chastify session or lock.

### A service fails

Check that the action or command is supported by the Chastify API and permitted for the current account/session.

### Session data is not updating

Use the **Refresh** control and check the **Last API error** and **Last successful update** sensors. The integration also emits `chastify_session_started`, `chastify_session_ended`, and `chastify_session_state_changed` Home Assistant events for automations.

## 👩‍💻 Development

Integration source code is located in `custom_components/chastify/`.

Important components include:

- `api.py`
- `config_flow.py`
- `coordinator.py`
- `sensor.py`
- `binary_sensor.py`
- `button.py`
- `services.yaml`
- `www/chastify-card.js`

GitHub Actions run Home Assistant Hassfest validation.

## 🔄 Updating

For HACS installations:

1. Update **Chastify** from HACS.
2. Restart Home Assistant.
3. Reload the dashboard if the card does not immediately reflect the update.
4. Reauthenticate if Home Assistant requests it.

## 📄 License

This project is licensed under the [MIT License](LICENSE).

## 🔗 Links

- [Repository](https://github.com/jonny5509/Chastify-ha)
- [Issues](https://github.com/jonny5509/Chastify-ha/issues)

[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/jonny5509)
