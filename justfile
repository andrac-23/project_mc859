set windows-shell := ["powershell.exe", "-NoLogo", "-Command"]

# Run main project
run:
    uv run python main.py

# Run the pipeline to get data and update the network
run_data_to_network_pipeline:
    uv run python ./data-and-network/main.py

# Clear all existing pipeline data and network
clear_data_to_network_pipeline:
    uv run python ./data-and-network/main.py --reset

# Check for linting errors
lint:
    uv run ruff check .

# Format project (includes import autosorting)
format:
    uv run ruff check --select I --fix . && ruff format .
