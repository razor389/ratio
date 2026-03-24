"""Outlook ingestion script for collecting ticker-related sent emails."""

import json
import logging
import sys
from typing import List, Dict, Any, Set, Optional, Iterable, Tuple
import re
from datetime import datetime, timedelta
import os
from pathlib import Path
from dotenv import load_dotenv

from ..core.config import get_settings

# Configure logging for console output only
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s:%(message)s",
)

# Load environment variables from .env file
load_dotenv()

SENDER_EMAIL = (os.getenv("SENDER_EMAIL") or "").strip().lower()
EXCLUDED_EMAIL = (os.getenv("EXCLUDED_EMAIL") or "").strip().lower()

# MAPI property tags for SMTP addresses (works better than SenderEmailAddress for Exchange)
PR_SENDER_SMTP_ADDRESS = "http://schemas.microsoft.com/mapi/proptag/0x5D01001E"
PR_RECEIVED_BY_SMTP_ADDRESS = "http://schemas.microsoft.com/mapi/proptag/0x5D07001E"
PR_SENT_REPRESENTING_SMTP_ADDRESS = "http://schemas.microsoft.com/mapi/proptag/0x5D02001E"


def get_sender_email() -> str:
    """Return the configured sender email or raise if it is missing."""
    if not SENDER_EMAIL:
        raise ValueError("SENDER_EMAIL not found in .env file")
    return SENDER_EMAIL


def safe_getattr(obj, name, default=None):
    """Safely get an attribute from a COM object without raising."""
    try:
        return getattr(obj, name, default)
    except Exception:
        return default


def to_naive(dt: datetime) -> datetime:
    """Return a tz-naive datetime (drop tzinfo if present)."""
    if isinstance(dt, datetime) and dt.tzinfo is not None:
        return dt.replace(tzinfo=None)
    return dt


def load_ticker_config(config_path: str = "ticker_email_config.json") -> Dict[str, List[str]]:
    """
    Load ticker configuration from JSON file.
    Returns empty dict if file not found or invalid.
    """
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        if not isinstance(config, dict):
            logging.warning(f"Config file is not a dict: {config_path}")
            return {}
        # Normalize config values to list[str]
        normalized: Dict[str, List[str]] = {}
        for k, v in config.items():
            if isinstance(v, list):
                normalized[str(k).upper()] = [str(x) for x in v if str(x).strip()]
            else:
                normalized[str(k).upper()] = [str(v)]
        return normalized
    except FileNotFoundError:
        logging.warning(f"Config file not found: {config_path}")
        return {}
    except json.JSONDecodeError:
        logging.warning(f"Config file invalid JSON: {config_path}")
        return {}


def initialize_outlook():
    """Initialize and return the Outlook namespace."""
    try:
        import win32com.client

        outlook = win32com.client.Dispatch("Outlook.Application")
        namespace = outlook.GetNamespace("MAPI")
        # Use existing profile/session; avoid prompting if possible.
        namespace.Logon("", "", False, False)
        return namespace
    except Exception as e:
        logging.error(f"Failed to initialize Outlook: {e}")
        sys.exit(1)


def safe_get_smtp_from_accessor(message, prop_tag: str) -> Optional[str]:
    """Try to get an SMTP address using PropertyAccessor; return None if unavailable."""
    try:
        accessor = safe_getattr(message, "PropertyAccessor", None)
        if accessor is None:
            return None
        val = accessor.GetProperty(prop_tag)
        if val:
            return str(val).strip().lower()
    except Exception:
        return None
    return None


def safe_get_sender_smtp(message) -> Optional[str]:
    """
    Get sender SMTP address robustly (Exchange often has non-SMTP SenderEmailAddress).
    """
    # Try common SMTP props
    for tag in (PR_SENDER_SMTP_ADDRESS, PR_SENT_REPRESENTING_SMTP_ADDRESS):
        smtp = safe_get_smtp_from_accessor(message, tag)
        if smtp:
            return smtp

    # Fallback
    try:
        v = safe_getattr(message, "SenderEmailAddress", None)
        if v:
            return str(v).strip().lower()
    except Exception:
        pass
    return None


def safe_iter_recipients_addresses(message) -> Iterable[str]:
    """
    Yield recipient addresses. On Exchange, Recipients[i].Address may not be SMTP,
    but it's still useful as a fallback. This function is best-effort and never throws.
    """
    try:
        recipients = safe_getattr(message, "Recipients", None)
        if not recipients:
            return
        for r in recipients:
            try:
                addr = safe_getattr(r, "Address", None)
                if addr:
                    yield str(addr).strip().lower()
            except Exception:
                continue
    except Exception:
        return


