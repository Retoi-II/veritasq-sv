# Define cyan color and reset variables
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${CYAN}Activating Python virtual environment...${NC}"
# Activate the virtual environment
source .venv/bin/activate

echo -e "${CYAN}Clearing streamlit cache...${NC}"
python -m streamlit cache clear

echo -e "${CYAN}Running app.py...${NC}"
python -m streamlit run app.py
