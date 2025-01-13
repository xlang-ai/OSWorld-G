JS_WITH_COMPONENT = """
import React from 'react';
import './App.css';
import {component_name} from './{component_name}';

function App() {{
  return (
    <div className="App">
      <{component_name} />
    </div>
  );
}}

export default App;
"""

JS_WITHOUT_COMPONENT = """
import React from 'react';
import './App.css';

function App() {{
    return (
        <div className="App">
            <h1>Hello, World</h1>
        </div>
    );
}}

export default App;
"""

JS_EVAL_POSITION = """() => {
    const component = document.querySelector('.App');
    if (!component) return null;
    
    // 获取组件基本位置和信息
    const componentRect = component.getBoundingClientRect();
    
    // 扩展可交互元素的选择器
    const interactiveElements = Array.from(component.querySelectorAll(
        'button, input, select, textarea, [role="button"], [role="slider"], ' +
        '[contenteditable="true"], a, [tabindex]:not([tabindex="-1"]), ' +
        '[role="checkbox"], [role="radio"], [role="switch"], [role="tab"], ' +
        '[role="combobox"], [role="listbox"], [role="menu"], [role="menuitem"]'
    ));
    
    // 获取所有元素（包括非交互元素）
    const getAllElements = (root) => {
        const elements = [];
        const walker = document.createTreeWalker(
            root,
            NodeFilter.SHOW_ELEMENT,
            null,
            false
        );
        
        let node;
        while (node = walker.nextNode()) {
            elements.push(node);
        }
        return elements;
    };

    // 判断元素是否可见
    const isVisible = (element) => {
        const style = window.getComputedStyle(element);
        return style.display !== 'none' && 
               style.visibility !== 'hidden' && 
               style.opacity !== '0' &&
               element.offsetWidth > 0 && 
               element.offsetHeight > 0;
    };

    // 安全地获取className
    const getClassName = (element) => {
        if (element.className === undefined) return '';
        if (typeof element.className === 'string') return element.className;
        if (element.className.baseVal !== undefined) return element.className.baseVal;
        return '';
    };

    // 获取元素的完整路径
    const getElementPath = (element) => {
        const path = [];
        let currentElement = element;
        
        while (currentElement && currentElement !== component) {
            let selector = currentElement.tagName.toLowerCase();
            if (currentElement.id) {
                selector += `#${currentElement.id}`;
            }
            const className = getClassName(currentElement);
            if (className) {
                selector += `.${className.split(' ').filter(Boolean).join('.')}`;
            }
            path.unshift(selector);
            currentElement = currentElement.parentElement;
        }
        
        return path.join(' > ');
    };

    // 获取元素的所有属性
    const getElementAttributes = (element) => {
        const attributes = {};
        for (const attr of element.attributes) {
            attributes[attr.name] = attr.value;
        }
        return attributes;
    };

    // 收集元素详细信息
    const getAllElementsInfo = (elements) => {
        return elements.map(element => {
            try {
                const rect = element.getBoundingClientRect();
                const style = window.getComputedStyle(element);
                
                return {
                    attributes: getElementAttributes(element),
                    text: element.textContent.trim(),
                    isInteractive: interactiveElements.includes(element),
                    position: {
                        x_left: rect.left + window.scrollX,
                        y_top: rect.top + window.scrollY,
                        x_right: rect.left + window.scrollX + rect.width,
                        y_bottom: rect.top + window.scrollY + rect.height,
                        x_center: rect.left + window.scrollX + rect.width / 2,
                        y_center: rect.top + window.scrollY + rect.height / 2,
                    },
                };
            } catch (error) {
                console.error('Error processing element:', element, error);
                return null;
            }
        })
    };

    const allElements = getAllElements(component);
    
    return {
        elements: getAllElementsInfo(allElements),
        metadata: {
            timestamp: new Date().toISOString(),
            totalElements: allElements.length,
            interactiveElementsCount: interactiveElements.length,
            viewport: {
                width: window.innerWidth,
                height: window.innerHeight
            }
        }
    };
}
"""