def email_contains_excluded_address(message, excluded_email: str) -> bool:
    """
    Returns True if the excluded email appears as sender or recipient
    (To, CC, or BCC) in the message.

    IMPORTANT: This is best-effort. If anything goes wrong, we FAIL OPEN (return False),
    so we don't accidentally exclude everything.
    """
    if not excluded_email:
        return False

    try:
        fields: List[str] = []

        sender_smtp = safe_get_sender_smtp(message)
        if sender_smtp:
            fields.append(sender_smtp)

        for addr in safe_iter_recipients_addresses(message):
            fields.append(addr)

        combined = " ".join(fields).lower()
        return excluded_email in combined
    except Exception:
        # Fail open
        return False


def is_valid_search_term(term: str) -> bool:
    """
    Validate search term format.
    Allow either ticker format (1-5 uppercase letters) or company names (word characters and spaces)
    """
    return bool(re.match(r"^[A-Z]{1,5}$", term) or re.match(r"^[\w\s-]+$", term))


def clean_message(raw_message: str) -> str:
    """
    Cleans the raw email message by removing excessive line breaks,
    email signatures, and other boilerplate text.
    """
    signature_patterns = [
        r"Scott Granowski CFA®, CFP®\s+Academy Capital Management.*",
        r"Sent via .*",
        r"-------- Original message --------.*",
        r"From: .*",
        r"[\r\n]{2,}",
    ]

    cleaned = raw_message or ""

    for pattern in signature_patterns:
        cleaned = re.sub(pattern, "", cleaned, flags=re.DOTALL | re.IGNORECASE)

    # Replace multiple line breaks with single space
    cleaned = re.sub(r"[\r\n]+", " ", cleaned)

    # Remove any remaining excessive whitespace
    cleaned = re.sub(r"\s{2,}", " ", cleaned)

    return cleaned.strip()


def build_items_sources(namespace) -> List[Tuple[str, Any]]:
    """
    Return list of (source_name, ItemsCollection) for Sent Items.
    Recommended change: search Sent Items across ALL stores, so multi-account/shared mailbox works.
    """
    sources: List[Tuple[str, Any]] = []

    # Try all stores
    try:
        top_folders = namespace.Folders
        for store in top_folders:
            try:
                store_name = str(safe_getattr(store, "Name", "UnknownStore"))
                sent_folder = None

                # Most common English name
                try:
                    sent_folder = store.Folders["Sent Items"]
                except Exception:
                    sent_folder = None

                if sent_folder is None:
                    continue

                items = sent_folder.Items
                # Sort descending by SentOn
                try:
                    items.Sort("[SentOn]", True)
                except Exception:
                    pass

                count = safe_getattr(items, "Count", None)
                if count is None:
                    sources.append((f"{store_name} / Sent Items", items))
                else:
                    sources.append((f"{store_name} / Sent Items (Count={count})", items))
            except Exception:
                continue
    except Exception as e:
        logging.warning(f"Failed to enumerate stores. Falling back to default Sent Items. Error: {e}")

    # Fallback: default Sent Items
    if not sources:
        try:
            sent_folder = namespace.GetDefaultFolder(5)  # 5 = olFolderSentMail
            items = sent_folder.Items
            try:
                items.Sort("[SentOn]", True)
            except Exception:
                pass
            sources.append(("Default Store / Sent Items", items))
        except Exception as e:
            logging.error(f"Error fetching default Sent Items: {e}")

    return sources

