import requests
import json

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
url = "http://localhost:3000/mcp/venture"
headers = {"Content-Type": "application/json"}

try:
    response = requests.post(url, json=payload, headers=headers)
    response.raise_for_status()  # Raise an exception for bad status codes
    
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
except requests.exceptions.RequestException as e:
    print(f"Error making request: {e}")
    if hasattr(e, 'response') and e.response is not None:
        print(f"Response status: {e.response.status_code}")
        print(f"Response body: {e.response.text}")
