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
