"""The suite exercises local demo flows explicitly; deployed defaults stay closed."""

import os

os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("ALLOW_DEMO_AUTH", "true")
