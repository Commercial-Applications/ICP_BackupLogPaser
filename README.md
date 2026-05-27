# virtnbdbackup-logparser

A Python script to parse logs from `virtnbdbackup` and send the metrics to an InfluxDB v2 instance.

## Features

- Parses `virtnbdbackup` log files (full and incremental).
- Extracts metrics such as:
  - Backup duration and status.
  - Backup week number (ISO) and year.
  - Total data saved (GiB).
  - VM name and version.
  - Checkpoint information.
  - Error and warning counts.
- Duplicate detection: Tracks processed log files to avoid duplicate entries in InfluxDB.
- Test suite: Includes unit and functional tests to ensure reliability.
- Sends data to InfluxDB v2 for monitoring and alerting.
- Supports dry-run mode for local verification.

## Prerequisites

- Python 3.12 or higher.
- [uv](https://github.com/astral-sh/uv) (recommended) or `pip`.

## Installation
1. For typical usage through crontab -e
    ```bash
   # To be able to configure virtual environments some systems may need..
   sudo apt update && sudo apt install -y python3.10-venv
   ```
    ```bash
   # Create a directory in /opt/virtnbdbackup-logparser 
   # In this directory create the venv
   sudo python3 -m venv venv
   ```
   ```bash
   # Upgrade PIP in vEnv and install dependencies 
   # In this directory create the venv
   sudo ./venv/bin/pip install --upgrade pip
   sudo ./venv/bin/pip install python-dotenv request
    ```
   Clone the repository:
   ```bash
   git clone https://github.com/Commercial-Applications/ICP_BackupLogPaser.git .
   ````
   
   Configure environment variables:
   Create a `.env` file in the root directory (copy from `.env.example` if available):
   ```env
   INFLUX_URL=http://your-influxdb-url:8086
   INFLUX_TOKEN=your-influxdb-token
   INFLUX_ORG=your-org
   INFLUX_BUCKET=your-bucket
   LOG_DIR=/var/log/virtnbdbackup
   ```
   Lock this directory down to admin as it contains .env secrets
   ```
   # Make the wrapper executable
   chmod +x /usr/local/sbin/my-utility
   
   # Restrict the project directory to root access only
   chmod -R 700 /opt/my-admin-tool
   chown -R root:root /opt/my-admin-tool
   ```
    Create a small wrapper script in /usr/local/sbin that calls this package
    ```aiignore
    #!/bin/bash
    # Move to the directory so Python naturally finds your .env file
    cd /opt/my-admin-tool
    
    # Run the script using the virtual environment's isolated python interpreter
    exec ./venv/bin/python main.py "$@"
    ```

### For Testing or other installations

1. Install dependencies:
   Using `uv`:
   ```bash
   uv sync
   ```
   Or using `pip`:
   ```bash
   pip install -r requirements.txt  # If requirements.txt is generated
   # or
   pip install requests python-dotenv
   ```

## Usage

Run the script to parse the latest log and send it to InfluxDB:

```bash
python virtnbd-parser.py
```

### Options

- `--dry-run`: Parse the logs and print the InfluxDB line protocol to the console without sending it to the server.
- `--log-dir <path>`: Specify a custom directory to look for log files.
- `--all-logs`: Process all log files in the log directory, not just the latest.
- `--force`: Process log files even if they have already been entered into InfluxDB.

Example dry-run:
```bash
python virtnbd_parser.py --dry-run --log-dir ./tests/files/
```

## Development

### Running Tests
To run the test suite:
```bash
# Using pytest directly (ensure dependencies are installed)
export PYTHONPATH="."
pytest tests/test_parser.py
```

## Project Structure

- `virtnbd_parser.py`: The main script logic.
- `pyproject.toml`: Project metadata and dependencies.
- `uv.lock`: Locked dependency versions.
- `tests/files/`: Sample log files for testing.

## License

[Specify License if applicable, e.g., MIT]
