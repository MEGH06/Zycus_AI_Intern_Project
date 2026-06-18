"""CLI entrypoint: python -m src.cli <command> [options]"""
import argparse
import json
import sys


def cmd_health(_args: argparse.Namespace) -> None:
    print(json.dumps({"status": "ok"}))


def cmd_inspect_data(args: argparse.Namespace) -> None:
    from src.config import load_config
    from src.data_loader import DataAvailabilityError, DataFormatError
    from src.data_loader import load_accounts, load_knowledge_base, load_tickets

    config = load_config()
    use_fixtures: bool = args.use_fixtures

    try:
        tickets = load_tickets(config, use_fixtures=use_fixtures)
        accounts = load_accounts(config, use_fixtures=use_fixtures)
        kb_docs = load_knowledge_base(config, use_fixtures=use_fixtures)
    except (DataAvailabilityError, DataFormatError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    mode = "fixtures" if use_fixtures else "real"
    print(json.dumps({
        "tickets": len(tickets),
        "accounts": len(accounts),
        "knowledge_docs": len(kb_docs),
        "mode": mode,
    }))


def cmd_triage(args: argparse.Namespace) -> None:
    from src.data_loader import DataAvailabilityError, DataFormatError
    from src.triage import triage_ticket
    from src.visual_trace import to_mermaid

    try:
        result = triage_ticket(
            {"subject": args.subject, "body": args.body},
            use_fixtures=args.use_fixtures,
        )
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    except (DataAvailabilityError, DataFormatError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    print(json.dumps(result.model_dump(), indent=2))

    if args.trace_mermaid:
        print("\n--- Mermaid Trace ---")
        print(to_mermaid(result.trace))


def cmd_account_brief(args: argparse.Namespace) -> None:
    from src.account_health import generate_account_brief
    from src.data_loader import DataAvailabilityError, DataFormatError
    from src.visual_trace import to_mermaid

    try:
        result = generate_account_brief(
            account_id=args.account_id,
            use_fixtures=args.use_fixtures,
        )
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    except (DataAvailabilityError, DataFormatError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    print(json.dumps(result.model_dump(), indent=2))

    if args.trace_mermaid:
        print("\n--- Mermaid Trace ---")
        print(to_mermaid(result.trace))


def cmd_ui(_args: argparse.Namespace) -> None:
    print("streamlit run ui/streamlit_app.py")


def cmd_eval(args: argparse.Namespace) -> None:
    from evals.run_eval import run_all, write_reports
    result = run_all(use_fixtures=args.use_fixtures)
    write_reports(result)
    print(f"Overall: {result['overall_score']}  Passed: {result['passed_cases']}/{result['total_cases']}")


def cmd_not_implemented(name: str) -> None:
    print(f"NotImplementedError: '{name}' is not yet implemented.", file=sys.stderr)
    sys.exit(2)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="src.cli",
        description="Zycus AI Support / TAM CLI",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("health", help="Print service health as JSON")

    inspect = sub.add_parser("inspect-data", help="Show counts of loaded data")
    inspect.add_argument("--use-fixtures", action="store_true")

    triage = sub.add_parser("triage", help="Triage a support ticket")
    triage.add_argument("--subject", default="")
    triage.add_argument("--body", required=True)
    triage.add_argument("--use-fixtures", action="store_true")
    triage.add_argument("--trace-mermaid", action="store_true")

    demo = sub.add_parser("demo-all", help="Run all tasks using fixture data")
    demo.add_argument("--use-fixtures", action="store_true", required=True)

    sub.add_parser("ui", help="Print command to launch Streamlit UI")

    ev = sub.add_parser("eval", help="Run the evaluation harness")
    ev.add_argument("--use-fixtures", action="store_true")

    brief = sub.add_parser("account-brief", help="Generate a TAM account health brief")
    brief.add_argument("--account-id", required=True)
    brief.add_argument("--use-fixtures", action="store_true")
    brief.add_argument("--trace-mermaid", action="store_true")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "health":
        cmd_health(args)
    elif args.command == "inspect-data":
        cmd_inspect_data(args)
    elif args.command == "triage":
        cmd_triage(args)
    elif args.command == "ui":
        cmd_ui(args)
    elif args.command == "eval":
        cmd_eval(args)
    elif args.command == "demo-all":
        cmd_not_implemented("demo-all")
    elif args.command == "account-brief":
        cmd_account_brief(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
