import argparse
import os
import re
import socket
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# -----------------------------
# CONFIG
# -----------------------------

LOG_DIR = os.getenv("LOG_DIR", "/var/log/virtnbdbackup")

INFLUX_URL = os.getenv("INFLUX_URL")
INFLUX_BUCKET = os.getenv("INFLUX_BUCKET")
INFLUX_ORG = os.getenv("INFLUX_ORG")
INFLUX_TOKEN = os.getenv("INFLUX_TOKEN")

MEASUREMENT = "backup_run"
PROGRAM = "virtnbdbackup"


# -----------------------------
# HELPERS
# -----------------------------

def escape_tag(value):
  return str(value).replace(" ", r"\ ").replace(",", r"\,").replace("=", r"\=")


def escape_string(value):
  return str(value).replace("\\", "\\\\").replace('"', '\\"')


def parse_timestamp(line):
  match = re.match(r"\[(.*?)\]", line)
  if not match:
    return None

  return datetime.strptime(
    match.group(1),
    "%Y-%m-%d %H:%M:%S"
  ).replace(tzinfo=timezone.utc)


def get_all_logs(log_dir):
  logs = list(Path(log_dir).glob("backup.full*.log"))
  logs += list(Path(log_dir).glob("backup.inc*.log"))

  if not logs:
    raise FileNotFoundError(f"No backup.full*.log or backup.inc*.log files found in {log_dir}")

  return sorted(logs, key=lambda p: p.stat().st_mtime)


def get_latest_log(log_dir):
  logs = get_all_logs(log_dir)
  return logs[-1]


def backup_level_from_filename(log_file):
  name = log_file.name.lower()

  if name.startswith("backup.full"):
    return "full"

  if name.startswith("backup.inc"):
    return "incremental"

  return "unknown"


def vm_from_log(parsed, fallback="unknown"):
  if parsed.get("vm"):
    return parsed["vm"]

  if parsed.get("output_path"):
    return Path(parsed["output_path"]).name

  return fallback


# -----------------------------
# LOG PARSER
# -----------------------------

def parse_log(log_path):
  result = {
    "vm": "",
    "version": "",
    "backup_level": "unknown",
    "output_path": "",
    "attached_disks": 0,
    "concurrent_processes": 0,
    "error_count": 0,
    "warning_count": 0,
    "error_message": "",
    "checkpoint_error": "",
    "backup_start_failed": 0,
    "checkpoint_name": "",
    "parent_checkpoint": "",
    "total_saved_data_gib": 0.0,
    "start_time": None,
    "end_time": None,
    "duration_sec": 0,
  }

  with open(log_path, "r", errors="ignore") as file:
    for line in file:
      ts = parse_timestamp(line)

      if ts:
        if result["start_time"] is None:
          result["start_time"] = ts
        result["end_time"] = ts

      if "] ERROR " in line:
        result["error_count"] += 1
        clean_error = line.strip().split("]:", 1)[-1].strip()
        result["error_message"] = clean_error

        # Specific error classification
        if "bitmap" in line.lower():
          result["checkpoint_error"] = "bitmap issue"

        if "Cannot store dirty bitmaps in qcow2 v2 files" in line:
          result["checkpoint_error"] = (
            "qcow2 v2 bitmap persistence unsupported"
          )

        if "Failed to start backup" in line:
          result["backup_start_failed"] = 1

      if "] WARNING " in line or "] WARN " in line:
        result["warning_count"] += 1

      match = re.search(r"Version:\s+([\d.]+)", line)
      if match:
        result["version"] = match.group(1)

      match = re.search(r"Backup level:\s+\[(.*?)\]", line)
      if match:
        result["backup_level"] = match.group(1)

      match = re.search(r"Arguments:.*?-d\s+(\S+)", line)
      if match:
        result["vm"] = match.group(1)

      match = re.search(r"Arguments:.*?-o\s+(\S+)", line)
      if match:
        result["output_path"] = match.group(1)

      match = re.search(r"Backup will save \[(\d+)\] attached disks", line)
      if match:
        result["attached_disks"] = int(match.group(1))

      match = re.search(r"Concurrent backup processes:\s+\[(\d+)\]", line)
      if match:
        result["concurrent_processes"] = int(match.group(1))

      match = re.search(r"Using checkpoint name:\s+\[([^\]]+)\]", line)
      if match:
        result["checkpoint_name"] = match.group(1)

      match = re.search(r"Parent checkpoint name\s+\[([^\]]+)\]", line)
      if match:
        result["parent_checkpoint"] = match.group(1)

      match = re.search(r"Total saved disk data:\s+\[(\d+(?:\.\d+)?)GiB\]", line)
      if match:
        result["total_saved_data_gib"] = float(match.group(1))

  if result["start_time"] and result["end_time"]:
    result["duration_sec"] = int(
      (result["end_time"] - result["start_time"]).total_seconds()
    )

  return result


