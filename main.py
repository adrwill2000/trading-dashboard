import json
import requests
import subprocess
import os
from fastapi import FastAPI, HTTPException

SOLANA_RPC_URL = "https://api.mainnet-beta.solana.com"
JUPITER_API_URL = "https://quote-api.jup.ag/v6/quote"
RAYDIUM_API_URL = "https://api.raydium.io/v2/sdk/swap"
PUMP_FUN_API_URL = "https://pump.fun/api/trending"
MAX_SOL_TRANSFER = 100  # Prevent accidental large transactions


def get_wallet_balance():
    try:
        result = subprocess.run(["solana", "balance"], capture_output=True, text=True, check=True)
        return float(result.stdout.split()[0])
    except Exception:
        return 0.0


def is_valid_mint(mint_address: str):
    return len(mint_address) == 44


def fetch_jupiter_tokens():
    try:
        response = requests.get("https://cache.jup.ag/allTokens")
        response.raise_for_status()
        return response.json()
    except Exception:
        return {}


JUPITER_TOKENS = fetch_jupiter_tokens()

wallet_path = subprocess.run(["solana", "config", "get"], capture_output=True, text=True)
SOLANA_WALLET_PATH = ""
for line in wallet_path.stdout.split("\n"):
    if "Keypair Path:" in line:
        SOLANA_WALLET_PATH = line.split(" ")[-1].strip()
        break
if not SOLANA_WALLET_PATH or not os.path.exists(SOLANA_WALLET_PATH):
    SOLANA_WALLET_PATH = os.path.expanduser("~/.config/solana/id.json")

app = FastAPI()


@app.get("/bump")
def bump_pump_fun(target_address: str, amount: float):
    if amount <= 0 or amount > MAX_SOL_TRANSFER:
        raise HTTPException(status_code=400, detail="Invalid transfer amount. Must be between 0 and 100 SOL.")
    balance = get_wallet_balance()
    if amount > balance:
        raise HTTPException(status_code=400, detail=f"Insufficient funds. Wallet balance: {balance} SOL.")
    try:
        amount_lamports = int(amount * 1_000_000_000)
        print(f"Attempting to send {amount} SOL ({amount_lamports} lamports) to {target_address}")
        command = [
            "solana", "transfer", target_address, str(amount), "--from", SOLANA_WALLET_PATH, "--allow-unfunded-recipient", "--url", SOLANA_RPC_URL
        ]
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        return {"status": "success", "output": result.stdout.strip()}
    except subprocess.CalledProcessError as e:
        return {"status": "error", "message": e.stderr.strip()}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/trade")
def trade_jupiter(input_mint: str, output_mint: str, amount: float):
    if not is_valid_mint(input_mint) or not is_valid_mint(output_mint):
        raise HTTPException(status_code=400, detail="Invalid mint address.")
    if input_mint not in JUPITER_TOKENS or output_mint not in JUPITER_TOKENS:
        raise HTTPException(status_code=400, detail="One of the provided token mints is not supported by Jupiter.")
    try:
        amount_lamports = int(amount * 1_000_000_000)
        params = {
            "inputMint": input_mint,
            "outputMint": output_mint,
            "amount": str(amount_lamports),
            "slippageBps": 50,
        }
        print(f"Requesting Jupiter API: {JUPITER_API_URL} with params: {params}")
        response = requests.get(JUPITER_API_URL, params=params)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        return {"status": "error", "message": str(e)}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/raydium-trade")
def trade_raydium(input_mint: str, output_mint: str, amount: float):
    try:
        amount_lamports = int(amount * 1_000_000_000)
        params = {
            "inputMint": input_mint,
            "outputMint": output_mint,
            "amount": str(amount_lamports)
        }
        print(f"Requesting Raydium API: {RAYDIUM_API_URL} with params: {params}")
        response = requests.get(RAYDIUM_API_URL, params=params)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        return {"status": "error", "message": str(e)}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/pump-trending")
def get_trending_pump_tokens():
    try:
        response = requests.get(PUMP_FUN_API_URL)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        return {"status": "error", "message": str(e)}
    except Exception as e:
        return {"status": "error", "message": str(e)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

