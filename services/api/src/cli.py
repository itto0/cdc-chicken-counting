import argparse
from services.api.src.db.models import ApiKey
from services.api.src.db.session import SessionLocal
from services.api.src.main import init_db
from services.api.src.services.auth import generate_api_key


def create_api_key_cmd(name: str, role: str) -> str:
    init_db()
    raw_key, key_hash, prefix = generate_api_key()
    with SessionLocal() as db:
        key_record = ApiKey(
            name=name,
            key_hash=key_hash,
            prefix=prefix,
            role=role.upper(),
            is_active=True,
        )
        db.add(key_record)
        db.commit()
        db.refresh(key_record)
        return raw_key


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Lihat.id Poultry Counter Central API Admin CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create_parser = subparsers.add_parser("create-api-key", help="Create a persistent API key for edge devices")
    create_parser.add_argument("--name", required=True, help="Descriptive name of the device/key (e.g. 'Line 1 Edge')")
    create_parser.add_argument(
        "--role",
        default="OPERATOR",
        type=str.upper,
        choices=["OPERATOR", "ADMIN"],
        help="Role assigned to this key",
    )

    args = parser.parse_args(argv)
    if args.command == "create-api-key":
        key = create_api_key_cmd(args.name, args.role)
        print(f"API Key created successfully for '{args.name}' [{args.role}]:")
        print(f"  {key}")
        print("Store this key securely in the edge device's .env file as API_TOKEN.")


if __name__ == "__main__":
    main()
