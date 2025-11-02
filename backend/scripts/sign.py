import json
import os
import sys
from typing import Any, Dict

import requests
from eth_account import Account
from eth_account.messages import encode_defunct


def getenv_or_exit(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        print(f"Environment variable {name} is required", file=sys.stderr)
        sys.exit(1)
    return value


def post_json(url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    try:
        resp = requests.post(url, json=payload, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as exc:
        print(f"HTTP error calling {url}: {exc}", file=sys.stderr)
        if hasattr(exc, "response") and exc.response is not None:
            try:
                print(exc.response.text, file=sys.stderr)
            except Exception:
                pass
        sys.exit(2)


def main() -> None:
    api_base = os.environ.get("API_BASE", "http://localhost:3000")
    private_key = getenv_or_exit("PRIVATE_KEY")  # use a dev key only
    address = getenv_or_exit("ADDR")

    # 1) Request challenge
    challenge_url = f"{api_base}/api/v1/auth/challenge?address={address}"
    try:
        challenge_resp = requests.post(challenge_url, timeout=15)
        challenge_resp.raise_for_status()
        challenge = challenge_resp.json().get("challenge")
        if not challenge:
            print("No challenge returned by server", file=sys.stderr)
            sys.exit(3)
    except requests.RequestException as exc:
        print(f"HTTP error calling {challenge_url}: {exc}", file=sys.stderr)
        if hasattr(exc, "response") and exc.response is not None:
            try:
                print(exc.response.text, file=sys.stderr)
            except Exception:
                pass
        sys.exit(2)

    # 2) Sign challenge (personal_sign / EIP-191)
    message = encode_defunct(text=str(challenge))
    raw_sig = Account.sign_message(message, private_key=private_key).signature.hex()
    signature = raw_sig if raw_sig.startswith("0x") else f"0x{raw_sig}"

    # 3) Login to get JWT (endpoint expects query parameters)
    login_url = f"{api_base}/api/v1/auth/login"
    payload = {"challenge": challenge, "signature": signature, "address": address}
    try:
        resp = requests.post(login_url, params=payload, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as exc:
        print(f"HTTP error calling {login_url}: {exc}", file=sys.stderr)
        if hasattr(exc, "response") and exc.response is not None:
            try:
                print(exc.response.text, file=sys.stderr)
            except Exception:
                pass
        sys.exit(2)

    access_token = data.get("access_token")
    if not access_token:
        print("Login did not return access_token", file=sys.stderr)
        print(json.dumps(data, indent=2), file=sys.stderr)
        sys.exit(4)

    # Output token and handy usage examples
    print(access_token)
    print("\nExport for curl:")
    print(f"export AUTH='Authorization: Bearer {access_token}'")
    print('# example: curl -H "$AUTH"', f"{api_base}/api/v1/auth/me")


if __name__ == "__main__":
    main()
