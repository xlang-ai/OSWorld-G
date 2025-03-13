visual_description_templates = [
    "This {element_type} element can be described as follows:\n\nVisual Description: {visual_description}",
    "The visual appearance of this {element_type} is as follows:\n\nVisual Description: {visual_description}",
    "Let me describe the visual characteristics of this {element_type}:\n{visual_description}",
    "Here's what this {element_type} looks like:\n{visual_description}",
    "Visual appearance details of the {element_type}:\n{visual_description}",
    "The {element_type}'s visual characteristics are as follows:\n{visual_description}",
    "Visually, this {element_type} can be described as:\n{visual_description}",
    "Looking at this {element_type}, we can observe:\n{visual_description}",
    "The visual attributes of this {element_type} are:\n{visual_description}",
    "Visual features of the {element_type}:\n{visual_description}",
    "Here's a detailed visual description of the {element_type}:\n{visual_description}",
    "The {element_type}'s appearance can be described as:\n{visual_description}",
]

position_information_templates = [
    "The position of this {element_type} can be described as:\n{position_information}",
    "Location details of the {element_type}:\n{position_information}",
    "This {element_type} is positioned as follows:\n{position_information}",
    "Regarding the {element_type}'s position:\n{position_information}",
    "The spatial layout of this {element_type}:\n{position_information}",
    "In terms of the {element_type}'s positioning:\n{position_information}",
    "The {element_type}'s location can be described as:\n{position_information}",
    "Spatial context of the {element_type}:\n{position_information}",
    "Here's where the {element_type} is located:\n{position_information}",
    "The {element_type}'s placement in the interface:\n{position_information}",
    "Positional details of the {element_type}:\n{position_information}",
    "Location and arrangement of this {element_type}:\n{position_information}",
]

element_function_templates = [
    "The functionality of this {element_type}:\n{element_function}",
    "This {element_type} serves the following purpose:\n{element_function}",
    "The {element_type}'s intended function:\n{element_function}",
    "How this {element_type} works:\n{element_function}",
    "Functional description of the {element_type}:\n{element_function}",
    "This {element_type}'s purpose and usage:\n{element_function}",
    "The role of this {element_type}:\n{element_function}",
    "Regarding the {element_type}'s functionality:\n{element_function}",
    "What this {element_type} does:\n{element_function}",
    "Usage and purpose of this {element_type}:\n{element_function}",
    "Functional capabilities of the {element_type}:\n{element_function}",
    "This {element_type} allows users to:\n{element_function}",
]

DESC_INST_SYS_PROMPT = """
You are analyzing an application layout image where a specific UI element is highlighted in red bounding box, with the center of the box marked with a red dot.

You'll receive both the full layout image and a cropped image of the highlighted element. And you will also receive a context image, which is the region of the full image that contains the red bounding box highlighting the element and the red dot marking the center of the box.

You will also receive tree-like position information in JSON format, which helps you better understand the position of the element in the layout.

Remember, the target element may not be completely visible, it may be hidden or truncated, you need to consider this and use it in "Element completeness" session.

As an experienced designer, provide a clear description of this element that would help developers, designers, and general users locate and understand it without relying on any highlighting.
You CAN find the distinctive features of the element, describe the relationship between the element and other distinct elements, etc. Be creative, and find the most effective way to describe the element.

Please, analyze the following aspects:

### 1. Visual Description
Describe the element's visual characteristics, including:
- Geometric composition
- Colors and styling
- Visual context within the interface
- Any notable design patterns or features

### 2. Position Information
Describe the element’s location with respect to:
Numbering parallel elements: If the element is one of multiple similar elements (e.g., rating stars, buttons, or list items), you must specify its exact position among them. For rating buttons, explicitly state which star (or other rating icon) this element represents. Use the provided position information, including the bounding box (bbox) and parent-child structure to determine its position relative to its siblings.
Overall screen placement: Specify its position on the screen (e.g., top-right corner).
Surrounding UI components: Identify adjacent or related UI elements.
Parent containers or groups: Indicate which parent element or group it belongs to.
Position within structured layouts: If the element is part of a list, table, or grid, specify its order or location.

### 3. Element Function
Detail the element's purpose and interaction methods:
- Primary functionality
- Expected user interactions
- Resulting actions or behaviors
- Common use cases

### 4. Element Type
Identify the specific UI component type, such as:
- Button
- Text input
- Dropdown menu
- Checkbox
- Toggle switch
- Scrollbar
- Other standard UI elements

### 5. Possible Action
Identify the list of specific actions that can be performed on THE CENTER of this element, which is marked with red dot, such as:
- click the star to rate it
- doubleClick the element the select the element
- rightClick the box to open a context menu
- drag this element to another location
- hover on this element
- write something

### 6. Element Complete Visibility Analysis (`element_complete_visibility_analysis`)
Assess whether the element is completely visible, give your analysis process in `element_complete_visibility_analysis` and give the final answer in `element_complete_visibility_result`:

- If the element is not fully visible for any of these reasons:
  - It is partially truncated or part of a larger component (which happens often)
  - The image doesn't align well with your description (image shows element A but description mentions element B)
  - The element is partially hidden by other elements
  - The element is not visible at all
  - The bounding box does not fit tightly around the target element, with significant padding between them
  Then answer False in Element Visibility Result (`element_complete_visibility_result`)

- If the element is absolutely, fully visible, answer True in Element Visibility Result (`element_complete_visibility_result`)

### 7. Element Atomicity Analysis (element_atomicity_analysis)
Assess whether the element represents a single cohesive component, give your analysis in `element_atomicity_analysis` and give the final answer in `element_atomicity_result`:

- If the bounding box contains multiple distinct elements that should be considered separate (rather than a single cohesive component), answer False in Element Atomicity Result (`element_atomicity_result`)

- If the element represents a single cohesive component (not multiple independent elements grouped together), answer True in Element Atomicity Result (`element_atomicity_result`)

Additional Context:
You'll receive a metadata called element information: A dict containing information including the role, title, value, identifier, description, help, path of this element. The MAY OR MAY NOT be useful for your analysis.
   
Keep descriptions concise and focused.

Important: 
**NEVER** reference any highlighting or bounded areas in your description. Check the cropped image for the original look of the component. Sometimes a checkbox is wrapped by a red bounding box, but the checkbox itself is not red, which you can see in the cropped image.
Make every sentence to the point and concise, don't use vague words like "specific area" and "certain region", etc.
Again, the user should be able to find the element even without the bounding box, you need to find the distinctive features of the element, describe the relationship between the element and other distinct elements, etc. Among the five analytical aspects, EACH ONE must be UNIQUE, ensuring that users can uniquely identify our target element based on any single aspect alone. 
For multiple elements of the same type, you need to pay special attention to describing the characteristics of each element compared to other elements of the same type.
Grasp the info that you seen, if you know the title, say the title, if you know the user name, say the user name, if you find some distinctive text, say the text.
"""

