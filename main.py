"""
Banking Teller AI Assistant — CLI Entry Point

Usage:
    python main.py customer.json
    python main.py customer.json --model mistral
    python main.py customer.json --model llama3 --raw
"""

import sys
import argparse
from assistant import load_client, setup_lm, BankingAssistantModule


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate teller conversation prompts from a client JSON file."
    )
    parser.add_argument("client_file", help="Path to customer JSON file (e.g. customer.json)")
    parser.add_argument("--model",  default="llama3.1:8b", help="Ollama model to use (default: llama3.1:8b)")
    parser.add_argument("--raw",    action="store_true", help="Also print the raw unrefined prompts")
    return parser.parse_args()


def main():
    args = parse_args()

    # Load client
    try:
        client = load_client(args.client_file)
    except FileNotFoundError:
        print(f"Error: file not found — {args.client_file}")
        sys.exit(1)
    except KeyError as e:
        print(f"Error: missing required field in JSON — {e}")
        sys.exit(1)

    print(f"\n{'─' * 50}")
    print(f"  Client : {client.name}, age {client.age}")
    print(f"  Model  : {args.model}")
    print(f"{'─' * 50}\n")

    # Setup LM
    try:
        setup_lm(model=args.model)
    except Exception as e:
        print(f"Error connecting to Ollama: {e}")
        print("Make sure Ollama is running: ollama serve")
        sys.exit(1)

    # Run assistant
    print("Generating prompts...\n")
    assistant = BankingAssistantModule()

    try:
        result = assistant(client_profile=client.to_prompt_string())
    except Exception as e:
        print(f"Error during generation: {e}")
        sys.exit(1)

    # Print raw prompts (optional)
    if args.raw:
        print("── RAW PROMPTS ──────────────────────────────────")
        print(result.raw_prompts)
        print()

    # Print refined prompts
    print("── SUGGESTED CONVERSATION PROMPTS ───────────────")
    if isinstance(result.refined_prompts, list):
        print("\n".join(result.refined_prompts))
    else:
        print(result.refined_prompts)
    print()


if __name__ == "__main__":
    main()