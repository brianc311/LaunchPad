"""Generate editable storage inventory Excel sheet (site, host, IP, model, serial, capacity)."""

from pathlib import Path

from launchpad.capacity_export import export_blank_inventory


def main() -> Path:
    output = Path(__file__).resolve().parents[1] / "Storage_Capacity_Report.xlsx"
    export_blank_inventory(output)
    return output


if __name__ == "__main__":
    path = main()
    print(f"Created {path}")
