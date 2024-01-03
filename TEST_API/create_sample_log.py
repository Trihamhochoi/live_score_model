# == Necessary Imports =========================================================
import logging
import pandas as pd
import getpass


# == Script Configuration ======================================================
# Set a seed to enable reproducibility
SEED = 1

# Get the username of the person who is running the script.
USERNAME = getpass.getuser()

# Set a format to the logs.
LOG_FORMAT = '[%(levelname)s | ' + USERNAME + ' | %(asctime)s] - %(message)s'

# Name of the file to store the logs.
LOG_FILENAME = 'script_execution.log'

# Level in which messages are to be logged. Logging, by default has the
# following levels, ordered by ranking of severity:
# 1. DEBUG: detailed information, useful only when diagnosing a problem.
# 2. INFO: message that confirms that everything is working as it should.
# 3. WARNING: message with information that requires user attention
# 4. ERROR: an error has occurred and script is unable to perform some function.
# 5. CRITICAL: serious error occurred and script may stop running properly.
LOG_LEVEL = logging.INFO
# When you set the level, all messages from a higher level of severity are also
# logged. For example, when you set the log level to `INFO`, all `WARNING`,
# `ERROR` and `CRITICAL` messages are also logged, but `DEBUG` messages are not.


# == Set up logging ============================================================
logging.basicConfig(
    level=LOG_LEVEL,
    format=LOG_FORMAT,
    force=True,
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.FileHandler(LOG_FILENAME, "a", "utf-8"),
              logging.StreamHandler()]
)


# == Script Start ==============================================================
# Log the script execution start
logging.info('Script started execution!')

# Read data from the Excel file
data = pd.read_excel('example.xlsx')

# Retrieve a sample with 50% of the rows from `data`.
# When a `random_state` is set, `pd.DataFrame.sample` will always return
# the same dataframe, given that `data` doesn't change.
sample_data = data.sample(frac=0.5, random_state=SEED)

# Other stuff
# ...

# Log when the script finishes execution
logging.info('Script finished execution!')