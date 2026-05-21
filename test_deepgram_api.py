#!/usr/bin/env python3
from deepgram import DeepgramClient

# DeepgramClient reads DEEPGRAM_API_KEY from environment automatically
client = DeepgramClient()

# Check available methods
print("Client listen methods:")
for attr in dir(client.listen):
    if not attr.startswith('_'):
        print(f"  - {attr}")
        
# Try to see the actual structure
print("\nListenClient type:", type(client.listen))
print("Has prerecorded:", hasattr(client.listen, 'prerecorded'))

# List all non-private attributes
print("\nAll listen attributes:")
print([a for a in dir(client.listen) if not a.startswith('_')])
