import requests
import json
from pathlib import Path
from urllib.parse import quote

# JSON-RPC request payload
payload = {
    "jsonrpc": "2.0",
    "id": "1762507546312",
    "method": "tools/call",
    "params": {
        "name": "query",
        "arguments": {
            "kind": "venture"
        }
    }
}

# POST request to the MCP endpoint
url = "https://example-api.agenticprofile.ai/mcp/venture"
headers = {"Content-Type": "application/json"}

try:
    response = requests.post(url, json=payload, headers=headers)
    response.raise_for_status()  # Raise an exception for bad status codes
    
    print(f"Status Code: {response.status_code}")

    response_data = response.json()
    profiles = response_data.get("result", {}).get("profiles", [])

    summaries_dir = Path(__file__).parent / "data" / "venture-summaries"
    summaries_dir.mkdir(parents=True, exist_ok=True)

    for profile in profiles:
        profile_id = profile.get("id")
        if not profile_id:
            print("Skipping profile without an 'id' field:"
                  f" {json.dumps(profile, indent=2)}")
            continue

        base_id = str(profile_id).split("^", 1)[0]
        if not base_id:
            print("Skipping profile with empty base id:"
                  f" {json.dumps(profile, indent=2)}")
            continue

        escaped_id = quote(base_id, safe="-_.")
        if not escaped_id:
            print("Skipping profile with empty escaped id:"
                  f" {json.dumps(profile, indent=2)}")
            continue

        profile_path = summaries_dir / f"{escaped_id}.json"
        profile_path.write_text(json.dumps(profile, indent=2) + "\n")

    print(f"Wrote {len(profiles)} profile files to {summaries_dir}")
except requests.exceptions.RequestException as e:
    print(f"Error making request: {e}")
    if hasattr(e, 'response') and e.response is not None:
        print(f"Response status: {e.response.status_code}")
        print(f"Response body: {e.response.text}")
