#!/usr/bin/env python3
"""
Script to fix common line length issues in main.cpp
"""

import re

def fix_line_lengths(content):
    """Fix common line length issues"""
    lines = content.split('\n')
    fixed_lines = []

    for line in lines:
        original_line = line

        # Skip if line is already <= 80 characters or is a preprocessor directive
        if len(line) <= 80 or line.strip().startswith('#'):
            fixed_lines.append(line)
            continue

        # Pattern 1: Long if statements - break at logical operators
        if_match = re.match(r'(\s*if\s*\([^)]*)\s*(&&|\|\|)\s*(.*)', line.strip())
        if if_match and len(line) > 80:
            indent = re.match(r'^(\s*)', line).group(1)
            condition1 = if_match.group(1)
            operator = if_match.group(2)
            condition2 = if_match.group(3)
            fixed_lines.append(f"{indent}{condition1}")
            fixed_lines.append(f"{indent}    {operator} {condition2}")
            continue

        # Pattern 2: Long static_cast declarations - break at static_cast
        cast_match = re.match(r'(\s*[^=]*=)\s*(static_cast<[^>]*>\([^)]*\));', line.strip())
        if cast_match and len(line) > 80:
            indent = re.match(r'^(\s*)', line).group(1)
            left_side = cast_match.group(1)
            right_side = cast_match.group(2)
            fixed_lines.append(f"{indent}{left_side}")
            fixed_lines.append(f"{indent}    {right_side}")
            continue

        # Pattern 3: Long comments - break at spaces
        if line.strip().startswith('//') and len(line) > 80:
            comment_text = line.strip()[2:].strip()
            indent = re.match(r'^(\s*)', line).group(1)
            words = comment_text.split(' ')
            current_line = f"{indent}//"
            for word in words:
                if len(current_line + ' ' + word) <= 80:
                    current_line += ' ' + word
                else:
                    if current_line != f"{indent}//":
                        fixed_lines.append(current_line)
                    current_line = f"{indent}// {word}"
            if current_line != f"{indent}//":
                fixed_lines.append(current_line)
            continue

        # Pattern 4: Long function calls with multiple parameters
        func_match = re.match(r'(\s*[^=]*=)\s*([^;]+);', line.strip())
        if func_match and len(line) > 80:
            indent = re.match(r'^(\s*)', line).group(1)
            left_side = func_match.group(1)
            func_call = func_match.group(2)
            # If it's a function call with parentheses, try to break at commas
            if '(' in func_call and ')' in func_call and ',' in func_call:
                fixed_lines.append(f"{indent}{left_side}")
                fixed_lines.append(f"{indent}    {func_call};")
                continue

        # If no pattern matches, keep the original line
        fixed_lines.append(original_line)

    return '\n'.join(fixed_lines)

def main():
    filepath = "/Users/justin/Documents/Github/ESP32-Temp-Sensor/firmware/arduino/src/main.cpp"
    try:
        with open(filepath, 'r') as f:
            content = f.read()

        fixed_content = fix_line_lengths(content)

        with open(filepath, 'w') as f:
            f.write(fixed_content)

        print(f"Fixed line lengths in {filepath}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()