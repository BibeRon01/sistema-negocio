# Alias entrypoint delegating directly to app.py
import runpy
import os

_app_path = os.path.join(os.path.dirname(__file__), "app.py")
runpy.run_path(_app_path, run_name="__main__")
