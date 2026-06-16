import sys
from pathlib import Path


def main() -> None:
    secret = Path(sys.executable).with_name("ssh_askpass.secret")
    if not secret.exists():
        raise SystemExit(1)
    sys.stdout.write(secret.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
