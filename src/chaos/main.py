"""CHAOS entry point (Milestone 0 — Foundation).

``main`` loads configuration, builds the application context and runs
the runtime skeleton to a clean exit. CI-safe: development defaults
need no API key. Configuration failures exit 2 with the reason on
stderr (values — especially secrets — are never echoed).
"""

import sys

import chaos
from chaos.cau_hinh.settings import ChaosSettings
from chaos.ha_tang.application import create_application
from chaos.ha_tang.contracts.errors import ConfigurationError


def main() -> int:
    """Bootstrap CHAOS. Returns the process exit code."""
    try:
        settings = ChaosSettings.from_env()
    except ConfigurationError as exc:
        print(f"CHAOS configuration error: {exc}", file=sys.stderr)
        return 2
    print(f"CHAOS {chaos.__version__} — environment={settings.app.environment} (Milestone 0)")
    return create_application(settings).run()


if __name__ == "__main__":
    raise SystemExit(main())
