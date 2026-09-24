# Chastify for Home Assistant

Home Assistant custom integration for the Chastify Developer API.

## Features

- HACS-compatible Home Assistant custom integration
- Config Flow using a user-wide Chastify DEV API token
- Session/lock state polling
- Lock title, remaining time, locked time, maximum remaining time and task points
- Frozen, Ready to unlock, trusted and task-assigned binary sensors
- Refresh button
- Time, freeze and unfreeze services
- General Chastify action service
- Custom lock-log service
- Generic device-command service for the documented Chastify device API

## Installation

Add this repository as a custom repository in HACS under **Integrations**:

https://github.com/jonny5509/Chastify

Then install **Chastify**, restart Home Assistant, and add **Chastify** from **Settings → Devices & services**.

## Token

Create a user-wide DEV API key in Chastify under **Developer API → User-wide DEV API keys**. The token is shown once. Treat it like a password.

## Services

- `chastify.action`
- `chastify.apply_time`
- `chastify.add_time`
- `chastify.remove_time`
- `chastify.freeze`
- `chastify.unfreeze`
- `chastify.log_custom`
- `chastify.device_command`

The generic action and device-command services intentionally mirror the documented API so new Chastify API commands can be used without waiting for a new integration release. Use device commands only when you understand the command and its parameters.

## API coverage

The integration uses the user-wide DEV token API at:

https://chastify.net/api/apps/v1/

Covered endpoints include:

- `GET /session`
- `POST /action`
- `POST /lock/apply-time`
- `POST /lock/freeze`
- `POST /lock/unfreeze`
- `POST /logs/custom`
- `POST /device-command`

## Development

The repository includes HACS and Home Assistant Hassfest GitHub Actions.

## License

MIT