DESC_INST_USER_PROMPT = """
The bounded image, cropped image and context image are provided in the following prompt.

The target element is:
{bbox}

The parent element of the target element, along with the children of this parent element are:
{parent_bbox}

Use parent element and its children to determine the relative position of the target element.
"""

DESC2ACTION_SYS_PROMPT = """
## Task
Generate precise action descriptions and corresponding code for UI elements based on provided details.

## Input Information
You will be provided with:
1. **Detailed Element Description** - Visual and functional details of a specific UI element
2. **Brief Action Description** - A short description of the action to perform
3. **Center Point Coordinates** - The exact x,y coordinates of the target element's center

## Your Outputs

### 1. Action Description
Create a clear, specific action description that:
- Uniquely identifies the target element using details from the element description
- Incorporates the brief action description
- Is concise yet unambiguous

### 2. Action Code
Generate executable code following this exact grammar:

```python
pyautogui.click(center_x, center_y)
pyautogui.doubleClick(center_x, center_y)
pyautogui.rightClick(center_x, center_y)
pyautogui.moveTo(center_x, center_y)
pyautogui.dragTo(center_x, center_y)
pyautogui.drag(dx, dy)
pyautogui.write("text")
```

Where:
- `center_x` and `center_y` are the provided coordinates
- `dx` and `dy` are float/int values for drag distance
- `text` is a string for text input actions

## Requirements
- Ensure the action description uniquely identifies the element
- Use only the provided PyAutoGUI functions with exact syntax
- Match the action type to the element's functionality
- Use only the provided center point coordinates for targeting
"""

DESC2ACTION_USER_PROMPT = """
The element description, action type, center point of the bounding box are provided in the following prompt.

Element Description:
{element_desc}

Action Brief Description:
{action_brief_desc}

Center Point of the Bounding Box:
{center_point}
"""

