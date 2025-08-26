#!/usr/bin/env python3
"""
Final cleanup of renderer.js - remove all duplicate event handlers
"""

def clean_renderer():
    renderer_path = "/Users/ktsutsum/Documents/claude/web-whisper-mw/electron/src/renderer/renderer.js"
    
    with open(renderer_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Track if we're inside initializeEventHandlers function
    inside_init_function = False
    init_brace_count = 0
    cleaned_lines = []
    skip_lines = False
    
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        
        # Check if we're entering initializeEventHandlers function
        if "function initializeEventHandlers() {" in line:
            inside_init_function = True
            init_brace_count = 1
            cleaned_lines.append(lines[i])
            i += 1
            continue
        
        # If inside initializeEventHandlers, track braces
        if inside_init_function:
            init_brace_count += line.count('{') - line.count('}')
            cleaned_lines.append(lines[i])
            if init_brace_count == 0:
                inside_init_function = False
            i += 1
            continue
        
        # Skip standalone event handlers outside initializeEventHandlers
        if "$(" in line and ".onclick" in line and not inside_init_function:
            # Skip this event handler block
            skip_lines = True
            # Find the end of this event handler (look for }; or };)
            brace_count = line.count('{') - line.count('}')
            i += 1
            
            while i < len(lines) and (brace_count > 0 or not lines[i].strip().endswith('};')):
                brace_count += lines[i].count('{') - lines[i].count('}')
                i += 1
            
            # Skip the closing line as well
            if i < len(lines):
                i += 1
            continue
        
        # Skip recording functionality and other standalone blocks
        if line.startswith("// Recording functionality"):
            # Skip until next function or major section
            while i < len(lines) and not (lines[i].startswith("function ") or lines[i].startswith("// ") and "function" in lines[i]):
                i += 1
            continue
            
        cleaned_lines.append(lines[i])
        i += 1
    
    # Write cleaned content
    with open(renderer_path, 'w', encoding='utf-8') as f:
        f.writelines(cleaned_lines)
    
    print(f"Cleaned renderer.js - removed standalone event handlers")

if __name__ == "__main__":
    clean_renderer()