# -----------------------------
# STATUS LOGIC
# -----------------------------

def determine_status(exit_code, error_count, warning_count):
  if exit_code != 0:
    return "failed", 2

  if error_count > 0:
    return "failed", 2

  if warning_count > 0:
    return "warning", 1

  return "success", 0


# -----------------------------
# INFLUX WRITE
# -----------------------------

def build_line_protocol(host, vm, log_file, exit_code, parsed):
  status, status_code = determine_status(
    exit_code,
    parsed["error_count"],
    parsed["warning_count"],
  )

  timestamp = parsed["end_time"] or datetime.now(timezone.utc)
  timestamp_ns = int(timestamp.timestamp() * 1_000_000_000)
  week_number = timestamp.isocalendar().week

  tags = {
    "host": host,
    "vm": vm,
    "backup_level": parsed["backup_level"],
    "program": PROGRAM,
  }

  fields = {
    "status": status,
    "status_code": f"{status_code}i",
    "exit_code": f"{exit_code}i",
    "error_count": f'{parsed["error_count"]}i',
    "warning_count": f'{parsed["warning_count"]}i',
    "duration_sec": f'{parsed["duration_sec"]}i',
    "attached_disks": f'{parsed["attached_disks"]}i',
    "concurrent_processes": f'{parsed["concurrent_processes"]}i',
    "week_number": f"{week_number}i",
    "version": parsed["version"],
    "output_path": parsed["output_path"],
    "log_file": log_file.name,
    "error_message": parsed["error_message"],
    "checkpoint_error": parsed["checkpoint_error"],
    "backup_start_failed": f'{parsed["backup_start_failed"]}i',
    "checkpoint_name": parsed["checkpoint_name"],
    "parent_checkpoint": parsed["parent_checkpoint"],
    "total_saved_data_gib": parsed["total_saved_data_gib"],
    "start_time": f'{int(parsed["start_time"].timestamp())}i' if parsed["start_time"] else "0i",
    "end_time": f'{int(parsed["end_time"].timestamp())}i' if parsed["end_time"] else "0i",
  }

  tag_text = ",".join(
    f"{escape_tag(k)}={escape_tag(v)}"
    for k, v in tags.items()
  )

  field_parts = []

  for key, value in fields.items():
    if isinstance(value, str) and not value.endswith("i"):
      field_parts.append(f'{key}="{escape_string(value)}"')
    else:
      field_parts.append(f"{key}={value}")

  field_text = ",".join(field_parts)

  return f"{MEASUREMENT},{tag_text} {field_text} {timestamp_ns}"


def write_to_influx(line):
  url = (
    f"{INFLUX_URL}"
    f"?org={INFLUX_ORG}"
    f"&bucket={INFLUX_BUCKET}"
    f"&precision=ns"
  )

  headers = {
    "Authorization": f"Token {INFLUX_TOKEN}",
    "Content-Type": "text/plain",
  }

  response = requests.post(url, headers=headers, data=line, timeout=10)
  response.raise_for_status()


# -----------------------------
# MAIN
# -----------------------------

def main():
  parser = argparse.ArgumentParser(
    description="Parse latest virtnbdbackup log and write backup status to InfluxDB."
  )

  parser.add_argument("--log-dir", default=LOG_DIR)
  parser.add_argument("--host", default=socket.gethostname())
  parser.add_argument("--exit-code", type=int, default=0)
  parser.add_argument("--dry-run", action="store_true")
  parser.add_argument(
    "--all-logs",
    action="store_true",
    help="Process all log files in log-dir, not just the latest.",
  )

  args = parser.parse_args()

  log_files = get_all_logs(args.log_dir) if args.all_logs else [get_latest_log(args.log_dir)]

  for log_file in log_files:
    parsed = parse_log(log_file)

    # Prefer filename for backup type
    parsed["backup_level"] = backup_level_from_filename(log_file)

    vm = vm_from_log(parsed)

    line = build_line_protocol(
      host=args.host,
      vm=vm,
      log_file=log_file,
      exit_code=args.exit_code,
      parsed=parsed,
    )

    if args.dry_run:
      print(line)
    else:
      write_to_influx(line)
      print(f"Wrote backup status to InfluxDB for VM: {vm}, log: {log_file.name}")


if __name__ == "__main__":
  main()
