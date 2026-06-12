import json
import streamlit as st
import pandas as pd
import utils.display as dp
from rich import print
from config.settings import GET_WHOSCORED, GET_PATH, Settings
import soccerdata as sd

# set = Settings()

# path = GET_WHOSCORED['schedule']
# # print(f"[green]SUCCESS[/green]\tSave events DataFrame to path.\n\t[bold green]{path.name}[/bold green]")
# st.success(f":green[SUCCESS]&emsp;Save events DataFrame to path.\n&emsp;**:green[{path.name}]**")
import logging
import sys
import streamlit as st
import soccerdata as sd
from utils.logger import StreamlitLogHandler
st.title("🧪 Streamlit Logger Unit Test")
st.write("Click the button below to simulate background library processes (like Selenium or SoccerData) emitting logs.")

# 2. Setup the UI Layout placeholders
status_box = st.empty()

st.subheader("⚙️ Target UI Log Window (The Handler Output)")
log_ui_placeholder = st.empty()

# 1. Target the system-wide root logger instead of a named one
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)

# 2. Completely strip away any pre-packaged handlers (like rich)
# This forces libraries to stop bypassing your Streamlit handler
root_logger.handlers.clear()

# 3. Connect your custom Streamlit UI handler to the root stream
ui_handler = StreamlitLogHandler(log_ui_placeholder)
formatter = logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s", "%H:%M:%S")
ui_handler.setFormatter(formatter)
root_logger.addHandler(ui_handler)

# 4. Optional: Add a standard console backup stream so you can still see output in terminal
console_backup = logging.StreamHandler(sys.stdout)
console_backup.setFormatter(formatter)
root_logger.addHandler(console_backup)

# 5. Interactive UI Runner Check
if st.button("▶️ Run Logging Test Loop"):
    status_box.info("Scraper running... Intercepting engine logs...")
    
    # Force a completely uncached query so the library has to download data
    # (If the data is cached, it won't emit runtime logs!)
    ws = sd.WhoScored(leagues="FRA-Ligue 1", seasons="2324")
    
    status_box.success("Execution complete.")


st.stop()

import logging
import time
import streamlit as st

# 1. The Log Handler class we are testing
class StreamlitLogHandler(logging.Handler):
    def __init__(self, container):
        super().__init__()
        self.container = container
        self.log_buffer = []

    def emit(self, record):
        msg = self.format(record)
        self.log_buffer.append(msg)
        if len(self.log_buffer) > 15:  # Keep it short for testing
            self.log_buffer.pop(0)
        full_log_text = "\n".join(self.log_buffer)
        self.container.code(full_log_text, language="log")

st.title("🧪 Streamlit Logger Unit Test")
st.write("Click the button below to simulate background library processes (like Selenium or SoccerData) emitting logs.")

# 2. Setup the UI Layout placeholders
status_box = st.empty()

st.subheader("⚙️ Target UI Log Window (The Handler Output)")
log_ui_placeholder = st.empty()

# 3. Initialize the logging system
# We create a specific dummy logger name 'mock_library' for this test
# mock_logger = logging.getLogger("mock_library")
# mock_logger.setLevel(logging.INFO)

soccerdata = logging.getLogger("soccerdata")
soccerdata.setLevel(logging.INFO)


# Connect our custom Streamlit handler to the mock logger
ui_handler = StreamlitLogHandler(log_ui_placeholder)
formatter = logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s", "%H:%M:%S")
ui_handler.setFormatter(formatter)
# mock_logger.addHandler(ui_handler)
soccerdata.addHandler(ui_handler)

# 4. The Interactive Test Runner
if st.button("▶️ Run Logging Test Loop"):
    status_box.info("Test running... Watch the console box below populate in real-time!")
    ws = sd.WhoScored(leagues="ENG-Premier League", seasons=2425)
    
    # # Simulate background library logging milestones over a few seconds
    # mock_logger.info("Initializing automated browser environment...")
    # time.sleep(1)
    
    # mock_logger.info("Connecting to localhost port 40549...")
    # time.sleep(1)
    
    # mock_logger.warning("Connection sluggish, retrying session connection request (Attempt 1/3)...")
    # time.sleep(1.5)
    
    # mock_logger.info("SUCCESS: Connected to WhoScored target endpoint.")
    # time.sleep(1)
    
    # for i in range(1, 6):
    #     mock_logger.info(f"Downloading match event payload data package ({i}/5)...")
    #     time.sleep(0.5)
        
    # mock_logger.info("Data harvesting complete. Terminating active driver thread safely.")
    # status_box.success("✅ Test loop finished completely! Check the code block below to verify formatting matches expectations.")

else:
    status_box.warning("System idling. Click 'Run Logging Test Loop' above to fire test log signals.")



st.stop()

flat_df = pd.DataFrame()

file_path = GET_WHOSCORED['schedule']
df = pd.read_csv(file_path)
st.dataframe(df)
flat_df, config = dp.flatten_with_config(df)
st.dataframe(flat_df)
st.json(config)

flat_df.to_csv(GET_PATH['locales'], index=True)
with open(GET_PATH['locales', 'w']) as f:
    json.dump(config, f, indent=4)