FINE_ACTION_INST_SYS_PROMPT = """
You're an UI Component Interaction Generator. You need to fugure out whether the target element has a continuous action space, and generate action function if the action space is continuous.

You'll receive both the full layout image and a cropped image of the highlighted element. And you will also receive a context image, which is the region of the full image that contains the red bounding box highlighting the element and the red dot marking the center of the box.

You will also receive tree-like position information in JSON format, which helps you better understand the position of the element in the layout.

Remember, the target element may not be completely visible, it may be hidden or truncated, you need to consider this and use it in "Element completeness" session.

## Generate Action
Based on the action space type and action intent, generate appropriate action specifications of action intent. The action should contain:

1. Element Completeness Analysis(element_completeness_analysis)
Assess whether the element is complete, give your analysis process in `element_completeness_analysis` and give the final answer in `element_completeness_result`:
- If 
    - it is partially truncated or part of a larger component(which happens often), 
    - or the image doesn't align well with your description(image shows element A but description mentions element B),
    - or the element is partially hidden by other elements, 
    - or the element is not visible at all,
    - or the bounding box consists of more than one elements,
    please, answer False in Element Completeness Result(element_completeness_result)
- If it is absolutely, fully visible, answer True in Element Completeness Result(element_completeness_result)

If `element_completeness_result` is False, you should not generate following aspects:

    - Action Description
    - Action Code
    - Action Space Type
    - Action Continuous Interval
    - Action Discrete Values
    - Action Parameters
    - Thought Process
Return None for all of them.

2. **Determine Whether the action space is continuous** (`is_continuous`)
ALL SLIDERS have continuous action space!!!
Analyze and determine the whether there are infinite possible meaningful actions within a range for this Element (In most cases the action space isn't continuous! Example of continuous action space: dragging a slider to any position). Output True/False for this aspect.

3. **Thought Process** (`thought_process`)
    - If the action space is continuous, give corresponding action description for the action
    - Identify key UI points that remain constant, for example:
        * Component endpoints (for sliders)
        * Center positions (for buttons)
        * Control points (for resizable elements)
    - Continuous actions' value ranges aren't necessarily 0-100; they could also be -10-40 (temperature), 0-24 hours (time), etc. You need to determine these value ranges based on the screenshot and position information.
    - Document points using format: `x_name, y_name = x, y`
    - Explain calculation logic
    - Identify and explain parameters from action description
    - The action must be completed in one step! Actions like "Set the startand end values of the sliders to 15 and 12 respectively." is not a valid action.

4. **Action Description** (`action_desc`)
   - Describe what the action does, which serves as the instantiation/implementation of the action intent.
   - Should not describe actions that require prior interactions.
   - The description should be clear enough
   - Use `<param_name>` format for variable parameters

5. **Action Params** (`action_params`)
   - List of all parameter names for the action

6. **Action Continuous Interval** (`action_continuous_interval`)
   - List of interval for all possible parameter values for continuous action spaces, not {{}} only when action_space_type is "continuous".
   - Use a dictionary to represent the interval, with the key as the parameter name(e.g. "volume") and the value as the list of intervals(e.g. [(0, 30), (60, 100)]). The interval should be a tuple of two numbers, representing the lower and upper bounds of the interval. Most of the time, one interval is enough, but more than one interval is possible.

7. **Action Code** (`action_code`)
   - Function name must be `action`
   - Define constant coordinates first
   - Use PyAutoGUI only
   - For discrete or continuous action spaces: Implement variable parameters using `<param_name>` format
   - Use singleclick action whenever possible and suitable.

## Examples

### Example 1: Volume Slider
**Input:**
- Component Name: "A volume slider"
- Screenshot: An image showing the volume slider
- Action Intent: "Set volume"
- Position: 
```
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
}}
```
**Output:**
```json
{{
    "action_space_type": "continuous",
    "action_desc": "Set volume to <volume>%",
    "thought_process": "
        - Identified slider endpoints: (22,30) and (222,30)
                - Volume parameter determines click position
                - Linear interpolation between endpoints based on volume",
    "action_params": ["volume"],
    "action_discrete_values": {{}},
    "action_continuous_interval": {{"volume": [(0, 100)]}},
    "action_code": "
        def action(volume):
            x_0, y_0 = 22, 30  # Left endpoint
            x_1, y_1 = 222, 30  # Right endpoint
            x = x_0 + (x_1 - x_0) * (volume / 100)
            pyautogui.click(x, y_0)"
}}
```

### Example 2: Temperature Slider
**Input:**
- Component Name: "A temperature slider"
- Screenshot: An image showing the temperature slider
- Action Intent: "Set temperature"
- Position: 
```
{
  "elements": [
    {
      "attributes": {
        "style": "width: 250px; margin: 20px;"
      },
      "text": "Temperature: 20°C",
      "isInteractive": false,
      "position": {  
        "x_left": 25,
        "y_top": 25,
        "x_right": 275,
        "y_bottom": 75,
        "x_center": 150,
        "y_center": 50,
      }
    },
    {
      "attributes": {
        "min": "-10",
        "max": "40",
        "type": "range",
        "value": "20",
        "style": "width: 100%;"
      },
      "text": "",
      "isInteractive": true,
      "position": {
        "x_left": 27,
        "y_top": 27,
        "x_right": 277,
        "y_bottom": 43,
        "x_center": 152,
        "y_center": 35,
      }
    },
    {
      "attributes": {
        "style": "display: flex; justify-content: space-between; margin-top: 5px;"
      },
      "text": "-10°C                                                   40°C",
      "isInteractive": false,
      "position": {
        "x_left": 25,
        "y_top": 56,
        "x_right": 275,
        "y_bottom": 74,
        "x_center": 150,
        "y_center": 65,
      }
    }
  ]
}
```
**Output:**
```json
{
    "action_space_type": "continuous",
    "action_desc": "Set temperature to <temperature>°C",
    "thought_process": "
        - Identified slider endpoints: (27,35) and (277,35)
        - Range is from -10°C to 40°C (not 0-100)
        - Temperature parameter determines click position
        - Linear interpolation between endpoints based on temperature value",
    "action_params": ["temperature"],
    "action_discrete_values": {},
    "action_continuous_interval": {"temperature": [(-10, 40)]},
    "action_code": "
        def action(temperature):
            x_0, y_0 = 27, 35  # Left endpoint
            x_1, y_1 = 277, 35  # Right endpoint
            # Map temperature from range -10 to 40 to position
            x = x_0 + (x_1 - x_0) * ((temperature - (-10)) / (40 - (-10)))
            pyautogui.click(x, y_0)"
}
```

"""

FINE_ACTION_INST_USER_PROMPT = """
The bounded image, cropped image and context image are provided in the following prompt.

The target element's bounding box is:
{bbox}
"""

ACTION_INTENT_PROMPT = """You are an assistant with deep knowledge of UI component functionality. Your task is to analyze a component's current state and generate a comprehensive list of possible user interactions, grouped by similar action types.

Input:
- Component name: {component_name}
- Component code: {component_code}
- Screenshot: showing component's current state and properties


Requirements:
1. Return an empty list if an error message like "Compiled with problems" appears on the screen or if the screen is obstructed by red error messages.
2. When considering all possible interactions, focus more on actions directly related to the component: {component_name}.
3. Carefully read the component code to understand its functionality and interaction logic.
4. Ensure all interactions align with the actual usage of the components. Verify the action's feasibility by reviewing the screenshot, and ensure your intended actions are consistent with what is visually observable on the screen.
5. Group similar actions together and avoid including overly repetitive or redundant action intents.
6. Propose actions for both interactive and non-interactive elements (such as text, images, etc.). You can double-click on text, drag parts of text, or click on images, for example.
7. Each interaction should be completed in a single step. Do not combine multiple steps or targets in one action (e.g., you cannot click multiple buttons in one action).
8. Pay close attention to fine-grained operations.
9. Be mindful of the impact of each action. For instance, if you want to select a word, drag or double-click the word. Simply clicking a word without a link may not have any effect.
10. Describe your action in various aspects including
  1. Function-based description: Focuses on the action’s purpose or effect.
    Example: "Click the close button", "Click the submit button".
  2. Index-based description: Refers to the item’s position in a list or menu.
    Example: "Click the 3rd item in the menu", "Select the 2nd checkbox".
  3. Visual-based description: Uses color, shape, or location to identify the element.
    Example: "Click the red button at the bottom-right", "Click the blue link at the top".
  4. Contextual description: Describes based on surrounding elements or context.
    Example: "Click the button next to the text field", "Select the option in the 'Settings' menu".

Output Format:
{{
    "action_intent_list": [
        "<category_1>",
        "<category_2>",
        "<category_3>",
        "<category_4>"...
    ]
}}

Example for a FloatingActionButtonZoom Group:
{{
    "action_intent_list": [
        "Select different items",
        "Select part or all of the displayed text",
        "Click floating action button"
    ]
}}
"""

