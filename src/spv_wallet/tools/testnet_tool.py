#!/usr/bin/env python3
"""BSV Testnet Tool — generate keys, check balance, list UTXOs.

A standalone CLI utility for interacting with the BSV testnet:

    # Generate a testnet wallet (seed phrase + tprv + addresses)
    python -m spv_wallet.tools.testnet_tool generate

    # Check balance of a testnet address
    python -m spv_wallet.tools.testnet_tool balance <address>

    # List UTXOs for a testnet address
    python -m spv_wallet.tools.testnet_tool utxos <address>

    # Derive addresses from an existing tprv/xprv key
    python -m spv_wallet.tools.testnet_tool derive <tprv_string> [count]

After generating an address, visit the testnet faucet to receive coins:
    https://witnessonchain.com/faucet/tbsv
"""

from __future__ import annotations

import asyncio
import sys


def _cmd_generate() -> None:
    """Generate a new testnet wallet: mnemonic → tprv → first 5 addresses."""
    from mnemonic import Mnemonic

    from spv_wallet.bsv.address import privkey_to_wif, pubkey_to_address
    from spv_wallet.bsv.keys import ExtendedKey

    m = Mnemonic("english")
    words = m.generate(strength=128)
    seed = m.to_seed(words)

    master = ExtendedKey.from_seed(seed, testnet=True)
    tprv = master.to_string()
    tpub = master.neuter().to_string()

    # BIP44 path: m/44'/236'/0'
    account = master.derive_path("m/44'/236'/0'")
    external = account.derive_child(0)  # external (receiving) chain

    print("=" * 60)
    print("BSV TESTNET WALLET")
    print("=" * 60)
    print()
    print(f"Mnemonic:  {words}")
    print()
    print(f"Master tprv: {tprv}")
    print(f"Master tpub: {tpub}")
    print()
    print("First 5 receiving addresses (m/44'/236'/0'/0/i):")
    print("-" * 60)

    for i in range(5):
        child = external.derive_child(i)
        pubkey = child.public_key()
        address = pubkey_to_address(pubkey, testnet=True)
        wif = privkey_to_wif(child.key, testnet=True)
        print(f"  [{i}] {address}")
        print(f"      WIF: {wif}")

    print()
    print("To get testnet coins, visit:")
    print("  https://witnessonchain.com/faucet/tbsv")
    print()
    print("Send coins to any of the addresses above, then run:")
    print("  python -m spv_wallet.tools.testnet_tool balance <address>")


def _cmd_balance(address: str) -> None:
    """Check balance of a testnet address via WhatsOnChain."""
    from spv_wallet.chain.woc.client import WoCClient

    async def _run() -> None:
        woc = WoCClient(testnet=True)
        await woc.connect()
        try:
            bal = await woc.get_balance(address)
            print(f"Address:      {address}")
            print(f"Confirmed:    {bal.confirmed:>12,} sats  ({bal.confirmed / 1e8:.8f} BSV)")
            print(f"Unconfirmed:  {bal.unconfirmed:>12,} sats  ({bal.unconfirmed / 1e8:.8f} BSV)")
            print(f"Total:        {bal.total:>12,} sats  ({bal.total / 1e8:.8f} BSV)")
        finally:
            await woc.close()

    asyncio.run(_run())


def _cmd_utxos(address: str) -> None:
    """List UTXOs for a testnet address via WhatsOnChain."""
    from spv_wallet.chain.woc.client import WoCClient

    async def _run() -> None:
        woc = WoCClient(testnet=True)
        await woc.connect()
        try:
            utxos = await woc.get_utxos(address)
            if not utxos:
                print(f"No UTXOs found for {address}")
                return
            print(f"UTXOs for {address}:")
            print("-" * 80)
            total = 0
            for u in utxos:
                conf = f"height={u.height}" if u.height > 0 else "unconfirmed"
                print(f"  {u.tx_hash}:{u.tx_pos}  {u.value:>12,} sats  ({conf})")
                total += u.value
            print("-" * 80)
            print(f"  Total: {total:>12,} sats  ({total / 1e8:.8f} BSV)  [{len(utxos)} UTXOs]")
        finally:
            await woc.close()

    asyncio.run(_run())


def _cmd_derive(key_string: str, count: int = 5) -> None:
    """Derive receiving addresses from a tprv/xprv key."""
    from spv_wallet.bsv.address import pubkey_to_address
    from spv_wallet.bsv.keys import ExtendedKey

    master = ExtendedKey.from_string(key_string)
    testnet = master.testnet

    network = "TESTNET" if testnet else "MAINNET"
    print(f"Network: {network}")
    print(f"Key: {key_string[:12]}...")
    print()

    # BIP44 path: m/44'/236'/0'/0/i
    account = master.derive_path("m/44'/236'/0'")
    external = account.derive_child(0)

    print("Derived addresses (m/44'/236'/0'/0/i):")
    print("-" * 60)
    for i in range(count):
        child = external.derive_child(i)
        pubkey = child.public_key()
        address = pubkey_to_address(pubkey, testnet=testnet)
        print(f"  [{i}] {address}")


def main() -> None:
    """CLI entry point."""
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1].lower()

    if cmd == "generate":
        _cmd_generate()
    elif cmd == "balance":
        if len(sys.argv) < 3:
            print("Usage: testnet_tool balance <address>")
            sys.exit(1)
        _cmd_balance(sys.argv[2])
    elif cmd == "utxos":
        if len(sys.argv) < 3:
            print("Usage: testnet_tool utxos <address>")
            sys.exit(1)
        _cmd_utxos(sys.argv[2])
    elif cmd == "derive":
        if len(sys.argv) < 3:
            print("Usage: testnet_tool derive <tprv_string> [count]")
            sys.exit(1)
        count = int(sys.argv[3]) if len(sys.argv) > 3 else 5
        _cmd_derive(sys.argv[2], count)
    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
