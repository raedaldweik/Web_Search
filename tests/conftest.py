import os

# Ensure a key is present so import-time warnings stay quiet and the client does
# not short-circuit on a missing key during tests that stub the network.
os.environ.setdefault("TAVILY_API_KEY", "tvly-test-key")
