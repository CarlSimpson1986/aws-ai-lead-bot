from pathlib import Path
import os
import subprocess

SOURCE_DIR = Path("infrastructure")
OUTPUT_DIR = Path("build/infrastructure")

account_id = os.environ.get("AWS_ACCOUNT_ID")

if not account_id:
    result = subprocess.run(
        [
            "aws", "sts", "get-caller-identity",
            "--query", "Account",
            "--output", "text"
        ],
        capture_output=True,
        text=True,
        check=True
    )
    account_id = result.stdout.strip()

if not account_id.isdigit() or len(account_id) != 12:
    raise RuntimeError("Could not determine a valid 12-digit AWS account ID.")

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

rendered = 0

for source in SOURCE_DIR.glob("*.json"):
    text = source.read_text(encoding="utf-8")
    text = text.replace("${AWS_ACCOUNT_ID}", account_id)

    destination = OUTPUT_DIR / source.name
    destination.write_text(text, encoding="utf-8")
    rendered += 1

print(f"Rendered {rendered} infrastructure files to {OUTPUT_DIR}")
