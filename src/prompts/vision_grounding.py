"""Vision grounding prompt (UI-TARS)"""


VISION_GROUNDING_PROMPT = """Please locate the following target element based on the screenshot:

{target_description}

## Task

1. Locate the target element in the screenshot
2. Briefly describe the element you see and its position

!!! VERY IMPORTANT !!! Carefully distinguish between similar elements (e.g. address bar vs search bar in a browser). The one with a magnifying glass icon is usually the search bar. If the target is NOT visible, respond with "Target not found".
"""


def build_vision_grounding_prompt(
    target_description: str
) -> str:
    """Build the vision grounding prompt.

    Args:
        target_description: Description of the target element to locate.

    Returns:
        The formatted prompt string.
    """
    return VISION_GROUNDING_PROMPT.format(
        target_description=target_description
    )


__all__ = ["VISION_GROUNDING_PROMPT", "build_vision_grounding_prompt"]