ACTION_DETAIL_PROMPT = """ You're an UI Component Interaction Generator. You're given a component's name, screenshot, and position data. You need to generate 3 different interactions for the component.

## Input
1. **Component Name**, The name of the UI component: {component_name}
2. **Screenshot**, An image showing the component's current state.
3. **Action Intent**, A possible user interaction intent category for the component: {action_intent}
4. **Position Data**, JSON object containing the positions of all elements: {position}
5. **Component code**, The code of this component:{component_code}


## Generate Action
Based on the action space type and action intent, generate appropriate action specifications of action intent. The action should contain:

1. **Thought Process** (`thought_process`)
   - Recall the action intent
   - Think if this action intent is executable in the current state of the component, think if this actions brings the expected interaction effect based on the component code.
   - If not, set action space type to "none" and generate empty action_desc and action_code.
   - If yes, give corresponding action description for the action intent
    - Identify key UI points that remain constant, for example:
        * Component endpoints (for sliders)
        * Center positions (for buttons)
        * Control points (for resizable elements)
    - Document points using format: `x_name, y_name = x, y`
    - Explain calculation logic
    - For discrete or continuous action spaces: Identify and explain parameters from action description

2. **Determine Action Space Type** (`action_space_type`)
Analyze and determine the type of action space for this interaction:
- **None**: No action space exists
- **Unique**: Only one possible action exists (e.g., clicking a button - note: clicking different parts of the same button doesn't count as different actions)
- **Discrete**: Limited/unlimited set of distinct possible actions (e.g., selecting from a list of options)
- **Continuous**: Infinite possible actions within a range (e.g., dragging a slider to any position)

If the action space type is "none", you should generate empty action_desc and action_code, but generate thought_process to explain why the action space type is "none".

3. **Action Description** (`action_desc`)
   - Describe what the action does, which serves as the instantiation/implementation of the action intent.
   - You should only interact with elements that are visible on the screen.
   - Should not describe actions that require prior interactions.
   - The description should be clear enough
   - For discrete or continuous action spaces: Use `<param_name>` format for variable parameters
   - The instructions you provide should be unambiguous and clear
   - after incorporating the possible action parameters, the instructions should point to only one action and one goal.
   - You can use the accompanying position information as context but focus more on what is visually observable when giving your aciton description. Avoid directly referencing position attributes(eg. position 12, index 3); instead, interpret their possible visual implications if they can be inferred from the image.
   - You need to pay particular attention to fine-grained operations. 
    {fine_grained_examples}

4. **Action Params** (`action_params`)
   - List of all parameter names for the action, not [] only when action_space_type is "discrete" or "continuous"
   - DO NOT create more than 2 parameters!!!

5. **Action Discrete Values** (`action_discrete_values`)
   - List of all possible parameter values for discrete action spaces, not {{}} only when action_space_type is "discrete".
   - Use a dictionary to represent the parameter values, with the key as the parameter name(e.g. "volume") and the value as the list of parameter values(e.g. [0, 30, 60, 100]).

6. **Action Continuous Interval** (`action_continuous_interval`)
   - List of interval for all possible parameter values for continuous action spaces, not {{}} only when action_space_type is "continuous".
   - Use a dictionary to represent the interval, with the key as the parameter name(e.g. "volume") and the value as the list of intervals(e.g. [(0, 30), (60, 100)]). The interval should be a tuple of two numbers, representing the lower and upper bounds of the interval. Most of the time, one interval is enough, but more than one interval is possible.

7. **Action Code** (`action_code`)
   - Function name must be `action`
   - Define constant coordinates first
   - Use PyAutoGUI only
   - For discrete or continuous action spaces: Implement variable parameters using `<param_name>` format
   - Use singleclick action whenever possible and suitable.

## Examples

### Example 1: Volume Slider
**Input:**
- Component Name: "A volume slider"
- Screenshot: An image showing the volume slider
- Action Intent: "Set volume"
- Position: 
```
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
}}
```
**Output:**
```json
{{
    "action_space_type": "continuous",
    "action_desc": "Set volume to <volume>%",
    "thought_process": "
        - Identified slider endpoints: (22,30) and (222,30)
                - Volume parameter determines click position
                - Linear interpolation between endpoints based on volume",
    "action_params": ["volume"],
    "action_discrete_values": {{}},
    "action_continuous_interval": {{"volume": [(0, 100)]}},
    "action_code": "
        def action(volume):
            x_0, y_0 = 22, 30  # Left endpoint
            x_1, y_1 = 222, 30  # Right endpoint
            x = x_0 + (x_1 - x_0) * (volume / 100)
            pyautogui.click(x, y_0)"
}}
```

### Example 2: Rating Component
- Component Name: "A rating component"
- Screenshot: An image showing the rating component
- Action Intent: "Set rating"
- Position: 
{{
    "elements": [
        {{
            "text": "★★★★★",
            "isInteractive": "False",
            "position": {{
                "x": 0,
                "y": 0,
                "width": 1280,
                "height": 28
            }}
        }},
        {{
            "text": "★",
            "isInteractive": "False",
            "position": {{
                "x": 578.859375,
                "y": 0,
                "width": 24.453125,
                "height": 28
            }}
        }},
        {{
            "attributes": {{
                "data-testid": "star-1",
                "style": "cursor: pointer; color: gold; font-size: 24px;"
            }},
            "text": "★",
            "isInteractive": "False",
            "position": {{
                "x_left": 603.3125,
                "y_top": 0,
                "x_right": 627.765625,
                "y_bottom": 28,
                "x_center": 615.5390625,
                "y_center": 14,
            }}
        }},
        {{
            "attributes": {{
                "data-testid": "star-2",
                "style": "cursor: pointer; color: gold; font-size: 24px;"
            }},
            "text": "★",
            "isInteractive": "False",
            "position": {{
                "x_left": 627.765625,
                "y_top": 0,
                "x_right": 652.21875,
                "y_bottom": 28,
                "x_center": 640.4453125,
                "y_center": 14,
            }}
        }},
        {{
            "type": "span",
            "path": "div > span",
            "attributes": {{
                "data-testid": "star-3",
                "style": "cursor: pointer; color: gold; font-size: 24px;"
            }},
            "text": "★",
            "position": {{
                "x_left": 652.21875,
                "y_top": 0,
                "x_right": 676.671875,
                "y_bottom": 28,
                "x_center": 664.4453125,
                "y_center": 14,
            }}
        }},
        {{
            "attributes": {{
                "data-testid": "star-4",
                "style": "cursor: pointer; color: gray; font-size: 24px;"
            }},
            "text": "★",
            "isInteractive": "False",
            "position": {{
                "x_left": 676.671875,
                "y_top": 0,
                "x_right": 701.124375,
                "y_bottom": 28,
                "x_center": 688.898125,
                "y_center": 14,
            }}
        }}
        {{
            "attributes": {{
                "data-testid": "star-5",
                "style": "cursor: pointer; color: gray; font-size: 24px;"
            }},
            "text": "★",
            "isInteractive": "False",
            "position": {{
                "x_left": 701.124375,
                "y_top": 0,
                "x_right": 725.5775,
                "y_bottom": 28,
                "x_center": 713.35125,
                "y_center": 14,
            }}
        }}
    ]
}}

**Output:**
```json
{{
    "action_space_type": "discrete",
    "action_desc": "Set rating to <rating> stars",
    "thought_process": "
        - Identified star endpoints: (615.5390625,14), (640.4453125,14), (664.4453125,14), (688.898125,14), (713.35125,14)
                - Rating parameter determines click position
                - Linear interpolation between endpoints based on rating",
    "action_params": ["rating"],
    "action_discrete_values": {{"rating": [1, 2, 3, 4, 5]}},
    "action_continuous_interval": {{}},
    "action_code": "
        rating = [1, 2, 3, 4, 5] # make sure to list all possible actions beforehand
        def action(rating):
            x_0, y_0 = 615.5390625, 14  # Left endpoint
            x_1, y_1 = 640.4453125, 14
            x_2, y_2 = 664.4453125, 14
            x_3, y_3 = 688.898125, 14
            x_4, y_4 = 713.35125, 14
            x = [x_0, x_1, x_2, x_3, x_4]
            y = [y_0, y_1, y_2, y_3, y_4]
            pyautogui.click(x[rating-1], y[rating-1])
            "
}}
```

### Example 3: Click on the submit button
- Component Name: "A submit button"
- Component Description: "Submit buttons are used to confirm actions or submit forms. They are typically found at the bottom of forms or dialogs."
- Screenshot: An image showing the submit button
- Action Intent: "Submit"
{{
    "elements": [
        {{
            "text": "submit",
            "isInteractive": "True",
            "position": {{
                "x_left": 600,
                "y_top": 200,
                "x_right": 700,
                "y_bottom": 250,
                "x_center": 650,
                "y_center": 225
            }}
        }}
    ]
}}

**Output:**
```json
{{
    "action_space_type": "unique",
    "action_desc": "Click on the submit button",
    "thought_process": "
        - Identified button position: (650, 225)
        - Click on the button",
    "action_params": [],
    "action_discrete_values": {{}},
    "action_continuous_interval": {{}},
    "action_code": "pyautogui.click(650, 225)"
}}
```

## Important Notes
- Only use current state information
- Ensure coordinates match the position data provided
"""

