JS_WITH_COMPONENT = r"""
import React from 'react';
import './App.css';
import {component_name} from './components/{component_name}';
import RandomContainer from './components/RandomContainer';

function App() {{
  return (
    <div className="App">
      <RandomContainer>
        <{component_name} />
      </RandomContainer>
    </div>
  );
}}

export default App;
"""

JS_WITHOUT_COMPONENT = r"""
import React from 'react';
import './App.css';
import RandomContainer from './components/RandomContainer';

function App() {
  return (
    <div className="App">
      <RandomContainer>
        <h1>Hello, World</h1>
      </RandomContainer>
    </div>
  );
}

export default App;
"""

JS_EVAL_TREE = """() => {
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

    // 递归收集元素信息及其子元素
    const getElementInfo = (element) => {
        try {
            const rect = element.getBoundingClientRect();
            const style = window.getComputedStyle(element);

            // 收集当前元素的信息
            const elementInfo = {
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
                children: [], // 初始化子节点数组
            };

            // 递归处理子元素
            for (const child of element.children) {
                if (isVisible(child)) {
                    const childInfo = getElementInfo(child);
                    if (childInfo) {
                        elementInfo.children.push(childInfo);
                    }
                }
            }

            return elementInfo;
        } catch (error) {
            console.error('Error processing element:', element, error);
            return null;
        }
    };

    // 从根组件开始递归构建树结构
    return getElementInfo(component);
}
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
    };
}
"""
