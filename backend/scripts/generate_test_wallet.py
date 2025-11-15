#!/usr/bin/env python3
"""
Generate a test wallet for development and testing.

This script creates a new Ethereum wallet with a random private key.
The wallet can be used for testing the authentication flow.

SECURITY WARNING: Only use this for development/testing!
Never use these wallets with real funds!
"""

import sys
from eth_account import Account


def main():
    print("=" * 60)
    print("AI Trading Agent - Test Wallet Generator")
    print("=" * 60)
    print()
    print("Generating a new test wallet...")
    print()
    
    # Create a new random wallet
    account = Account.create()
    
    print("[OK] Wallet generated successfully!")
    print()
    print("-" * 60)
    print("Wallet Details:")
    print("-" * 60)
    print(f"Address:     {account.address}")
    print(f"Private Key: {account.key.hex()}")
    print("-" * 60)
    print()

    print("Environment Variables:")
    print("-" * 60)
    print(f"export ADDR={account.address}")
    print(f"export PRIVATE_KEY={account.key.hex()}")
    print("-" * 60)
    print()

    print("Usage:")
    print("-" * 60)
    print("1. Copy the export commands above and run them in your terminal")
    print("2. Run the automated login script:")
    print("   cd backend && uv run python scripts/sign.py")
    print()
    print("Or use the demo script:")
    print("   cd backend && bash scripts/demo_login.sh")
    print("-" * 60)
    print()

    print("[WARNING] SECURITY WARNING:")
    print("-" * 60)
    print("- This is a TEST WALLET for development only!")
    print("- DO NOT use this wallet with real funds!")
    print("- DO NOT commit the private key to version control!")
    print("- Store the private key securely (e.g., in .env file)")
    print("-" * 60)
    print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nERROR: {e}", file=sys.stderr)
        sys.exit(1)

