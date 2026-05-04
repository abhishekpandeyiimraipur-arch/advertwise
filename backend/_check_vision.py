import requests, os, json
from dotenv import load_dotenv
from pathlib import Path
load_dotenv(Path('../.env.local'))

key = os.environ.get("TOGETHER_API_KEY", "")
print(f"Key prefix: {key[:15]}...")

resp = requests.get(
    'https://api.together.xyz/v1/models',
    headers={'Authorization': f'Bearer {key}'}
)
print(f"Status: {resp.status_code}")
data = resp.json()

if 'error' in data:
    print(f"Error: {data['error']}")
    print("\nTrying without auth (public endpoint)...")
    resp2 = requests.get('https://api.together.xyz/v1/models')
    print(f"Status: {resp2.status_code}")
    data = resp2.json()

if isinstance(data, list):
    models = data
elif isinstance(data, dict) and 'data' in data:
    models = data['data']
else:
    print("Cannot parse. Keys:", list(data.keys()) if isinstance(data, dict) else type(data))
    exit()

vision = [m['id'] for m in models if 'vision' in m.get('id','').lower() or 'vision' in json.dumps(m).lower()]
print(f'\nFound {len(vision)} vision models:')
for v in vision[:15]:
    print(f'  - {v}')
