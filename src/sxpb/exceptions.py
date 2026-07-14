from lark.exceptions import LarkError

# A mapping from the grammar's technical token names to human-readable descriptions.
TOKEN_TRANSLATIONS = {
    "BARE": "an unquoted word (e.g., key_name)",
    "BOOLEAN": "a boolean (+true or +false)",
    "EMPTY_STRING": "an empty quoted string",
    "ESCAPED_STRING": 'a quoted string (e.g., "hello world")',
    "LPAR": "an opening parenthesis `(`",
    "MULTILINE_STRING": 'a multiline string (e.g., """...""")',
    "NONEMPTY_ESCAPED_STRING": 'a quoted string (e.g., "hello world")',
    "PLAIN": "an unquoted string",
    "RPAR": "a closing parenthesis `)`",
    "SIGNED_NUMBER": "a number (e.g., 123, -4.5, +1e6)",
}


def format_lark_error(e: LarkError, text: str) -> str:
    """Formats a LarkError into a human-readable message."""

    # Get the list of expected tokens, which can be in 'expected' or 'allowed'.
    expected_tokens = getattr(e, "expected", getattr(e, "allowed", None))

    # Build the main error message.
    if hasattr(e, "char"):
        # UnexpectedCharacters or UnexpectedToken
        token = getattr(e, "token", None)
        found = (
            f"'{token.value}'" if token else f"character '{getattr(e, 'char', '?')}'"
        )
        message = f"Found an unexpected {found}."
    else:
        # This will catch UnexpectedEOF and other LarkErrors without a specific character.
        message = "Unexpected end of input."

    # Add context from the original text.
    get_context = getattr(e, "get_context", None)
    context = get_context(text) if callable(get_context) else ""
    if context:
        message += f"\n\n{context}"

    # Add the list of what was expected.
    if expected_tokens:
        message += "\n\nExpected one of the following:\n"
        for token_name in sorted(expected_tokens):
            description = TOKEN_TRANSLATIONS.get(token_name, token_name)
            message += f"  - {description}\n"

    return message
