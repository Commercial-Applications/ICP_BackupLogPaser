# virtnbdbackup-logparser

A Python script to parse logs from `virtnbdbackup` and send the metrics to an InfluxDB v2 instance.

## Features

- Parses `virtnbdbackup` log files (full and incremental).
- Extracts metrics such as:
    - Backup duration and status.
    - Total data saved (GiB).
    - VM name and version.
    - Checkpoint information.
    - Error and warning counts.
- Sends data to InfluxDB v2 for monitoring and alerting.
- Supports dry-run mode for local verification.

## Prerequisites

- Python 3.12 or higher.
- [uv](https://github.com/astral-sh/uv) (recommended) or `pip`.

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/SeanSmith/virtnbdbackup-logparser.git
   cd virtnbdbackup-logparser
   ```

2. Install dependencies:
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

3. Configure environment variables:
   Create a `.env` file in the root directory (copy from `.env.example` if available):
   ```env
   INFLUX_URL=http://your-influxdb-url:8086
   INFLUX_TOKEN=your-influxdb-token
   INFLUX_ORG=your-org
   INFLUX_BUCKET=your-bucket
   LOG_DIR=/var/log/virtnbdbackup
   ```

## Usage

Run the script to parse the latest log and send it to InfluxDB:

```bash
python virtnbd-parser.py
```

### Options

- `--dry-run`: Parse the logs and print the InfluxDB line protocol to the console without sending it to the server.
- `--log-dir <path>`: Specify a custom directory to look for log files.

Example dry-run:

```bash
python virtnbd-parser.py --dry-run --log-dir ./tests/files/
```

## Project Structure

- `virtnbd-parser.py`: The main script logic.
- `pyproject.toml`: Project metadata and dependencies.
- `uv.lock`: Locked dependency versions.
- `tests/files/`: Sample log files for testing.

## License

[Specify License if applicable, e.g., MIT]
