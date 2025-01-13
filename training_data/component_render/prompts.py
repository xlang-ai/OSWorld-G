COMPONENT_PROMPT = """Create a single React component that implements: {component_desc}

Rules:
1. Only provide the component's JavaScript code
2. No CSS imports, and MUI is the only library allowed
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

DESC_PROMPT = """Generate a `component_description` for each component. The description should be detailed and accurately describe its appearance and composition so that a front-end engineer can write the corresponding code based solely on this description without adding any additional information. 

Example:
"A rating component with 5 stars, where 4 stars are selected by default",
"A volume control slider that allows users to adjust the volume by clicking or dragging",
"A PowerPoint-style text box where users can resize or move it by dragging its eight control points on edges and corners",

After the component description, generate a list of 3 `action_descs` for each action that can be performed on the component. 
You are encouraged to use parameters in the action description to describe the action. The parameters should be marked with <param_name> in the description.
You are encouraged to explore as many functions of the component as possible.

Example:
For "A rating component with 5 stars, where 4 stars are selected by default":
["Click on the 2nd star of the rating component to select it", "Click on the 4th star of the rating component to select it", "Give a 3 star rating"],

For "A volume control slider that allows users to adjust the volume by clicking or dragging":
["Click on the volume slider to set the volume to <x>%", "Increase the volume by <x>%", "Decrease the volume by <x>%"],

For "A PowerPoint-style text box where users can resize or move it by dragging its eight control points on edges and corners":
["Drag the bottom-right corner of the PowerPoint-style text box to resize it, increasing its width by <x> and height by <y>", "Move the text box to the top-left corner of the screen", "Increase the text box's width by <x> and height by <y>, by dragging the top-left corner"],

Input Information:
1. Component: {component_type}

Your Response Format:
{{
    "component_desc": "Your description for the component",
    "action_descs": ["Your description for the action"]
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
