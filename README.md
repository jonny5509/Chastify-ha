# Chastify for Home Assistant

[![Downloads](https://img.shields.io/github/downloads/jonny5509/Chastify-ha/total?label=downloads)](https://github.com/jonny5509/Chastify-ha/releases) [![Version](https://img.shields.io/github/v/release/jonny5509/Chastify-ha?display_name=tag&sort=semver)](https://github.com/jonny5509/Chastify-ha/releases/latest) [![HACS Compatible](https://img.shields.io/badge/HACS-Compatible-41BDF5.svg)](https://hacs.xyz/)


A Home Assistant custom integration for the **Chastify Developer API**.

Chastify brings session status, lock information, countdowns, supported lock actions, time adjustments, custom logs, and device commands into Home Assistant through a native Config Flow integration.

## ✨ Features

- 🧩 Home Assistant Config Flow setup
- 🔑 User-wide DEV API key authentication
- 🔒 Session and lock sensors
- 📅 Automatic read-only calendar entity for the active Chastify session
- ⏱️ Lock countdown information
- 🎛️ Refresh and lock-control buttons
- ❄️ Freeze and unfreeze support
- 🩹 Hygienic unlock support (where supported by the API)
- ➕➖ Time adjustment services
- 📝 Custom lock logs
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

[Open Chastify in HACS](https://my.home-assistant.io/redirect/hacs_repository/?owner=jonny5509&repository=Chastify-ha&category=integration).

If Chastify is not yet available in the default HACS catalogue, add it as a custom repository:

1. Open **HACS → Integrations**.
2. Open the three-dot menu and select **Custom repositories**.
3. Add `https://github.com/jonny5509/Chastify-ha` and choose **Integration** as the category.
4. Add the repository, find **Chastify**, and download it.
5. Restart Home Assistant.
6. Open **Settings → Devices & services → Add integration**.
7. Search for **Chastify** and complete setup.

After Chastify is accepted into the default HACS catalogue, steps 2–4 will no longer be necessary.

### Manual installation

1. Download or clone this repository.
2. Copy `custom_components/chastify` to your Home Assistant `config/custom_components/` directory.
3. Restart Home Assistant.
4. Open **Settings → Devices & services → Add integration**.
5. Search for **Chastify** and complete setup.

## ⚙️ Configuration

Configuration is performed through the Home Assistant UI.

You will need a **Chastify user-wide DEV API key**. If the key becomes invalid, Home Assistant can request reauthentication.

### 🔑 API key security

Treat your API key like a password.

- Never commit it to Git.
- Do not publish it in screenshots, logs, or support requests.
- Rotate the key if you believe it has been exposed.

## 📊 Entities

### Calendar

The integration provides a native Home Assistant **Session Calendar** entity. It exposes the current Chastify session as a calendar event, updates its expected end time as the remaining-time counter changes, and saves completed sessions in Home Assistant storage so they remain in calendar history across restarts. History is collected from the time the feature is installed; older sessions can only be added if Chastify makes them available. Updates are written in order so a slower storage write cannot overwrite newer history, and pending writes are awaited when the entity unloads. History is retained indefinitely unless you press the **Clear calendar history** button or remove Home Assistant integration storage. Clearing history preserves the currently active session. This is a Home Assistant calendar entity; it does not create events in Google Calendar, Outlook, or another external calendar.

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
- Clear calendar history (removes completed local calendar records while preserving the active session)
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
| `chastify.device_command` | Send a documented device command |

Use only actions and commands supported by the Chastify API and your account.

## 🖥️ Lovelace dashboard card

A bundled Lovelace card is available at:

`/chastify/chastify-card.js`

The card provides a convenient Home Assistant dashboard interface for Chastify session and lock information.

## 🌐 API

The integration communicates with the Chastify user-wide DEV API.

Supported functionality includes session information, lock actions, time adjustments, freeze/unfreeze, custom logs, device commands, and hygienic unlock.

Chastify remains responsible for authentication, permissions, validation, and server-side restrictions.

## 🧰 Troubleshooting

### Authentication fails

Verify your DEV API key and make sure Home Assistant can reach the Chastify API.

### Entities are unavailable

Some entities require an active Chastify session or lock.

### A service fails

Check that the action or command is supported by the Chastify API and permitted for the current account/session.

### Session data is not updating

Use the **Refresh** control and check the Home Assistant logs if the API is unreachable or returning errors.

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

GitHub Actions validate the integration with HACS and Home Assistant Hassfest and run the integration test suite. HACS validation also runs on a daily schedule and can be triggered manually from the Actions tab.

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
- [Latest release](https://github.com/jonny5509/Chastify-ha/releases/latest)
- [HACS publisher requirements](https://www.hacs.dev/docs/publish/start/)
- [Submit to the HACS default catalogue](https://www.hacs.dev/docs/publish/include/)

[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/jonny5509)
