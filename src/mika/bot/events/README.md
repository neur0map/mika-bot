# bot/events/

Gateway event handlers, one file per event (`ready.py`, `message.py`, ...). Keep
handlers thin: validate, then delegate to llm/features.
