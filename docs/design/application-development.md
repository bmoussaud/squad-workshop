# Application Development Standard

Python is the primary language for application development. Use `uv` where
applicable to manage the Python version and environment, project dependencies and
lockfile, and execution of application, test, and project-tool commands.

Use TOML for Python project and tool configuration, with `pyproject.toml` as the
canonical project configuration file. This standard does not require runtime
secrets or environment-specific deployment settings to be stored in TOML; use
environment variables, secret stores, and deployment-specific configuration when
those mechanisms are appropriate.