def filter_emails(
    items_sources: List[Tuple[str, Any]],
    search_terms: Set[str],
    sender_email: str,
    lookback_years: int = 15,
) -> List[Dict[str, Any]]:
    """
    Filter emails that contain any of the search terms in the subject line.
    """
    filtered_emails: List[Dict[str, Any]] = []
    processed_count = 0
    seen_emails = set()

    # Define cutoff (naive)
    cutoff_date = to_naive(datetime.now() - timedelta(days=lookback_years * 365))

    patterns = {
        term: re.compile(r"\b" + re.escape(term) + r"\b", re.IGNORECASE)
        for term in search_terms
    }

    for source_name, items in items_sources:
        logging.info(f"Scanning Source: {source_name} ...")

        for message in items:
            # 1. Class Check (43 = olMailItem)
            if safe_getattr(message, "Class", None) != 43:
                continue

            # 2. Date Check
            sent_time_dt_raw = safe_getattr(message, "SentOn", None)
            if not sent_time_dt_raw:
                continue

            # Convert to naive datetime
            try:
                sent_time_dt = datetime(
                    sent_time_dt_raw.year, sent_time_dt_raw.month, sent_time_dt_raw.day,
                    sent_time_dt_raw.hour, sent_time_dt_raw.minute, sent_time_dt_raw.second
                )
            except Exception:
                continue

            # 3. Cutoff Check
            # Since items are sorted Descending, we can break once we hit old emails
            if sent_time_dt < cutoff_date:
                break

            # 4. Excluded Email Check
            if email_contains_excluded_address(message, EXCLUDED_EMAIL):
                continue

            # 5. Sender Match Check REMOVED
            # We trust "Sent Items" contains only emails sent by the user.
            # This avoids the Exchange X.500 address mismatch issue.

            subject = str(safe_getattr(message, "Subject", "") or "").strip()
            if not subject:
                continue

            # 6. Term Match Check
            found_terms = [
                term for term, pattern in patterns.items() if pattern.search(subject)
            ]
            
            if found_terms:
                logging.info(f"MATCH FOUND: '{subject}' with terms {found_terms}")
                
                unix_timestamp = int(sent_time_dt.timestamp())
                email_id = f"{unix_timestamp}_{subject}"

                if email_id in seen_emails:
                    continue
                seen_emails.add(email_id)

                filtered_emails.append({
                    "timestamp": unix_timestamp,
                    "message": clean_message(str(safe_getattr(message, "Body", "") or "")),
                    "authorEmail": sender_email,
                    "sourceFolder": source_name,
                    "subject": subject,
                })

            processed_count += 1
            if processed_count % 1000 == 0:
                logging.info(f"Processed {processed_count} messages...")

    return filtered_emails

def filter_emails_by_config(
    ticker: str,
    config_path: str = "ticker_email_config.json",
    lookback_years: int = 15,
) -> List[Dict[str, Any]]:
    """
    Main function to filter sent emails by ticker and its related terms from config.
    If ticker not in config, searches for just the ticker symbol.
    """
    ticker = ticker.upper()

    # Validate ticker format
    if not is_valid_search_term(ticker):
        raise ValueError(f"Invalid ticker format: {ticker}")

    # Load config and get search terms
    config = load_ticker_config(config_path)

    # Create set of search terms - if ticker not in config, just use the ticker
    search_terms = set([ticker] + config.get(ticker, []))
    sender_email = get_sender_email()

    logging.info(f"Searching for terms: {search_terms} in Sent Items")

    namespace = initialize_outlook()
    items_sources = build_items_sources(namespace)

    if not items_sources:
        logging.info("No Sent Items sources found to scan.")
        return []

    filtered_emails = filter_emails(
        items_sources=items_sources,
        search_terms=search_terms,
        sender_email=sender_email,
        lookback_years=lookback_years,
        )

    if not filtered_emails:
        logging.info(f"No emails found containing any search terms for {ticker}")
        return []

    return filtered_emails


def _get_output_dir() -> Path:
    """Return the configured output directory for generated artifacts."""
    output_dir = get_settings().output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def write_outlook_email_snapshot(
    ticker: str,
    emails: List[Dict[str, Any]],
    output_dir: Path | None = None,
) -> Path:
    """Write collected Outlook emails to the canonical JSON artifact."""
    target_dir = output_dir or _get_output_dir()
    output_path = target_dir / f"{ticker}_sent_emails.json"

    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(emails, handle, indent=4, ensure_ascii=False)

    return output_path


def main():
    """Command-line interface for filtering emails by ticker."""
    try:
        if len(sys.argv) != 2:
            print("Usage: python -m ratio_backend.ingestion.outlook_ticker_search TICKER")
            sys.exit(1)

        ticker = sys.argv[1].upper()
        filtered_emails = filter_emails_by_config(ticker)
        output_file = write_outlook_email_snapshot(ticker, filtered_emails)

        if not filtered_emails:
            print(f"No emails found for '{ticker}'.")
            return

        email_count = len(filtered_emails)
        sender_email = get_sender_email()
        logging.info(f"Email filtering complete. Results saved to {output_file}")
        print(f"\nFound {email_count} sent emails from {sender_email} containing search terms for '{ticker}'")
        print(f"Results saved to: {output_file}")

    except ValueError as ve:
        logging.error(f"Validation Error: {ve}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
