#!/usr/bin/env python3
"""
Fix renderer.js by removing duplicate event handlers
"""
import re

def fix_renderer_js():
    renderer_path = "/Users/ktsutsum/Documents/claude/web-whisper-mw/electron/src/renderer/renderer.js"
    
    # Read the file
    with open(renderer_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Remove all standalone event handler assignments (those not inside initializeEventHandlers)
    # Keep only the ones inside the initializeEventHandlers function
    
    # Find the initializeEventHandlers function
    init_function_pattern = r'function initializeEventHandlers\(\) \{.*?\n\}'
    init_match = re.search(init_function_pattern, content, re.DOTALL)
    
    if init_match:
        # Extract the initializeEventHandlers function
        init_function = init_match.group(0)
        
        # Remove all standalone onclick assignments
        patterns_to_remove = [
            r"\$\('health'\)\.onclick = async \(\) => \{[^}]*\}[^}]*\};?\n?",
            r"\$\('switch-model'\)\.onclick = async \(\) => \{[^}]*\}[^}]*\};?\n?", 
            r"\$\('gpu-info'\)\.onclick = async \(\) => \{[^}]*\}[^}]*\};?\n?",
            r"\$\('send'\)\.onclick = async \(\) => \{[^}]*\}[^}]*\};?\n?",
            r"\$\('rec'\)\.onclick = async \(\) => \{[^}]*\}[^}]*\};?\n?",
            r"\$\('copy'\)\.onclick = async \(\) => \{[^}]*\}[^}]*\};?\n?",
            r"\$\('save'\)\.onclick = \(\) => \{[^}]*\}[^}]*\};?\n?",
            r"\$\('streaming-send'\)\.onclick = async \(\) => \{[^}]*\}[^}]*\};?\n?",
            r"\$\('streaming-cancel'\)\.onclick = async \(\) => \{[^}]*\}[^}]*\};?\n?",
            r"\$\('theme-toggle'\)\.onclick = \(\) => \{[^}]*\}[^}]*\};?\n?"
        ]
        
        # More aggressive pattern to remove everything between event handlers
        # Let's try a simpler approach - remove standalone event handlers
        standalone_patterns = [
            r"// GPU information\n\$\('gpu-info'\)\.onclick[\s\S]*?(?=\n\n//|\n\n\w|\nfunction|\n\$\(|\Z)",
            r"// File transcription\n\$\('send'\)\.onclick[\s\S]*?(?=\n\n//|\n\n\w|\nfunction|\n\$\(|\Z)", 
            r"// Recording\n\$\('rec'\)\.onclick[\s\S]*?(?=\n\n//|\n\n\w|\nfunction|\n\$\(|\Z)",
            r"// Copy and save functionality\n\$\('copy'\)\.onclick[\s\S]*?(?=\n\n//|\n\n\w|\nfunction|\n\$\(|\Z)",
            r"\$\('save'\)\.onclick[\s\S]*?(?=\n\n//|\n\n\w|\nfunction|\n\$\(|\Z)",
            r"// Streaming processing\n\$\('streaming-send'\)\.onclick[\s\S]*?(?=\n\n//|\n\n\w|\nfunction|\n\$\(|\Z)",
            r"\$\('streaming-cancel'\)\.onclick[\s\S]*?(?=\n\n//|\n\n\w|\nfunction|\n\$\(|\Z)",
            r"// Theme management[\s\S]*?\$\('theme-toggle'\)\.onclick[\s\S]*?(?=\n\n//|\n\n\w|\nfunction|\Z)"
        ]
        
        # Remove each pattern
        for pattern in standalone_patterns:
            content = re.sub(pattern, "", content, flags=re.MULTILINE)
    
    # Clean up extra newlines
    content = re.sub(r'\n{3,}', '\n\n', content)
    
    # Write back
    with open(renderer_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("Fixed renderer.js by removing duplicate event handlers")

if __name__ == "__main__":
    fix_renderer_js()