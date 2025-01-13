COMPONENT_PROMPT = """Create a single React component that implements: {component_desc}

Rules:
1. Only provide the component's JavaScript code
2. No external libraries or CSS imports
3. Component must be a functional component
4. Export the component as default

Format your response as JSON:
{{
    "component_code": "<the React component code>"
}}

"""

ACTION_PROMPT = """Generate a PyAutoGUI function to interact with a UI component shown in the screenshot.

Input Information:
1. Action Description: {action_desc}
2. Component Description: {component_desc}
3. Screenshot: An image showing the component's current state
4. Position: The position of the elements in the screenshot, {position}

Task Analysis Process:
1. First identify the key points in the UI that won't change with parameters, for example:
   - For a slider: identify the left and right endpoints
   - For a button: identify its center position
   - For a text box: identify its corners or control points
   You can use the position information to help you identify these key points' position. 
   Note that you should generate these key points in the format of x_name, y_name = x, y. 
   x and y of the same key point should appear together in the same line.

2. Then identify the parameters from the action description:
   - Parameters are marked with <param_name> in the description
   - These will become function parameters
   - Example: "<volume>" in "set volume to <volume>%"

Requirements:
1. Function name must be "action"
2. Define constant coordinates for key UI points first
3. Use parameters from action description as function parameters
4. Include detailed explanation in thought_process

Example Scenarios:

1. Action Description: "Set volume to <volume>%"
   Component Description: "A volume slider"
   Screenshot: An image showing the volume slider
   Position: ```
   {{
  "elements": [
    {{
      "attributes": {{
        "style": "width: 200px; margin: 20px;"
      }},
      "text": "Volume: 50%",
      "isInteractive": false,
      "position": {{  
        "x_left": 20,
        "y_top": 20,
        "x_right": 220,
        "y_bottom": 70,
        "x_center": 120,
        "y_center": 45,
      }}
    }},
    {{
      "attributes": {{
        "min": "0",
        "max": "100",
        "type": "range",
        "value": "50",
        "style": "width: 100%;"
      }},
      "text": "",
      "isInteractive": true,
      "position": {{
        "x_left": 22,
        "y_top": 22,
        "x_right": 222,
        "y_bottom": 38,
        "x_center": 122,
        "y_center": 30,
      }}
    }},
    {{
      "attributes": {{
        "style": "text-align: center; margin-top: 10px;"
      }},
      "text": "Volume: 50%",
      "isInteractive": false,
      "position": {{
        "x_left": 20,
        "y_top": 51,
        "x_right": 220,
        "y_bottom": 69,
        "x_center": 120,
        "y_center": 60,
      }}
    }}
  ]
  "metadata": {{
    "timestamp": "2025-01-11T17:34:50.039Z",
    "totalElements": 3,
    "interactiveElementsCount": 1,
    "viewport": {{
      "width": 1280,
      "height": 720
    }}
  }}
}}
```
   thought_process:
   - Identify the left and right endpoints of the slider using the position information:
     - The left endpoint is (22, 30)
     - The right endpoint is (222, 30)
   - Use the volume parameter to calculate the click position
   action_code:
   def action(volume):
       # Fixed points: slider endpoints
       x_0, y_0 = 22, 30     # Left endpoint of slider
       x_1, y_1 = 222, 30   # Right endpoint of slider
       
       # Calculate click position based on volume parameter
       x = x_0 + (x_1 - x_0) * (volume / 100)
       pyautogui.click(x, y_0)

2. Action Description: "Click the \"CVPR2024\" link in the conferences section on the right side of the screen."
   Component Description: "A conferences section"
   Screenshot: An image showing the conferences section
   Position: ```
   {{
   "elements": [
     {{
       "attributes": {{
         "style": "width: 200px; margin: 20px;"
       }},
       "text": "CVPR2024",
       "isInteractive": true,
       "position": {{ 
            x_left: 20,
            y_top: 20,
            x_right: 220,
            y_bottom: 70,
            x_center: 120,
            y_center: 45,
       }}
     }}
   ]
   }}
   ```
    action_code:
    def action():
        x_0, y_0 = 120, 45
        pyautogui.click(x_0, y_0)

There is no parameter for the click, since the location of this action is fixed.

Your Response Format:
{{
    "thought_process": "Explain:
        1. What key points you identified in the UI
        2. Why you chose these points
        3. How parameters affect the interaction
        4. How you calculate the final coordinates",
    "action_code": "Your PyAutoGUI function"
}}
"""
