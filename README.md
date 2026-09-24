# Chastify for Home Assistant

A Home Assistant custom integration for the Chastify Developer API.

The integration connects Home Assistant to Chastify using a user-wide DEV API token and exposes session/lock state, sensors, controls, and API-backed services.

## Features

- HACS-compatible Home Assistant custom integration
- Config Flow setup
- User-wide Chastify DEV API token authentication
- Cloud polling of the current Chastify session/lock
- Lock title and timing information
- Locked time and maximum remaining time
- Task points
- Frozen, ready-to-unlock, trusted, and task-assigned binary sensors
- Refresh control
- Add, remove, and apply time controls
- Freeze and unfreeze controls
- General Chastify action service
- Custom lock-log service
- Generic device-command service for documented Chastify device API commands

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
2. Copy the `custom_components/chastify` directory into your Home Assistant `config/custom_components/` directory.
3. Restart Home Assistant.
4. Add **Chastify** from **Settings → Devices & services**.

For HACS installations, HACS handles updates and keeps the integration in the expected custom-component location.

## Authentication

Chastify uses a user-wide DEV API key.

Create the key in Chastify under **Developer API → User-wide DEV API keys**. The token is shown once, so store it securely.

Treat the API key like a password:

- Do not commit it to Git.
- Do not put it in public configuration files.
- Do not share it in screenshots, logs, issues, or support requests.

The integration sends the token to the Chastify API when making authenticated requests.

## Services

The integration provides the following services:

| Service | Purpose |
| --- | --- |
| `chastify.action` | Send a general Chastify action |
| `chastify.apply_time` | Apply time through the lock API |
| `chastify.add_time` | Add time to the current lock |
| `chastify.remove_time` | Remove time from the current lock |
| `chastify.freeze` | Freeze the current lock |
| `chastify.unfreeze` | Unfreeze the current lock |
| `chastify.log_custom` | Create a custom lock log entry |
| `chastify.device_command` | Send a documented Chastify device command |

The `action` and `device_command` services are intentionally generic so API commands can be exposed without requiring a dedicated Home Assistant service for every Chastify API operation.

Only use commands and parameters supported by the Chastify API. Generic API access does not bypass Chastify's own permissions or server-side restrictions.

## API coverage

The integration uses the Chastify user-wide DEV token API:

`https://chastify.net/api/apps/v1/`

Current integration coverage includes:

- `GET /session`
- `POST /action`
- `POST /lock/apply-time`
- `POST /lock/freeze`
- `POST /lock/unfreeze`
- `POST /logs/custom`
- `POST /device-command`

API behaviour and permissions are controlled by Chastify. The Home Assistant integration does not provide a way to bypass Chastify's authentication, authorization, or server-side rules.

## Entities

The integration exposes session information through Home Assistant entities, including:

### Session and lock information

- Lock title
- Remaining time
- Locked time
- Maximum remaining time
- Task points

### Binary sensors

- Frozen
- Ready to unlock
- Trusted
- Task assigned

A refresh control is also provided to request an immediate update instead of waiting for the normal polling cycle.

Entity availability depends on the current Chastify session and the data returned by the API.

## Troubleshooting

### The integration cannot authenticate

Check that:

1. The DEV API key is correct.
2. The key is a user-wide key rather than a different API credential.
3. The token has not been revoked or replaced.
4. Home Assistant can reach the Chastify API.

### The integration installs but entities are unavailable

Check the Home Assistant logs and confirm that Chastify is returning a valid session response. Some entities depend on information that may only be present when a relevant Chastify session or lock exists.

### A generic API command fails

Verify the API endpoint, HTTP method, command name, and parameters against the documented Chastify API. Generic services intentionally pass through API functionality and cannot make an unsupported Chastify command valid.

## Development

The repository contains the Home Assistant custom integration under `custom_components/chastify/`.

GitHub Actions are included for HACS and Home Assistant Hassfest validation.

When developing changes:

1. Keep the integration domain as `chastify`.
2. Preserve Home Assistant Config Flow compatibility.
3. Avoid logging API tokens or other credentials.
4. Validate changes with the repository's GitHub Actions before release.

## Existing installations

If you are upgrading an existing installation, restart Home Assistant after updating the integration. HACS users can use the normal HACS update flow.

If an update changes configuration or entity behaviour, check **Settings → Devices & services → Chastify** and the Home Assistant logs after restarting.

## Repository

Source code and issue tracking are available in this repository:

`https://github.com/jonny5509/Chastify-ha`

## License

This project is licensed under the MIT License.
