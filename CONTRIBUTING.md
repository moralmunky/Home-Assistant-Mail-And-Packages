# Contribution Guidelines

Contributing to this project should be as easy and transparent as possible, whether it's:

- Reporting a bug
- Discussing the current state of the code
- Submitting a fix
- Proposing new features
- Adding support for a new carrier

## GitHub is used for everything

GitHub is used to host code, to track issues and feature requests, as well as accept pull requests.

Pull requests are the best way to propose changes to the codebase.

1. Fork the repo and create your branch from `dev`.
2. If you've changed something, update the documentation.
3. Make sure your code passes linting and tests.
4. Test your contribution.
5. Issue that pull request!

## Development Setup

```bash
# Install test dependencies
pip install -r requirements_test.txt

# Run all tests
tox

# Run tests directly
pytest --timeout=30 --cov=custom_components/mail_and_packages/

# Run linting
tox -e lint

# Format code
black custom_components/mail_and_packages/
isort custom_components/mail_and_packages/
```

## Code Style

- **Formatter:** [black](https://github.com/psf/black) with 88 character line length
- **Import sorting:** [isort](https://pycqa.github.io/isort/) with black-compatible profile
- **Linting:** flake8, pylint, pydocstyle
- **Type checking:** mypy (via `tox -e mypy`)

## PR Requirements

- PR titles must follow [Conventional Commits](https://www.conventionalcommits.org/) (e.g., `feat:`, `fix:`, `refactor:`, `docs:`)
- All tests must pass
- Code must pass linting checks
- Branch from `dev`, not `master`

## Privacy-First Principle

All code changes must adhere to the privacy-first principle:

- **All processing must be local by default** - no data may be sent to external services unless the user explicitly opts in
- Any new feature involving external communication must be **disabled by default**
- Clear privacy notices must be shown when configuring features that send data externally
- This is a non-negotiable requirement for every code change

## Adding a New Carrier

1. Add email matching rules to `SENSOR_DATA` in `const.py` (sender addresses, subject patterns, optional body patterns)
2. Add sensor entity descriptions to `SENSOR_TYPES` in `const.py`
3. Add the carrier prefix to the `SHIPPERS` list in `const.py`
4. Optionally add a universal tracking pattern to `UNIVERSAL_TRACKING_PATTERNS` in `const.py` (only if the pattern is distinctive enough to avoid false positives)
5. Add test email samples to `tests/test_emails/`
6. Add test cases to `tests/test_helpers.py`
7. Update the supported carriers table in `README.md`

## Any contributions you make will be under the MIT Software License

In short, when you submit code changes, your submissions are understood to be under the same [MIT License](http://choosealicense.com/licenses/mit/) that covers the project. Feel free to contact the maintainers if that's a concern.

## Report bugs using GitHub's [issues](../../issues)

GitHub issues are used to track public bugs.
Report a bug by [opening a new issue](../../issues/new/choose); it's that easy!

## Write bug reports with detail, background, and sample code

**Great Bug Reports** tend to have:

- A quick summary and/or background
- Steps to reproduce
  - Be specific!
  - Give sample code if you can.
- What you expected would happen
- What actually happens
- Relevant log output (with `custom_components.mail_and_packages` set to debug)
- Diagnostics download (Settings > Devices & Services > Mail and Packages > 3-dot menu > Download Diagnostics)
- Notes (possibly including why you think this might be happening, or stuff you tried that didn't work)

## License

By contributing, you agree that your contributions will be licensed under its MIT License.