ACTION_GROUNDING_PROMPT = """You are an assistant skilled at understanding pyautogui code. I will provide you with an action_detail, and based on it, you will generate an instruction and a pyautogui_action. The instruction represents what the user intends to do, and the pyautogui_action is the corresponding pyautogui code.

Specifically, the action_detail contains the following information:
- **thought_process**: The reasoning behind the action.
- **action_space_type**: The type of action space, which could be "none", "unique", "discrete", or "continuous".
- **action_desc**: A description of the action.
- **action_params**: The parameters for the action.
- **action_discrete_values**: The discrete parameters for the action's params, applicable when the action_space_type is "discrete".
- **action_continuous_intervals**: The continuous intervals for the action's params, applicable when the action_space_type is "continuous".
- **action_code**: The pyautogui code that corresponds to the action.

Your task is to generate the action's grounding based on the action_space_type:
- **For "unique"**: Directly generate one instruction and one pyautogui_action.
- **For "discrete"**: For each discrete parameter in action_discrete_params, generate an instruction and pyautogui_action by substituting the parameter into the action_desc and action_code.
- **For "continuous"**: Based on the thought_process and action_desc, randomly generate three reasonable values, substitute them into the action_desc and action_code, and generate three sets of instruction and pyautogui_action.

**Important note**: The values used in the `pyautogui_action` (such as coordinates, durations, etc.) must be constants, derived from evaluating the code, not variables. When extracting the values for the pyautogui actions, ensure they are fixed numbers (constants) instead of symbolic variables.

The provided action_detail will be as follows:
{action_detail}

Your Response Format:
{{
    "action_grounding_list": [
        {{
            "instruction": "The user input instruction",
            "pyautogui_action": "The corresponding pyautogui code with constants"
        }},
        {{
            "instruction": "The user input instruction",
            "pyautogui_action": "The corresponding pyautogui code with constants"
        }},
        {{
            "instruction": "The user input instruction",
            "pyautogui_action": "The corresponding pyautogui code with constants"
        }},
        ...
    ]
}}
"""


DESC_PROMPT = """Generate a `component_description` for each component. The description should be detailed and accurately describe its appearance and composition so that a front-end engineer can write the corresponding code based solely on this description without adding any additional information. 

Example:
"A rating component with 5 stars, where 4 stars are selected by default",
"A volume control slider that allows users to adjust the volume by clicking or dragging",
"A PowerPoint-style text box where users can resize or move it by dragging its eight control points on edges and corners",

Input Information:
1. Component: {component_type}

Your Response Format:
{{
    "component_desc": "Your description for the component",
}}
"""

