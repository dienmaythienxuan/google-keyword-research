from __future__ import annotations

import argparse
import logging
import os
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from google.oauth2.credentials import Credentials

GOOGLE_ADS_SCOPE = "https://www.googleapis.com/auth/adwords"
ENV_CLIENT_ID = "GOOGLE_CLIENT_ID"
ENV_CLIENT_SECRET = "GOOGLE_CLIENT_SECRET"
SCRIPT_NAME = Path(__file__).name
REPO_DIR = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = REPO_DIR / "google-ads.yaml"


@dataclass(frozen=True)
class OAuthClientConfig:
    client_id: str
    client_secret: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Get a Google Ads OAuth refresh token via Google OAuth 2.0."
    )
    parser.add_argument(
        "--client-id",
        help=f"OAuth Client ID. Falls back to {ENV_CLIENT_ID} or google-ads.yaml.",
    )
    parser.add_argument(
        "--client-secret",
        help=f"OAuth Client Secret. Falls back to {ENV_CLIENT_SECRET} or google-ads.yaml.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help=f"Path to google-ads.yaml (default: {DEFAULT_CONFIG})",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=0,
        help="Local callback port. Default 0 lets the OS choose a free port.",
    )
    parser.add_argument(
        "--no-write",
        action="store_true",
        help="Do not write the new refresh_token back to google-ads.yaml.",
    )
    return parser.parse_args()


def load_yaml_config(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    try:
        import yaml
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Missing dependency PyYAML. Install with: "
            "python3 -m pip install -r requirements.txt"
        ) from exc
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Invalid Google Ads config format in {path}")
    return data


def load_client_config(args: argparse.Namespace) -> OAuthClientConfig:
    yaml_data = load_yaml_config(args.config)
    client_id = (
        os.getenv(ENV_CLIENT_ID)
        or args.client_id
        or str(yaml_data.get("client_id") or "").strip()
    )
    client_secret = (
        os.getenv(ENV_CLIENT_SECRET)
        or args.client_secret
        or str(yaml_data.get("client_secret") or "").strip()
    )

    missing = []
    if not client_id:
        missing.append("client_id")
    if not client_secret:
        missing.append("client_secret")

    if missing:
        raise ValueError(
            "Missing OAuth client credentials: "
            + ", ".join(missing)
            + "\n\nProvide them via google-ads.yaml, environment variables, or CLI:\n"
            + f"  {sys.executable} {SCRIPT_NAME}\n"
            + f"  {sys.executable} {SCRIPT_NAME} "
            + "--client-id your-client-id.apps.googleusercontent.com "
            + "--client-secret your-client-secret"
        )

    return OAuthClientConfig(client_id=client_id, client_secret=client_secret)


def build_installed_app_config(config: OAuthClientConfig) -> dict[str, object]:
    return {
        "installed": {
            "client_id": config.client_id,
            "client_secret": config.client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }


def run_oauth_flow(config: OAuthClientConfig, port: int) -> "Credentials":
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Missing dependency google-auth-oauthlib. Install with:\n"
            "  .venv/bin/pip install -r requirements.txt\n"
            f"Then run:\n  .venv/bin/python {SCRIPT_NAME}"
        ) from exc

    flow = InstalledAppFlow.from_client_config(
        build_installed_app_config(config),
        scopes=[GOOGLE_ADS_SCOPE],
    )

    logging.info("Opening browser for Google OAuth consent...")
    credentials = flow.run_local_server(
        port=port,
        open_browser=True,
        authorization_prompt_message=(
            "Please visit this URL to authorize this application: {url}"
        ),
        success_message=(
            "Authorization complete. You can close this browser tab and return "
            "to the terminal."
        ),
        access_type="offline",
        prompt="consent",
    )

    if not credentials.refresh_token:
        raise RuntimeError(
            "Google did not return a refresh token. Re-run the script and make "
            "sure you approve the consent prompt. If you previously authorized "
            "this app, revoke its access at https://myaccount.google.com/permissions "
            "and try again."
        )

    return credentials


def write_refresh_token(config_path: Path, refresh_token: str) -> None:
    try:
        import yaml
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Missing dependency PyYAML. Install with: "
            "python3 -m pip install -r requirements.txt"
        ) from exc

    data = load_yaml_config(config_path)
    data["refresh_token"] = refresh_token
    if "login_customer_id" in data and data["login_customer_id"] is not None:
        data["login_customer_id"] = str(data["login_customer_id"]).replace("-", "")
    if "use_proto_plus" not in data:
        data["use_proto_plus"] = True

    config_path.parent.mkdir(parents=True, exist_ok=True)
    with config_path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle, default_flow_style=False, allow_unicode=True, sort_keys=False)


def format_expiry(expiry: datetime | None) -> str:
    if expiry is None:
        return "Unknown"

    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=UTC)
    else:
        expiry = expiry.astimezone(UTC)

    return expiry.isoformat(timespec="seconds").replace("+00:00", "Z")


def print_credentials(credentials: "Credentials") -> None:
    print("\nRefresh Token:")
    print(credentials.refresh_token)
    print("\nAccess Token:")
    print(credentials.token)
    print("\nExpires:")
    print(format_expiry(credentials.expiry))


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s: %(message)s",
    )


def main() -> int:
    configure_logging()
    args = parse_args()

    try:
        config = load_client_config(args)
        credentials = run_oauth_flow(config, args.port)
        print_credentials(credentials)
        if not args.no_write:
            write_refresh_token(args.config, credentials.refresh_token)
            logging.info("Updated refresh_token in %s", args.config)
    except ValueError as exc:
        logging.error("%s", exc)
        return 2
    except OSError as exc:
        logging.error("Could not start local OAuth callback server: %s", exc)
        return 1
    except KeyboardInterrupt:
        logging.warning("OAuth flow cancelled by user.")
        return 130
    except Exception as exc:
        logging.error("OAuth flow failed: %s", exc)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
