---
name: IMAP RFC Compliance Guidelines
description: Rules and best practices for writing RFC-compliant IMAP search queries and maintaining test mock fidelity.
---

# IMAP RFC Compliance Guidelines

This skill provides guidelines and patterns to ensure that any IMAP connection, search query, or fetch command implemented in this repository is strictly compliant with the standard IMAP RFC specifications (e.g., RFC 3501).

## Guidelines & Best Practices

### 1. SEARCH vs. FETCH Command Syntax
Do not confuse or mix up `SEARCH` criteria keys with section or body specifiers meant for the `FETCH` command.
* **Incorrect (`SEARCH` query)**: `BODY[TEXT] "value"`
* **Correct (`SEARCH` query)**: `BODY "value"` or `TEXT "value"`

### 2. Valid IMAP SEARCH Keys
The following are the standard keys defined in RFC 3501 for search criteria:
* `BODY <string>`: Messages that contain the specified string in the body of the message.
* `TEXT <string>`: Messages that contain the specified string in the header or body of the message.
* `SUBJECT <string>`: Messages that contain the specified string in the Subject header.
* `FROM <string>`: Messages that contain the specified string in the From header.
* `HEADER <field-name> <string>`: Messages that contain the specified string in the header with the specified field-name.

### 3. Parentheses & Logical Query Grouping
* Keep grouping simple and compliant.
* **Yahoo / AOL IMAP Exception**: Yahoo and AOL IMAP servers require the entire search criteria string to be enclosed in a single pair of outer parentheses (e.g., `(FROM "example@domain.com" SUBJECT "Delivery")`). The `build_search` utility implements this via the `is_yahoo=True` flag.

### 4. Code Utilities Reference
Always use the centralized query-building utility rather than manually constructing search queries:
* **Function**: `build_search(address: list, date: str, subject: str | list[str] = "", body: str | list[str] = "", header: str = "", is_yahoo: bool = False)`
* Located in: [imap.py](file:///home/firstof9/github/Home-Assistant-Mail-And-Packages/custom_components/mail_and_packages/utils/imap.py)

#### Centralized Search String Sanitization
Always sanitize search terms to strip double quotes and normalize non-ASCII characters to ensure compatibility with ASCII-only IMAP servers (like Microsoft Exchange):
* Use `clean_search_string(val: str) -> str` from [imap.py](file:///home/firstof9/github/Home-Assistant-Mail-And-Packages/custom_components/mail_and_packages/utils/imap.py).

### 5. Test Mock Fidelity
Ensure all IMAP mock objects (such as mock connections or mock responses in `tests/`) emulate standard IMAP server behaviors:
* Verify that test mocks explicitly assert that the generated search query uses correct keys (like `BODY` instead of `BODY[TEXT]`).
* Do not write mocks that silently succeed on incorrect syntax.
* Refer to [test_imap_email.py](file:///home/firstof9/github/Home-Assistant-Mail-And-Packages/tests/utils/test_imap_email.py) for examples of standard search string assertion assertions.

### 6. Batch UID FETCH Formatting & Line Safety
To minimize network round-trips over high-latency TLS connections, use multi-UID batch fetching when verifying subjects or headers across multiple candidate emails:
* **Syntax**: Format sequence sets as comma-separated UIDs without spaces: `UID FETCH <uid1>,<uid2>,... (BODY[HEADER.FIELDS (SUBJECT)])`.
* **Utility**: Use `email_fetch_headers_batch(account, nums)` from [imap_fetch.py](file:///home/firstof9/github/Home-Assistant-Mail-And-Packages/custom_components/mail_and_packages/utils/imap_fetch.py).
* **Chunking Limits**: Cap batch fetches at `_MAX_HEADER_CHUNK = 50` UIDs per command to prevent IMAP command line buffer overflows on strict servers.
* **Fallback**: Always handle partial batch responses or protocol exceptions gracefully by falling back to scalar single-message fetching.

### 7. Batch Test Mock Fidelity
When mocking IMAP responses for batch queries in `tests/`:
* Emulate real server response structure: batch FETCH responses alternate between header tuple lines (`(b"* <seq> FETCH (UID <num> ...)", b"Header: ...\r\n\r\n")`) and byte closing delimiters (`b")"`).
* Header bodies in test mocks must include standard RFC line terminations (`\r\n\r\n`) so Python's `email.message_from_bytes` can parse message fields correctly.
* Verify both happy paths and edge cases (e.g. servers omitting requested UIDs from the batch response, raw byte lines, and network timeouts).

### 8. Persistent Email Caching
All email fetch calls (`email_fetch`, `email_fetch_headers`, `email_fetch_text`) should be routed through `EmailCache.fetch()`:
* Cache keys store distinct payload sections via `f"{eid_str}:{parts}"`.
* Raw byte structures must be preserved across storage operations using `latin-1` encoding (see [email_cache_architecture](file:///home/firstof9/github/Home-Assistant-Mail-And-Packages/.agents/skills/email_cache_architecture/SKILL.md)).
* For batch checks, probe cached headers first via `EmailCache.get_cached()` and store newly verified batches via `EmailCache.store()`.
