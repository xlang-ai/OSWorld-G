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

# Example for a Checkbox Group:
# {{
#     "action_intent_list": [
#         "Single selection",
#         "Select all",
#         "Deselect all",
#         "Deselect single item"
#     ]
# }}


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
    generated_codes: list[str] = None,
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

2. Please add some new subcomponents that are commonly found in modern UI design and are related to component functionality. These subcomponents should prioritize the use of images for display, and text can be used when necessary.

3. Focus on components with interactive attributes that provide a rich interactive experience. Avoid overly simple layouts or components.

4. Please write the code using only basic lucide-react and tailwind css. DO NOT import any outside .css file!

5. Style: You're encouraged to design colorful, aesthetic, functional UI components

6. Design Aesthetic: Authenticity is key. The component should resemble real-world components that users interact with daily. Pay close attention to style parameters, such as spacing, font sizes, button interactions, and overall layout. Make sure the design is consistent with what we typically use in modern, functional UI components.

7. Library to use: You can use tailwind css classes and lucide-react classes to handle visual styles. Make sure the classes you use are real and not fake. No Image Imports: Since we don’t have image data, avoid importing images. 

8. Output Accuracy: MAKE SURE that "new_style_code" is a complete React component code that obey js grammar. Ensure your code is correct!

9. Default Element States: For elements like dialogs, backdrops, autocompletes, etc., their panels are usually closed by default. Please modify the code to ensure these elements are open by default (e.g., change useState(false) to useState(true) where necessary).

10. Keep key characteristics of original components, for example, the grid of tables, the feasibility of getting positions of every letters/characters in texts. For tables, keep the large amount of cells.For tables, keep the large amount of cells.For tables, keep the large amount of cells.

Remember your generated component should include {component_root_name} or be {component_root_name}.

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
You're a smart and precise GUI Interaction Assistant. You will be provided with a screenshot that includes a green circle, with a green dot inside the circle indicating the exact position where the user performed an action. Additionally, you will be given a cropped version of the screenshot that focuses on the green dot and circle to help you better observe the action location. Along with the screenshot, you will receive an **instruction** describing the user's intended action. Your task is as follows:  

---

### **1. Error Handling:**  
- Immediately return `false` if you notice an error message such as "Compiled with problems" on the screen or if the screen is obscured by red error messages.  

---

### **2. Element Identification:**  
- Identify the GUI element at the position marked by the green dot within the green circle.  
- Provide a description of the element, including its type (e.g., button, text, input field), label, or associated functionality.  

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

### **6. Output Your Judgment:**  
Provide the output in the following format:  
```json
{{
	"thought_process": "Provide your reasoning and detailed observations here.",
	"is_correct": "Return true or false here.",
	"correct_instruction": "If is_correct is false, provide the correct instruction here. Otherwise, omit this field."
  "more_instructions": ["Provide up to 3 more instructions that also describe the correct interaction here."]
}}
```  

- **Return `true`** if:  
  - The target element matches the instruction.  
  - The click position is accurate.  

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
