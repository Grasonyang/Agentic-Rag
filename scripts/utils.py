import logging
import sys

class ScriptRunner:
    """A simple utility to run scripts with consistent logging."""

    def __init__(self, description: str, main_function):
        self.description = description
        self.main_function = main_function
        self.logger = logging.getLogger(self.__class__.__name__)
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    def run(self):
        """Runs the provided main function and logs the outcome."""
        self.logger.info(f"--- Running: {self.description} ---")
        try:
            result = self.main_function()
            if result is False:
                self.logger.error(f"--- {self.description}: Failed ---")
                sys.exit(1)
            else:
                self.logger.info(f"--- {self.description}: Success ---")
        except Exception as e:
            self.logger.error(f"An error occurred during script execution: {e}", exc_info=True)
            self.logger.error(f"--- {self.description}: Failed with exception ---")
            sys.exit(1)
