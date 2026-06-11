### Stack notes

- Python scripts, APIs, or data/analysis pipelines
- Use a virtualenv (`venv` / `.venv`) — do not install packages globally

### Project-specific rules

- Pin dependencies in `requirements.txt` or `pyproject.toml`
- Prefer `python -m` for package execution when a module layout exists
- Long-running jobs should support `--dry-run` when side effects are possible