COMPONENT_TYPE_LIST = [
    "Autocomplete - Provides a list of suggestions as the user types.",
    "Button - Triggers an action or event.",
    "Button Group - Groups multiple buttons together.",
    "Checkbox - Allows selection of multiple options from a set.",
    "Floating Action Button - A circular button for primary actions.",
    "Radio Group - Allows selection of a single option from a set.",
    "Rating - Enables users to provide a star rating.",
    "Select - Dropdown menu for selecting options.",
    "Slider - Adjusts values within a range by sliding a thumb.",
    "Switch - Toggles between two states, such as on and off.",
    "Text Field - Input field for text entry.",
    "Transfer List - Moves items between two lists.",
    "Toggle Button - Group of buttons that can be toggled on or off.",
    "Avatar - Displays user profile images or initials.",
    "Badge - Shows a small badge to indicate status or counts.",
    "Chip - Represents complex entities in a compact form.",
    "Divider - Separates content into clear groups.",
    "Icons - Provides a set of material design icons.",
    "Material Icons - Collection of Google's Material Design icons.",
    "List - Displays a list of items.",
    "Table - Organizes data into rows and columns.",
    "Tooltip - Displays informative text when hovering over an element.",
    "Typography - Applies consistent styling to text elements.",
    "Alert - Displays important messages or notifications.",
    "Backdrop - Dimmed background to focus attention on a foreground element.",
    "Dialog - Modal window to display content or prompt user actions.",
    "Progress - Indicates loading or ongoing processes.",
    "Skeleton - Placeholder to display while content is loading.",
    "Snackbar - Temporary notification messages.",
    "Accordion - Expands and collapses content sections.",
    "App Bar - Toolbar for application branding and navigation.",
    "Card - Container for content and actions related to a single subject.",
    "Paper - Material design paper background for elements.",
    "Bottom Navigation - Navigation bar at the bottom of the screen.",
    "Breadcrumbs - Indicates the current page’s location within a hierarchy.",
    "Drawer - Sidebar for navigation links or content.",
    "Link - Navigational hyperlink.",
    "Menu - Displays a list of choices on temporary surfaces.",
    "Pagination - Controls for navigating through paginated data.",
    "Speed Dial - Quick access to primary actions.",
    "Stepper - Guides users through multi-step processes.",
    "Tabs - Organizes content into separate views.",
    "Box - Wrapper component for applying layout styles.",
    "Container - Centers content horizontally with padding.",
    "Grid - 2D layout system for aligning items.",
    "Grid v2 - Enhanced version of the Grid component.",
    "Stack - Arranges children in a single direction, either vertically or horizontally.",
    "Image List - Displays a collection of images in a grid.",
    "Masonry - Responsive grid layout without fixed column sizes.",
    "Timeline - Displays a list of events in chronological order.",
    "Click-Away Listener - Detects clicks outside a specified element.",
    "CSS Baseline - Provides a consistent baseline for CSS styles.",
    "Modal - Component for creating modal dialogs.",
    "No SSR - Disables server-side rendering for a component.",
    "Popover - Displays content on top of another.",
    "Popper - Positions elements relative to another element.",
    "Portal - Renders children into a DOM node outside the parent hierarchy.",
    "Textarea Autosize - Textarea that automatically adjusts its height.",
    "Transitions - Provides animation effects for components.",
    "useMediaQuery - React hook for matching CSS media queries.",
]

SYSTEM_PROMPT_FOR_STYLE_AUGMENTATION = """You are an assistant familiar with the React framework and skilled at writing frontend code."""


# Some prompts for last turn's try. Save here for potential future use.
# 5. Do not import images since we don't have the image data. You can import anything from MUI libraries.
# 3. You can adjust the content of the original component. When extending styles, please focus on functional components. There is no need to modify purely presentational properties (such as background color, static text, etc.).
# 5. You don't always have to use the most common use cases; diversified use cases are encouraged.
# . You can make design in aspects such as:
#    - **Colors** (e.g., background color, text color, etc.)
#    - **Text content** (e.g., title, artist, etc.)
#    - **Spacing** (e.g., margin, padding)
#    - **Positions** (e.g., absolute, relative)
#    - **Fonts and icons** (optional, based on the component's needs)


def generate_new_scenario_component_prompt(
    component_root_name: str,
    component_constraint: str,
    original_code: str,
    generated_codes: list[str],
    lib_name: str,
) -> str:
    base_template = """
<UI Component Code>
{original_code}
</UI Component Code>
This is a piece of front-end UI code written in React, describing a component with basic interactive functionality.

Generated blocks:
{generated_blocks}
Please come up with a real application scenario for this type of component based on the original component {generated_reference}, and reconstruct a differently styled component based on the application scenario. Requirements:

0. The component should be different from the generated blocks in appearance and functionality.

1. The core functionality must remain consistent with the original component {component_root_name}. Based on this, you can design new application scenarios and styles. For {component_root_name}, there is certain constraint: {component_constraint}

2. Please add some new subcomponents that are commonly found in modern UI design and are related to component functionality. These subcomponents should prioritize the use of images for display, and text can be used when necessary. If the original component is simple, you should add MORE SUBCOMPONENTS of LAYOUTS to make it realistic and complex.

3. Focus on components with interactive attributes that provide a rich interactive experience. Avoid overly simple layouts or components.

4. Please write the code using only basic lucide-react and tailwind css. DO NOT import any outside .css file!

5. Style: You're encouraged to design colorful, aesthetic, functional UI components

6. Design Aesthetic: Authenticity is key. The component should resemble real-world components that users interact with daily. Pay close attention to style parameters, such as spacing, font sizes, button interactions, and overall layout. Make sure the design is consistent with what we typically use in modern, functional UI components.

7. Library to use: You are recommended to use tailwind css classes and lucide-react classes to handle visual styles. Ensure aesthetic component design as well as code accuracy. Make sure the classes you use are real and not fake. No Image Imports: Since we don't have image data, avoid importing images. 

8. Output Accuracy: MAKE SURE that "new_style_code" is a complete React component code that obey tsx grammar. Ensure your code is correct!

9. Default Element States: For elements like dialogs, backdrops, autocompletes, etc., their panels are usually closed by default. Please modify the code to ensure these elements are open by default (e.g., change useState(false) to useState(true) where necessary).

10. Keep key characteristics of original components, for example, the grid of tables, the feasibility of getting positions of every letters/characters in texts.

11. The original UI component code may have some bugs, you should not keep them.

Remember your generated component should include {component_root_name} or be {component_root_name}.

Pay attention to your import, make sure every import is correct.

Remember: Do not name your component 'App' as it conflicts with the main App.js file that imports it.

Please respond in JSON format directly. You should not add any other text or comments.
{{
    "thoughts": "The thought process of design ideas and scene selection",
    "new_style_code": "The specific code for the new component"
}}"""

    # 处理已生成的组件代码块
    generated_blocks = ""
    if generated_codes:
        for i, code in enumerate(generated_codes, 1):
            generated_blocks += f"""<Generated Component Code {i}>
                    {code}
                    </Generated Component Code {i}>

                    """

    # 根据是否有已生成的组件来设置相关引用和约束
    generated_reference = (
        "and the different scene components generated previously"
        if generated_codes
        else ""
    )
    uniqueness_constraint = (
        "The new scene cannot be the same as the existing scene."
        if generated_codes
        else ""
    )

    # 填充模板并返回完整prompt
    return base_template.format(
        original_code=original_code,
        component_root_name=component_root_name,
        component_constraint=component_constraint,
        generated_blocks=generated_blocks,
        generated_reference=generated_reference,
        uniqueness_constraint=uniqueness_constraint,
    )


