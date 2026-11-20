import logging
import sys

from broadcast_controller.config import load_config, get_state_directory
from broadcast_controller.testing.harness import ActiveTestHarness


def main():
    try:
        config = load_config()
        state_directory = get_state_directory(config)

        harness = ActiveTestHarness(
            config=config,
            state_directory=state_directory,
        )

        harness.run()

        return 0

    except KeyboardInterrupt:
        print("\nTest harness interrupted.")
        return 130

    except Exception as error:
        logging.exception("Active test harness failed.")
        print(f"\nUnable to run active test harness: {error}")
        return 1


if __name__ == "__main__":
    sys.exit(main())