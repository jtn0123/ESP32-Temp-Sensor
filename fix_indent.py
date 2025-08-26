#!/usr/bin/env python3
"""
Fix indentation for array elements in ui_ops_generated.cpp
"""

import re

def fix_indentation(content):
    """Fix indentation for array elements that start with {"""
    lines = content.split('\n')
    fixed_lines = []

    for line in lines:
        # If line starts with { followed by non-whitespace, add proper indentation
        if re.match(r'^\{[^}]*[^}\s]', line.strip()):
            # Add 4 spaces of indentation
            fixed_lines.append('    ' + line)
        else:
            fixed_lines.append(line)

    return '\n'.join(fixed_lines)

def main():
    filepath = "/Users/justin/Documents/Github/ESP32-Temp-Sensor/firmware/arduino/src/ui_ops_generated.cpp"
    try:
        with open(filepath, 'r') as f:
            content = f.read()

        fixed_content = fix_indentation(content)

        with open(filepath, 'w') as f:
            f.write(fixed_content)

        print(f"Fixed indentation in {filepath}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