# You can import components from Material-UI (MUI) or use CSS classes to handle visual styles. Avoid importing libraries that are not from MUI.

STYLE_TEMPLATE_GENERATE_PROMPT = """
<Original UI Component Code>
{original_code}
</Original UI Component Code>
```

This is a piece of front-end UI code written in React, which defines a component with interactive functionality for a specific application scenario. 

### Task:
1. **Analyze the Original Code:**  
   Carefully examine the React component code and think about the appropriate style properties that can be used as objects for the component. Consider visual aspects such as colors, text, margins, padding, and positioning.

2. **Create a Style Template:**  
   Generate a new complete React component code that includes the style template. The style template should contain dynamic, replaceable values for text, colors, relative positions, etc. These will allow you to achieve data augmentation by simply changing values like text content, colors, etc.

3. **Provide Component Prop Nesting Code:**  
   After creating the style template, include the component prop nesting code, which shows how to assign the style template to the component. This means wrapping the component with the nested props containing your styling and data structure.

### Guidelines:

1. **Style Template:** The style template should contain replaceable values for visual properties, such as:
   - **Colors** (e.g., background color, text color, etc.)
   - **Text content** (e.g., title, artist, etc.)
   - **Spacing** (e.g., margin, padding)
   - **Positions** (e.g., absolute, relative)
   - **Fonts and icons** (optional, based on the component's needs)

2. **Design Aesthetic:**  
   - Ensure that the generated style is visually appealing, colorful, and functional.
   - Experiment with diverse, engaging color schemes and layouts.
   - Authenticity is key: The component should resemble real-world components that users interact with daily. Pay close attention to style parameters, such as spacing, font sizes, button interactions, and overall layout. Make sure the design is consistent with what we typically use in modern, functional UI components.
   - Appearance is important—ensure the component is easy to interact with, visually engaging, and provides a smooth user experience.

3. **No Image Imports:**  
   Since we don’t have image data, avoid importing images. You can use Tailwind CSS  and lucide-react classes to handle visual styles.

4. **Encourage Creativity:**  
   Feel free to experiment with different design layouts or color schemes that fit the component's purpose.

5. **Output Accuracy:**  
   MAKE SURE that "component_code" is a complete React component code that obey js grammar, and "component_prop_nesting" is a prop nesting code that assigns the style template to the component that obey js grammar.

### Example Component Prop Nesting:

```
<MusicPlayer
  songData={{
    title: "Custom Song Name",
    artist: "Custom Artist",
    album: "Custom Album",
    duration: 500,
    lyrics: "Custom Lyrics...",
  }}
  theme={{
    primary: "bg-purple-500",
    secondary: "bg-purple-300",
    text: "text-gray-900",
    iconColor: "text-gray-700"
  }}
/>
```

```
<ProductCard
  productData={{
    name: "Wireless Headphones",
    price: "$99.99",
    description: "High-quality sound with noise cancellation feature.",
    rating: 4.5,
    images: ["headphones.jpg"],
  }}
  theme={{
    primary: "bg-yellow-500",
    secondary: "bg-yellow-300",
    text: "text-black",
    iconColor: "text-yellow-700"
  }}
/>
```

```
<TodoList
  todoData={{
    tasks: [
      {{ title: "Buy groceries", completed: false }},
      {{ title: "Clean the house", completed: true }},
      {{ title: "Finish project", completed: false }},
    ],
  }}
  theme={{
    primary: "bg-indigo-500",
    secondary: "bg-indigo-300",
    text: "text-white",
    iconColor: "text-indigo-700"
  }}
/>
```

```
<UserProfile
  userData={{
    name: "Alice Smith",
    age: 29,
    location: "New York",
    bio: "Software engineer and tech enthusiast.",
    profilePicture: "alice.jpg",
  }}
  theme={{
    primary: "bg-pink-500",
    secondary: "bg-pink-300",
    text: "text-white",
    iconColor: "text-pink-700"
  }}
/>
```

The result should include:

1. A **complete React component** with a flexible style template.
2. A **prop nesting** structure that assigns the style template dynamically.

**Output Format for New Component:**
```json
{{
  "thoughts": "The `MusicPlayer` component could benefit from customization in terms of background color, text color, and button styling. These properties should be made flexible for data augmentation.",
  "component_code": "<Component code with the generated style template>",
  "component_prop_nesting": "<Component with data and theme props assigned for dynamic styling>"
}}
```

"""

STYLE_CODE_GENERATE_PROMPT = """
User Prompt:
<Component Code>
{component_code}
<Component Code>

<Original Style Control Code>
{style_code}
<Original Style Control Code>

This is a style control code for a React object. Please help me randomly fill in these properties to help me get a variety of component objects, and generate a new style code that strictly follows the format of original style code, but with different values.

You're encouraged to design a style that is colorful, diverse, beautiful, and functional. Appearance is important.

Remember not to add attributes that results in additional imports.

Do not import images since we don't have the image data.

Output Format:
{{
	"thoughts": "Return your thoughts here.",
	"style_code": "Return your React code here"
}}
"""

