# Using bbox
REFORMAT_PROMPT = """
The following instruction is a user instruction for interacting with a computer interface:
Instruction: {instruction}

Please perform the following steps to refine the instruction into a clear, executable, one-step positional icon component description based on the image you see:  

1. **Locate the Marked Element**: First, identify the element marked with a green bounding box in the image.  
2. **Verify the Element**: Cross-check the identified element against the original instruction provided to confirm it aligns with the described action or component.  
3. **Refine the Instruction**: Rewrite the instruction to be clear, precise, and executable, specifying:  
   - **Which element to interact with** (e.g., button name, section label, etc.).  
   - **Which part it belongs to** (e.g., in the navigation menu, in the sidebar, etc.).  
   - **How to interact** (e.g., click, type, hover, etc.). In most cases, the interaction is performed by clicking.  

🚨 **Important**: In the refined instruction, do not mention or refer to the "green bounding box" in any way, even though it was used as part of your reasoning to identify the correct element.  

Ensure that the refined instruction:  
- Requires no further inference.  
- Can be executed directly by a human without any prior knowledge about the software.  

### Example:
- Click the "Keep" button in the popup.  
- Click "Add website" in the current panel "address book."  
- Click "Current layout only" in the left sidebar of the current window.  
- Hover over the 'NEWS' tab in the navigation menu.  
"""

# Not using bbox
# REFORMAT_PROMPT = """
# The following instruction is a user instruction for interacting with a computer interface:
# Instruction: {instruction}
# Please refine this into a clear, executable, one-step positional icon component description instruction based on the image you see.

# Specify exactly
# - which elements to interact with (e.g., button name, section label, etc.),
# - which part it belongs to (e.g., in the navigation menu, in the sidebar, etc.),
# - how to interact (e.g., click, type, hover, etc.). In most cases, the interaction is performed by clicking.

# Ensure no further inference is needed, and a human can execute it directly without any prior knowledge about the software.

# Example:
# Click the "Keep" button in the popup.
# Click "Add website" in the current panel "address book."
# Click "Current layout only" in the left sidebar of the current window.
# Hover over the 'NEWS' tab in the navigation menu.
# """
