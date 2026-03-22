import streamlit.web.cli as stcli
import sys

def run():
    sys.argv = ["streamlit", "run", "app.py", "--server.port=8501"]
    sys.exit(stcli.main())

if __name__ == "__main__":
    run()
    