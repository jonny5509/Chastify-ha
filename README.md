# Chastify for Home Assistant

A Home Assistant custom integration for the Chastify Developer API.

Chastify connects Home Assistant to your Chastify account using a user-wide DEV API key. It provides session information, lock state, controls, and API-backed services, with a Config Flow for setup.

## Features

- HACS-compatible custom integration
- Home Assistant Config Flow setup
- User-wide Chastify DEV API key authentication
- Cloud polling of the current Chastify session
- Automatic handling of API authentication and transient connection failures
- Session and lock information exposed as Home Assistant entities
- Refresh controls for the session and history
- Lock controls including freeze, unfreeze, unlock, emergency unlock, and archive
- Generic Chastify action service
- Time adjustment services
- Custom lock-log service
- Documented device-command service
- Built-in Chastify dashboard card JavaScript
- Home Assistant Hassfest validation through GitHub Actions

## Requirements

- Home Assistant with support for custom integrations
- A Chastify account
- A Chastify user-wide DEV API key
- Network access from Home Assistant to the Chastify API

## Installation

### HACS

1. Open **HACS → Integrations** in Home Assistant.
2. Add this repository as a custom repository if it is not already available:
   `https://github.com/jonny5509/Chastify-ha`
3. Select **Chastify** and install it.
4. Restart Home Assistant.
5. Go to **Settings → Devices & services → Add Integration**.
6. Search for **Chastify** and complete the setup flow.

### Manual

1. Download or clone this repository.
2. Copy `custom_components/chastify` into your Home Assistant `config/custom_components/` directory.
3. Restart Home Assistant.
4. Add **Chastify** from **Settings → Devices & services**.

## Configuration

The integration is configured entirely through the Home Assistant UI.

When adding Chastify, enter your **user-wide DEV API key**. The integration validates the key against the Chastify API before creating the config entry.

If the key later becomes invalid, Home Assistant can request reauthentication so the token can be replaced without recreating the integration.

### API key security

Treat your Chastify API key like a password:

- Do not commit it to Git.
- Do not put it in public configuration files.
- Do not share it in screenshots, logs, issues, or support requests.
- Keep backups and exported configuration containing the token secure.

The integration sends the token to the Chastify API only when making authenticated requests.

## Entities

Chastify creates a **Session** device and exposes the current session through sensors, binary sensors, and buttons.

### Sensors

The integration currently provides:

- **Wearer Username**
- **Keyholder Username**
- **Lock Title**
- **Lock Type**
- **Start Date**
- **End Date**
- **Timer Visible**
- **Time Locked**
- **Time Remaining**
- **Session Role**
- **Task Points**
- **Task Points Required**
- **Task Points Remaining**

Some values are derived when the API response does not provide a dedicated field. For example, start and end times can be calculated from the authoritative lock-duration and remaining-time values.

### Binary sensors

- **Frozen**
- **Locked**
- **Ready to unlock**
- **Task Assigned**

### Buttons

- **Refresh**
- **Refresh history**
- **Unlock**
- **Emergency unlock**
- **Archive**
- **Freeze**
- **Unfreeze**

The Freeze button uses a one-hour freeze duration. For a custom duration, use the `chastify.freeze` service instead.

Entity availability depends on the current Chastify session and the information returned by the API.

## Services

The integration provides these services:

| Service | Purpose |
| --- | --- |
| `chastify.action` | Send a supported Chastify general action |
| `chastify.apply_time` | Add or remove seconds from the active lock |
| `chastify.add_time` | Add time to the active lock |
| `chastify.remove_time` | Remove time from the active lock |
| `chastify.freeze` | Freeze the active lock, optionally for a specified duration |
| `chastify.unfreeze` | Unfreeze the active lock |
| `chastify.hygienic_unlock` | Request a hygienic unlock |
| `chastify.log_custom` | Create a custom lock-log entry |
| `chastify.device_command` | Send a documented Chastify device command |

### Generic action

`chastify.action` accepts an action name and optional parameters.

Use only actions supported by the Chastify API. The integration does not bypass Chastify permissions or server-side restrictions.

### Time controls

- `chastify.apply_time` accepts positive or negative seconds.
- `chastify.add_time` accepts positive seconds.
- `chastify.remove_time` accepts positive seconds and sends the corresponding negative adjustment.
- `chastify.freeze` accepts an optional duration between 60 and 86,400 seconds.

### Custom logs

`chastify.log_custom` supports:

- Title
- Description
- Role: `extension`, `wearer`, or `keyholder`
- Icon
- Color

### Device commands

`chastify.device_command` accepts a documented Chastify device command and optional parameters.

Only use commands and parameters supported by Chastify. Generic API access does not bypass authentication, authorization, or server-side restrictions.

## API

The integration communicates with the Chastify user-wide DEV token API:

`https://chastify.net/api/apps/v1/`

Current API operations used by the integration include:

- `GET /session`
- General action requests
- `POST /lock/apply-time`
- `POST /lock/freeze`
- `POST /lock/unfreeze`
- `POST /logs/custom`
- Device-command requests
- Hygienic unlock requests

Exact API behaviour and permissions are controlled by Chastify.

## Dashboard card

The integration includes a JavaScript dashboard card at:

`/chastify/chastify-card.js`

Home Assistant registers the card automatically when the integration is loaded. The card can be used as a frontend resource for a Chastify-focused dashboard.

## Troubleshooting

### The integration cannot authenticate

Check that:

1. The DEV API key is correct.
2. The key is a user-wide DEV API key.
3. The token has not been revoked or replaced.
4. Home Assistant can reach the Chastify API.

If the existing token becomes invalid, use the reauthentication prompt provided by Home Assistant.

### The integration installs but entities are unavailable

Check the Home Assistant logs and confirm that Chastify is returning a valid session response.

Some entities depend on information that is only available when a relevant Chastify session or lock exists.

### A generic API command fails

Verify the command, HTTP method, endpoint, and parameters against the documented Chastify API. Generic services intentionally expose API functionality without creating a separate Home Assistant service for every possible Chastify operation.

### The session is not updating

The integration uses cloud polling through a Home Assistant data coordinator. Use the **Refresh** button to request an immediate update and check the Home Assistant logs if the API is unreachable.

## Development

The Home Assistant integration lives under:

`custom_components/chastify/`

Important components include:

- `manifest.json` — Home Assistant integration metadata
- `config_flow.py` — UI setup and reauthentication
- `api.py` — Chastify API client
- `coordinator.py` — polling and shared API state
- `sensor.py` — session sensors
- `binary_sensor.py` — lock/session binary sensors
- `button.py` — session controls
- `services.yaml` — service descriptions and UI selectors
- `www/chastify-card.js` — dashboard card

GitHub Actions run Home Assistant Hassfest validation.

When developing changes:

1. Keep the integration domain as `chastify`.
2. Preserve Config Flow compatibility.
3. Do not log API tokens or other credentials.
4. Keep `manifest.json` keys ordered as required by Hassfest.
5. Validate changes with GitHub Actions before release.

## Existing installations

After updating the integration, restart Home Assistant so the new code and frontend card are loaded.

If you use HACS, use the normal HACS update flow and then restart Home Assistant.

The integration includes migration logic for older config entries and removes several obsolete entity-registry entries when upgrading.

## Repository

Source code, releases, and issue tracking:

`https://github.com/jonny5509/Chastify-ha`

## License

This project is licensed under the MIT License.
