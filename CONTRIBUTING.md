# Contributing

Thank you for considering a contribution to Telegram Video Downloader.

## Before you start

- Read [TERMS.md](TERMS.md).
- Follow the project's lawful-use requirements.
- Do not submit secrets, cookies, tokens, passwords, or private data.
- Check existing issues and pull requests before starting duplicate work.

## Reporting bugs

When reporting a bug, include:

1. A clear description of the problem.
2. Steps to reproduce it.
3. Expected behavior.
4. Actual behavior.
5. Python version and operating system.
6. Relevant non-sensitive logs or error messages.
7. The affected command or feature.

Remove bot tokens, cookies, session data, personal information, and other secrets before posting logs.

## Feature requests

Describe:

- The problem or use case.
- The proposed behavior.
- Why the change fits the project's self-hosted Telegram bot architecture.
- Any compatibility or configuration impact.

## Pull requests

1. Fork the repository.
2. Create a focused feature or fix branch.
3. Make the smallest practical change.
4. Update documentation when behavior or configuration changes.
5. Run local syntax checks and tests available in your environment.
6. Review the diff for secrets and unrelated changes.
7. Open a pull request with a clear description.

## Code quality

Prefer:

- Small, readable functions.
- Clear names and comments where needed.
- Safe handling of user input.
- Explicit error handling.
- Configuration through environment variables rather than hard-coded secrets.
- Changes that preserve existing commands and documented behavior.

## Testing

At minimum, before submitting a Python change, run:

```bash
python -m py_compile bot.py
```

If you have a configured test environment, also verify the affected command or workflow manually.

Do not use real private credentials or unauthorized cookies during testing.

## Responsible disclosure

Do not publicly disclose an exploitable security issue before giving the maintainer a reasonable opportunity to address it. See [SECURITY.md](SECURITY.md).
