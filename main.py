"""
Banking Teller AI Assistant — CLI Entry Point

Usage:
    python main.py customer.json
    python main.py customer.json --model llama3.1:8b
    python main.py customer.json --rerank-backend cross-encoder --raw
    python main.py customer.json --no-rag        # disable retrieval grounding

Retrieval (RAG) is on by default: the assistant retrieves grounding docs from
docs/products/ via metadata-filtered hybrid search (dense + BM25) with a
cross-encoder rerank, so product references are grounded in real rates/fees.
"""

import sys
import logging
import argparse
from assistant import load_client, setup_lm, BankingAssistantModule
from rag import HybridRetriever


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate teller conversation prompts from a client JSON file."
    )
    parser.add_argument("client_file", help="Path to customer JSON file (e.g. customer.json)")
    parser.add_argument("--model", default="llama3.1:8b", help="Ollama chat model (default: llama3.1:8b)")
    parser.add_argument("--embed-model", default="nomic-embed-text",
                        help="Ollama embedding model for dense retrieval (default: nomic-embed-text)")
    parser.add_argument("--rerank-backend", default="auto",
                        choices=["auto", "cross-encoder", "llm", "none"],
                        help="Reranker: auto prefers cross-encoder, falls back to LLM (default: auto)")
    parser.add_argument("--no-rag", action="store_true", help="Disable retrieval grounding")
    parser.add_argument("--raw", action="store_true", help="Also print raw prompts and retrieved sources")
    parser.add_argument("--verbose", action="store_true", help="Show retrieval/reranker logging")
    return parser.parse_args()


def main():
    args = parse_args()
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING,
                        format="%(levelname)s [%(name)s] %(message)s")

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
    print(f"  RAG    : {'off' if args.no_rag else f'hybrid + rerank ({args.rerank_backend})'}")
    print(f"{'─' * 50}\n")

    # Setup LM
    try:
        setup_lm(model=args.model)
    except Exception as e:
        print(f"Error connecting to Ollama: {e}")
        print("Make sure Ollama is running: ollama serve")
        sys.exit(1)

    # Build retriever (indexes the docs corpus once)
    retriever = None
    if not args.no_rag:
        print("Indexing product corpus...\n")
        try:
            retriever = HybridRetriever.build(
                embed_model=args.embed_model,
                rerank_backend=args.rerank_backend,
            )
        except Exception as e:
            print(f"Warning: could not build retriever ({e}); continuing without RAG.\n")

    # Run assistant
    print("Generating prompts...\n")
    assistant = BankingAssistantModule(retriever=retriever)

    try:
        result = assistant(client=client)
    except Exception as e:
        print(f"Error during generation: {e}")
        sys.exit(1)

    # Optional: raw prompts + retrieved sources
    if args.raw:
        if getattr(result, "retrieved", None):
            print("── RETRIEVED SOURCES ────────────────────────────")
            for r in result.retrieved:
                print(f"  [{r.score:6.2f}] {r.document.title}  ({r.document.category})")
            print()
        print("── RAW PROMPTS ──────────────────────────────────")
        print(result.raw_prompts)
        print()

    # Refined prompts
    print("── SUGGESTED CONVERSATION PROMPTS ───────────────")
    if isinstance(result.refined_prompts, list):
        print("\n".join(result.refined_prompts))
    else:
        print(result.refined_prompts)
    print()


if __name__ == "__main__":
    main()
