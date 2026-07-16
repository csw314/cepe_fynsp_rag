"""Run the local ETL pipeline.

This is a placeholder entry point for the scaffold.
"""

from cepe_fynsp.config import load_settings


def main() -> None:
    settings = load_settings()
    print(f"Loaded settings for {settings.project.name}")
    print("Implement ETL orchestration here.")


if __name__ == "__main__":
    main()
