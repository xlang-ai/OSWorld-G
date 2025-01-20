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
- Component description: {component_desc}
- Component name: {component_name}
- Screenshot: showing component's current state and properties


Requirements:
1. Consider all possible interactions, as many as possible
2. Group similar actions together, don't include action intents that are too similar or repetitive
3. Propose action on BOTH interactive elements and non-interactive elements(such as text, image, etc. You can click on text to select it or part of it)
4. Check screenshot to make sure the action is possible
5. The interaction should be completed in ONE step, don't include multiple steps in one action(e.g. you cannot click multiple buttons in one action)

Output Format:
{{
    "action_intent_list": [
        "<category_1>",
        "<category_2>",
        "<category_3>",
        "<category_4>"...
    ]
}}

Example for a Checkbox Group:
{{
    "action_intent_list": [
        "Single selection",
        "Select all",
        "Deselect all",
        "Deselect single item"
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

## Input Format
1. **Component Name**, The name of the UI component: {component_name}
2. **Component Description**, The description of the UI component: {component_desc}
3. **Screenshot**, An image showing the component's current state.
4. **Action Intent**, A possible user interaction intent category for the component: {action_intent}
5. **Position Data**, JSON object containing the positions of all elements: {position}


## Generate Action
Based on the action space type and action intent, generate appropriate action specifications of action intent. The action should contain:

1. **Thought Process** (`thought_process`)
   - Recall the action intent
   - Think if this action intent is executable in the current state of the component
   - If not, set action space type to "none" and generate empty action_desc and action_code.
   - If yes, give corresponding action description for the action intent
    - Identify key UI points that remain constant:
        * Component endpoints (for sliders)
        * Center positions (for buttons)
        * Control points (for resizable elements)
    - Document points using format: `x_name, y_name = x, y`
    - Explain calculation logic
    - For discrete or continuous action spaces: Identify and explain parameters from action description

2. **Determine Action Space Type** (`action_space_type`)
First, analyze and determine the type of action space for this interaction:
- **None**: No action space exists (e.g., clicking a button - note: clicking different parts of the same button doesn't count as different actions)
- **Unique**: Only one possible action exists (e.g., clicking a button - note: clicking different parts of the same button doesn't count as different actions)
- **Discrete**: Limited/unlimited set of distinct possible actions (e.g., selecting from a list of options)
- **Continuous**: Infinite possible actions within a range (e.g., dragging a slider to any position)

You must specify one of these action space types: "none", "unique", "discrete", or "continuous"

If the action space type is "none", you should generate empty action_desc and action_code, but generate thought_process to explain why the action space type is "none".

3. **Action Description** (`action_desc`)
   - Describe what the action does, which serves as the instantiation/implementation of the action intent
   - Must be based on the component's CURRENT state in the SCREENSHOT only(e.g. you cannot click on the button that is not displayed in the screenshot. You cannot turn on a switch that is already on)
   - Should not describe actions that require prior interactions
   - For discrete or continuous action spaces: Use `<param_name>` format for variable parameters
   - For discrete action spaces: Enumerate all possible actions beforehand

4. **Action Discrete Params** (`action_discrete_params`)
   - List of parameters for discrete action spaces, not [] only when action_space_type is "discrete"

5. **Action Code** (`action_code`)
   - Function name must be `action`
   - Define constant coordinates first
   - Use PyAutoGUI only
   - For discrete or continuous action spaces: Implement variable parameters using `<param_name>` format

## Response Format
```json
{{
    "action_space_type": "none" | "unique" | "discrete" | "continuous",
    "action_desc": "Description of the action",
    "thought_process": "Detailed explanation of:
                1. Key UI points identified
                2. Reasoning for point selection
                3. Parameter usage
                4. Coordinate calculations",
    "action_code": "PyAutoGUI implementation"
}}
```

## Examples

### Example 1: Volume Slider
**Input:**
- Component Name: "A volume slider"
- Component Description: "Sliders allow users to make selections from a range of values. Sliders reflect a range of values along a bar, from which users may select a single value. They are ideal for adjusting settings such as volume, brightness, or applying image filters."
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
            "action_code": "
                def action(volume):
                    x_0, y_0 = 22, 30  # Left endpoint
                    x_1, y_1 = 222, 30  # Right endpoint
                    x = x_0 + (x_1 - x_0) * (volume / 100)
                    pyautogui.click(x, y_0)"
              }}
          ]
      }}
  }}
```

### Example 2: Rating Component
- Component Name: "A rating component"
- Component Description: "Rating components allow users to rate something by selecting a number of stars. They are ideal for rating products, articles, or other items."
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
    "action_code": "pyautogui.click(650, 225)"
}}
```

## Important Notes
- Only use current state information
- Ensure coordinates match the position data provided
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


def generate_new_style_component_prompt(
    original_code: str, generated_codes: list[str] = None
) -> str:
    base_template = """
<UI Component Code>
{original_code}
</UI Component Code>
This is a piece of front-end UI code written in React, describing a component with basic interactive functionality.

{generated_blocks}
Please come up with a real application scenario for this type of component based on the original component {generated_reference}, and reconstruct a differently styled component based on the application scenario. Requirements:

1. The core functionality must remain consistent with the original component. Based on this, you can design new application scenarios and styles. {uniqueness_constraint}

2. Please add some new subcomponents that are commonly found in modern UI design and are related to component functionality. These subcomponents should prioritize the use of images for display, and text can be used when necessary.

3. You can adjust the content of the original component. When extending styles, please focus on functional components. There is no need to modify purely presentational properties (such as background color, static text, etc.).

4. Focus on components with interactive attributes that provide a rich interactive experience. Avoid overly simple layouts or components.

Please respond in JSON format:
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
        generated_blocks=generated_blocks,
        generated_reference=generated_reference,
        uniqueness_constraint=uniqueness_constraint,
    )


STYLE_TEMPLATE_GENERATE_PROMPT = """
User Prompt:

<UI Component Code>
{original_code}
</UI Component Code>

This is a piece of front-end UI code written in React, describing a component with interactive functionality in a specific application scenario. Please analyze this React code and add a style template for this UI component. The style template should include replaceable images, text, colors, relative positions, etc. This way, I can achieve data augmentation by assigning different style values (image paths, text content, etc.).

I hope to interact more with this component, so please focus on those components that have interactive properties. There is no need to include the properties of non-interactive components in the style template, such as background color, non-interactive text, etc.

Here is an example of style code:

<EnhancedMusicPlayer
  songData={{
    title: "Custom Song Name",
    artist: "Custom Artist",
    album: "Custom Album",
    duration: 300,
    coverImage: "/path/to/cover.jpg",
    lyrics: "Custom Lyrics...",
  }}
  theme={{
    primary: "bg-purple-500",
    secondary: "bg-purple-300",
    text: "text-gray-900",
    iconColor: "text-gray-700"
  }}
/>
You need to implement the acceptance of these parameters in the EnhancedMusicPlayer component object.

Please respond in JSON format. First, think about which components in this component are suitable to be used as objects for the style template. Then provide the complete React component code containing the style template. Finally, provide the replaceable style file code. Your styles do not need to be consistent with the example.

{{
    "thoughts": "",
    "component_code": "",
    "style_template": "",
}}
"""


STYLE_CODE_GENERATE_PROMPT = """
User Prompt:
<Style Control Code>
{style_code}
<Style Control Code>

This is a style control code for a React object. Please help me randomly fill in these properties to help me get a variety of component objects.

Please respond in JSON format.
{{
	"thoughts": "Return your thoughts here.",
	"style_code": "Return your React code here"
}}
"""