VISUAL_FILTER_PROMPT = """
You're a smart and precise GUI Interaction Assistant. 
You will be provided with a screenshot that includes a green circle, with a green dot inside the circle indicating the exact position where the user performed an action. 
Additionally, you will be given a cropped version of the screenshot that including the green dot and circle to help you better observe the action location. 
You'll also be given a cropped version of the screenshot without the green dot and the circle to help you see the original view of the component
Along with the screenshot, you will receive an **instruction** describing the user's intended action. You need to verify whether this instruction corresponds to the position marked by the green dot in the screenshot.
In detail, Your task is as follows:  

---

### **1. Error Handling:**  
- Immediately return `false` if you notice an error message such as "Compiled with problems" on the screen or if the screen is obscured by red error messages.  

---

### **2. Element Identification:**  
- Identify the GUI element at the position marked by the green dot within the green circle.  
- Provide a description of the element, including its type (e.g., button, text, input field), label, or associated functionality.  
- If the element is a slider, then the instruction is correct, you don't need to verify, return `true` in is_correct.

---

### **3. Instruction Target Type:**  
- Determine what is the target that the **instruction** requires interacting with, whether it is an element (e.g., a button) or a specific piece of text (e.g., a word, phrase, or paragraph).  

---

### **4. Target Match Verification:**  
- **Check if the Interaction Target is Visible:** Verify if the element, text or position being clicked is clearly visible in the screenshot. If the instruction means to click on a position corresponding to a certain value on the slider, but the slider does not have visible scales or a range, then such an instruction should also be filtered out.

- **Compare Instruction with Target:** Evaluate whether the **instruction target** matches the identified GUI element. The instruction is considered aligned if its target clearly corresponds to the element at the green dot's position.

---

### **5. Click Accuracy Verification:**  
- **Determine if the Click Position is Correct:**  For example
  - For **button-like elements**, the click should ideally be at the center of the element.  
  - For **text-like elements**, the click should be at the center of the specific word, phrase, or paragraph mentioned in the instruction.
  - For **other kinds fo elements**, the clicking position should be considered correct if it aligns the usage of this element. For example, for slider, the clicking position should be on the slider, at the position corresponding to the value mentioned in the instruction. For resizable textbox, we may drag on the corner of it to resize it.
  - Please note that if the position where the target element is clicked is covered by other elements, the click is also considered invalid.

---

### **6. Output Your Judgment:**  app_dir_path
Provide the output in the following format:  
```json
{{
	"thought_process": "Provide your reasoning and detailed observations here.",
	"is_correct": "Return true or false here.",
	"correct_instruction": "If is_correct is false, provide the correct instruction here. Otherwise, omit this field."
  "more_instructions": ["Provide up to 3 more instructions that also describe the correct interaction here."]
}}
```  

The green dot and The green circle surrounding the green dot is not part of the component; they serve solely as markers indicating the interaction position. If an instruction states, "click the green circle," but no actual component features a green circle—only our marker (green dot and green circle)—then the instruction is incorrect.

- **Return `true`** if:  
  - The target element matches the instruction.  
  - The click position is accurate.  
  - The target element is a slider.

- **Return `false`** if:  
  - The instruction does not align with the target element.  
  - The click position is inaccurate.  

If `false`, provide a corrected version of the instruction that aligns with the actual GUI interaction and click position.
"""

INST_FILTER_PROMPT = """
**"Given the instruction below, please check for the following issues:**
1. Whether the instruction contains unclear or ambiguous semantics.
2. Whether the instruction has multiple interaction targets or elements.
3. Whether the instruction includes references to positions like 'position 8' or 'index 1' (which are not relevant in a vision-based context).
4. Whether the instruction involves more than one step or action.

**Instruction:** {instruction}

- ambiguity: [True/False](Does the instruction contain unclear or ambiguous semantics?)
- multiple_targets: [True/False](Does the instruction have multiple goals or actions?)
- non_visino_reference: [True/False](Does the instruction reference positions like 'position 8' or 'index 1'?)
- multiple_steps: [True/False](Does the instruction involve more than one action or step?)

"""

# If `true`, provide 0-3 additional instructions that describe the correct interaction in `more_instructions`. These additional instructions should focus on the following aspects:

# 1. **Paraphrase the instruction**: Reword the original instruction to express the same intent in a different manner, while maintaining the same outcome.
#    *Example:*
#    Original: "Click the 'Submit' button."
#    Paraphrased: "Press the 'Submit' button to proceed."

# 2. **Describe the interaction with relative location**: Include instructions that describe the interaction in terms of its position relative to other elements. This could be a directional reference or a comparison to another visual element on the screen.
#    *Example:*
#    "Click the button to the right of the red 'Alert' button."
#    "Press the button located just below the 'Home' icon."

# 3. **Describe the interaction with ordinal numbers**: Specify the exact location of the item by its ordinal number (e.g., first, second, third, etc.) within a list or menu.
#    *Example:*
#    "Click the second button in the list from top to bottom."
#    "Select the third option in the dropdown menu."

# 4. **Describe the action in terms of its context or behavior**: Explain the interaction based on its purpose or behavior within the system, especially when the button or element has a specific function.
#    *Example:*
#    "Click the 'Download' button to start the file download."
#    "Press the 'Cancel' button to exit without saving changes."

# 5. **Use visual cues or descriptions of appearance**: Describe the element’s appearance (e.g., color, shape, size) to help the user recognize it.
#    *Example:*
#    "Click the blue 'Next' button at the bottom of the screen."
#    "Tap the large green button that says 'Confirm'."

# MAKE SURE every instruction in `more_instructions` is a accurate, correct, valid instruction that can be used to interact with the GUI. If there's no more accurate, correct, valid instructions, please omit this field.
