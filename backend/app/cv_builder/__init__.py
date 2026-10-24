"""The Assignment 1 CV Builder core (profile agent, job retrieval, CV generation, PDF).

Moved here from CV_Builder/01_System/source_code/; the A1 logic and prompts are unchanged.
The API wraps it in app/services/cv_builds.py and app/routers/cv_builds.py.
"""

from .config import apply_settings_to_env

apply_settings_to_env()
