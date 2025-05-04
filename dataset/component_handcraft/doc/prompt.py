SELECT_RANGE_PROMPT = """Given the following text:
"{text}"
, find the text in the document and select the range of subset text "{subset_text}".
"""

ACTIVATE_CHAR_PROMPT = """Given the following text:
"{text}"
, find the text in the document and click the {index}th character "{character}" in the text.
"""

ACTIVATE_CHAR_SPACE_PROMPT = """Given the following text:
"{text}"
, find the text in the document and click the space between the continuous character "{character}" and "{character_next}" in the text.
"""
