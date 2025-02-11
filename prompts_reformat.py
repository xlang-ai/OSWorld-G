REFORMAT_PROMPT_COMPONENT = """
Before proceeding, please assess if the instruction is already clear and executable without any further refinement. If the instruction is
- Requires no further inference.  
- Can be executed directly by a human without any prior knowledge about the software.  
then you should **not** modify it and set `refined` to `false`, set `refined_instruction` to `""`. If the instruction needs refining, proceed to the following steps.

The following instruction is a user instruction for interacting with a computer interface:
Instruction: {instruction}

You will be provided with two screenshots:
1. Full Screenshot: A green bounding box marks the target element to help you locate it within the full context of the interface.
2. Cropped Screenshot: A zoomed-in portion of the interface centered around the target element, also marked with a bounding box, to give you a closer view of the element and its immediate surroundings.

### Steps to Refine the Instruction:
Use the two screenshots to rewrite the instruction into a clear, executable description of the target element's position and appearance. Ensure the refined instruction is actionable and precise by following these steps:

1. **Locate the Marked Element**: First, identify the element marked with a green bounding box in the screenshot. The green bounding box is added by me, it is NOT part of the element, so don't mention is when describing this element.  
2. **Verify the Element**: Cross-check the identified element against the original instruction provided to confirm it aligns with the described action or component.  
3. **Refine the Instruction**: Rewrite the instruction to be clear, precise, and executable, specifying:  
   - **Which element to interact with**: Using a standard, recognized, and fundamental method of describing components. (e.g., button name, section label, etc.)
   - **Which part it belongs to**: Clearly specify which application/process and which window it belongs to. (e.g., in the navigation menu of page xxx, in the left sidebar of VSCode, etc.)
   - **How to interact**: In most cases, the interaction is performed by clicking. (e.g., click, type, hover, etc.)

🚨 **Important**: In the refined instruction, DO NOT mention or refer to the "bounding box", "green bounding box", "outline", "green outline", "green rectangle" in any way, even though it was used as part of your reasoning to identify the correct element.  
🚨 **Important**: All "green bounding box", "green outline", "green rectangle" is added by me, it is NOT part of the element, so don't mention them when describing this element(but please mention the element itself in detail), even if it helps you reason.

Ensure that the refined instruction:  
- Requires no further inference.  
- Can be executed directly by a human without any prior knowledge about the software.  

### Example:
- Click the "Keep" button in the popup.  
- Click "Add website" in the current panel "address book."  
- Click "Current layout only" in the left sidebar of the current window.  
- Hover over the 'NEWS' tab in the navigation menu.  

Your output includes `refined_instruction(str)` if you really refined the instruction, and `refined(bool)`. If you believe the original instruction is already clear enough, please do not modify it and set `refined` to `false`. If the instruction was modified, set `refined` to `true`.  
"""

REFORMAT_PROMPT_BABY = """
Before proceeding, please assess if the instruction is clear and executable for someone who has **never used a computer before**. If the instruction:  
- **Does not require any computer-related knowledge or jargon** (e.g., "click," "button," "menu," etc.).  
- **Is actionable using only plain language that assumes no prior experience with computers.**  
then you should **not** modify it and set `refined` to `false`, set `refined_instruction` to `""`. If the instruction needs refining, proceed to the following steps.

The following instruction is a user instruction for interacting with a computer interface:  
Instruction: {instruction}

You will be provided with two screenshots:
1. Full Screenshot: A green bounding box marks the target element to help you locate it within the full context of the interface.
2. Cropped Screenshot: A zoomed-in portion of the interface centered around the target element, also marked with a bounding box, to give you a closer view of the element and its immediate surroundings.

### Steps to Refine the Instruction:
Use the two screenshots to refine the instruction into a UNDERSTANDABLE, ACCURATE, DETAILED AND ACTIONABLE description, so that anyone with **no prior computer experience** can follow the instruction without confusion:  

1. **Locate the Marked Element**: First, identify the element marked with a green bounding box in the screenshot. The green bounding box is added by me, it is NOT part of the element, so don't mention the green bounding box when describing this element, even if it helps you reason.
2. **Verify the Element**: Cross-check the identified element against the original instruction provided to confirm it aligns with the described action or component.  
3. **Refine the Instruction**: Rewrite the instruction to be clear, precise, and executable, avoiding any computer-related jargon or assumptions, and specifying:  
   - **What to do**: Use simple, everyday language to describe the action(Click, Hover, Type, etc.). In most cases click is good enough. 
   - **What it looks like**: Provide clear and specific visual details, which are understandable to someone with **no prior computer experience** to help identify the element, such as its color, shape, size, or any text or symbols on it. DO NOT use any computer-related terms or jargon (e.g., "sidebar", "button", "menu" etc.).
   - **Where it locates**: Clearly describe the detailed element's location and its surroundings in plain language.

The goal is to ensure that even someone with no prior experience using a computer can follow the instruction without confusion. 

🚨 **Important**: In the refined instruction, DO NOT mention or refer to the "bounding box", "green bounding box", "outline", "green outline", "green rectangle" in any way, even though it was used as part of your reasoning to identify the correct element.  
🚨 **Important**: All "green bounding box", "green outline", "green rectangle" is added by me, it is NOT part of the element, so don't mention them when describing this element(but please mention the element itself in detail), even if it helps you reason.

### Examples:
1. Instruction: "Open the dropdown menu and select 'English'."
   Refined Instruction: "Look for the long rectangle with the word 'Select' on it. Tap it, then press 'English' from the list that appears below."
   Refined: True

2. Instruction: "Press the power button on the device."
   Refined Instruction: "Locate the round black button with a white circle and a vertical line in the middle, usually found on the right side of the device, and press it gently."
   Refined: True

3. Instruction: "Click to open the navigation bar at the top."
   Refined Instruction: "Find the row of labels at the very top of the screen, and press the label "navigation"."
   Refined: True

Ensure that the refined instruction:  
- **Requires no further inference.**  
- **Is actionable directly by someone with no computer experience.**  

"""
#   - "Click the green square with your finger"
#   - "Hover on the white circle with a black arrow inside."
#   - "Click the small gray box with the word 'Start' written on it."

#   - "Look for a small blue circle with a white star inside."
#   - "Find the long rectangle with the word 'Continue' in bold black text."
#   - "Locate the red triangle with a white exclamation mark in the center."

#   - "Look for the green box near the top-right corner of the screen."
#   - "Find the square with a red outline inside the area with a yellow background."
#   - "On the leftmost side of the dark area in the middle, distinct from the red background, locate a square slightly offset from the top-right corners of three other squares."

# ### Examples:
# 1. Instruction: "Open the dropdown menu and select 'English'."
#    Refined Instruction: "Look for the long rectangle with the word 'Select' on it. Tap it, then press 'English' from the list that appears below."
#    Refined: True

# 2. Instruction: "Press the power button on the device."
#    Refined Instruction: "Locate the round black button with a white circle and a vertical line in the middle, usually found on the right side of the device, and press it gently."
#    Refined: True

# 3. Instruction: "Click to open the navigation bar at the top."
#    Refined Instruction: "Find the row of labels at the very top of the screen, and press the label "navigation"."
#    Refined: True
