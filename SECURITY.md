# Security Policy

## Supported status

This repository is currently a **Testing / Beta** project.

Security fixes are welcome and should be reported responsibly.

## Reporting a vulnerability

If you discover a security vulnerability, avoid posting exploit details, credentials, cookies, tokens, or other sensitive information in a public issue.

Use a private security reporting channel available through GitHub for this repository when possible. If private reporting is unavailable, open a minimal public issue without sensitive details and request a private contact method.

Please include:

- A concise description of the vulnerability.
- Affected component or file.
- Reproduction steps or a minimal proof of concept when safe.
- Potential impact.
- Any suggested mitigation.

## Secrets

Never commit:

- Telegram bot tokens
- API keys
- Passwords
- Session tokens
- Browser cookies
- Private keys
- Personal credentials
- Production configuration files containing secrets

The repository's `.gitignore` excludes `.env` and common cookie files, but local review is still required before every push.

## Security practices

Operators should:

- Keep dependencies updated.
- Protect the host running the bot.
- Use authorized cookies only.
- Restrict administrative Telegram IDs carefully.
- Keep download directories protected.
- Use sensible rate and concurrency limits.
- Monitor disk usage and logs.
- Avoid exposing private configuration files.

GitHub's repository security features, including secret scanning, push protection, Dependabot alerts, and code scanning, are recommended where available.
