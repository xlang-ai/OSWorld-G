import Cocoa
import Foundation

class A11yInspector {
    private var app: NSRunningApplication?
    private var appRef: AXUIElement?
    private var dir_name: String
    
    init(dir_name: String) {
        self.app = NSWorkspace.shared.runningApplications.first(where: { 
            $0.localizedName == "Microsoft PowerPoint" 
        })
        self.dir_name = dir_name
        
        if let pid = app?.processIdentifier {
            self.appRef = AXUIElementCreateApplication(pid)
        }
    }
    
    struct ElementInfo: Codable {
        let role: String
        let title: String
        let value: String?
        let identifier: String?
        let description: String?
        let help: String?
        let frame: CGRect
        let path: String
        let children: [ElementInfo]
    }    

    func getElementInfo(_ element: AXUIElement, parentPath: String = "") -> ElementInfo? {
        var role: CFTypeRef?
        var title: CFTypeRef?
        var value: CFTypeRef?
        var identifier: CFTypeRef?
        var description: CFTypeRef?
        var help: CFTypeRef?
        var position: CFTypeRef?
        var size: CFTypeRef?
        var enabled: CFTypeRef?
        var focused: CFTypeRef?
        var selected: CFTypeRef?
        var children: CFTypeRef?
        
        AXUIElementCopyAttributeValue(element, kAXRoleAttribute as CFString, &role)
        AXUIElementCopyAttributeValue(element, kAXTitleAttribute as CFString, &title)
        AXUIElementCopyAttributeValue(element, kAXValueAttribute as CFString, &value)
        AXUIElementCopyAttributeValue(element, kAXIdentifierAttribute as CFString, &identifier)
        AXUIElementCopyAttributeValue(element, kAXDescriptionAttribute as CFString, &description)
        AXUIElementCopyAttributeValue(element, kAXHelpAttribute as CFString, &help)
        AXUIElementCopyAttributeValue(element, kAXPositionAttribute as CFString, &position)
        AXUIElementCopyAttributeValue(element, kAXSizeAttribute as CFString, &size)
        AXUIElementCopyAttributeValue(element, kAXEnabledAttribute as CFString, &enabled)
        AXUIElementCopyAttributeValue(element, kAXFocusedAttribute as CFString, &focused)
        AXUIElementCopyAttributeValue(element, kAXSelectedAttribute as CFString, &selected)
        AXUIElementCopyAttributeValue(element, kAXChildrenAttribute as CFString, &children)
        
        var frame = CGRect.zero
        if let positionValue = position as! AXValue? {
            var point = CGPoint.zero
            AXValueGetValue(positionValue, .cgPoint, &point)
            frame.origin = point
        }
        
        if let sizeValue = size as! AXValue? {
            var size = CGSize.zero
            AXValueGetValue(sizeValue, .cgSize, &size)
            frame.size = size
        }
        
        var attributeNames: CFArray?
        var actionNames: CFArray?
        AXUIElementCopyAttributeNames(element, &attributeNames)
        AXUIElementCopyActionNames(element, &actionNames)

        var actions: [String] = []
        if let actArray = actionNames as? [String] {
            actions = actArray
        }
        
        let roleStr = (role as? String) ?? "unknown"
        let titleStr = (title as? String) ?? ""
        let currentPath = parentPath.isEmpty ? roleStr : "\(parentPath)/\(roleStr)"
        let displayPath = titleStr.isEmpty ? currentPath : "\(currentPath)[\(titleStr)]"
        
        var childrenInfo: [ElementInfo] = []
        if let childArray = children as? [AXUIElement] {
            for childElement in childArray {
                if let childInfo = getElementInfo(childElement, parentPath: displayPath) {
                    childrenInfo.append(childInfo)
                }
            }
        }
        
        return ElementInfo(
            role: roleStr,
            title: titleStr,
            value: value as? String,
            identifier: identifier as? String,
            description: description as? String,
            help: help as? String,
            frame: frame,
            path: displayPath,
            children: childrenInfo
        )
    }
    
    func saveToJSON(filePath: String) {
        guard let appRef = self.appRef else {
            print("PowerPoint not found")
            return
        }
        
        var value: CFTypeRef?
        AXUIElementCopyAttributeValue(appRef, kAXWindowsAttribute as CFString, &value)
        
        if let windows = value as? [AXUIElement] {
            for window in windows {
                if let info = getElementInfo(window) {
                    let encoder = JSONEncoder()
                    encoder.outputFormatting = .prettyPrinted
                    
                    do {
                        let jsonData = try encoder.encode(info)
                        try jsonData.write(to: URL(fileURLWithPath: filePath))
                        print("Saved A11y Tree to JSON at \(filePath)")
                        
                    } catch {
                        print("Error saving JSON: \(error)")
                    }
                }
            }
        }
    }
    
    func takeScreenshot() {
        let screenshotPath = "original_screenpair/\(dir_name)/screenshot_\(dir_name).png"
        
        let image = CGWindowListCreateImage(CGRect.infinite, .optionOnScreenOnly, CGWindowID(0), .bestResolution)
        
        if let image = image {
            let bitmapRep = NSBitmapImageRep(cgImage: image)
            if let pngData = bitmapRep.representation(using: .png, properties: [:]) {
                do {
                    try pngData.write(to: URL(fileURLWithPath: screenshotPath))
                    print("Screenshot saved at \(screenshotPath)")
                } catch {
                    print("Error saving screenshot: \(error)")
                }
            }
        } else {
            print("Failed to capture screenshot.")
        }
    }
}

let dir_name = "tab6"

let fileManager = FileManager.default
let directoryPath = "original_screenpair/\(dir_name)"
if !fileManager.fileExists(atPath: directoryPath) {
    do {
        try fileManager.createDirectory(atPath: directoryPath, withIntermediateDirectories: true, attributes: nil)
        print("Directory created at path: \(directoryPath)")
    } catch {
        print("Error creating directory: \(error)")
    }
}

let inspector = A11yInspector(dir_name: dir_name)
Thread.sleep(forTimeInterval: 3)

inspector.saveToJSON(filePath: "\(directoryPath)/ppt_a11y_tree_\(dir_name).json")
inspector.takeScreenshot()
