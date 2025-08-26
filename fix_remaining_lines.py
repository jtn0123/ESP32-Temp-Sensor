#!/usr/bin/env python3
"""
Fix remaining line length issues in main.cpp
"""

import re


def fix_remaining_patterns(content):
    """Fix remaining line length patterns"""
    lines = content.split('\n')
    fixed_lines = []

    for i, line in enumerate(lines):
        original_line = line

        # Skip if line is already <= 80 characters or is a preprocessor directive
        if len(line) <= 80 or line.strip().startswith('#'):
            fixed_lines.append(line)
            continue

        # Pattern 1: Long function definitions with parameters
        func_match = re.match(r'(\s*static inline void \w+\([^)]*),\s*([^)]*\)\s*\{)', line.strip())
        if func_match and len(line) > 80:
            indent = re.match(r'^(\s*)', line).group(1)
            func_start = func_match.group(1)
            func_end = func_match.group(2)
            fixed_lines.append(f"{indent}{func_start}) {{")
            fixed_lines.append(f"{indent}    {func_end.replace(') {', '').replace('{', '')}")
            continue

        # Pattern 2: Long Serial.printf statements
        if 'Serial.printf(' in line and len(line) > 80:
            # Find the opening parenthesis
            paren_start = line.find('(')
            if paren_start != -1:
                indent = re.match(r'^(\s*)', line).group(1)
                prefix = line[:paren_start + 1]
                rest = line[paren_start + 1:]

                # Split the arguments and reformat
                if ',' in rest:
                    args = rest.split(',')
                    fixed_lines.append(f"{indent}{prefix}{args[0]},")

                    for arg in args[1:-1]:
                        fixed_lines.append(f"{indent}{' ' * (len(prefix) + 1)}{arg.strip()},")

                    if args[-1].strip().endswith(');'):
                        last_arg = args[-1].strip()[:-2]  # Remove );
                        fixed_lines.append(f"{indent}{' ' * (len(prefix) + 1)}{last_arg});")
                    continue

        # Pattern 3: Long conditional statements
        if ('if (' in line or '&&' in line or '||' in line) and len(line) > 80:
            indent = re.match(r'^(\s*)', line).group(1)

            # Handle if statements with multiple conditions
            if 'if (' in line and ('&&' in line or '||' in line):
                if_match = re.match(r'(\s*if\s*\([^)]*)\s*(&&|\|\|)\s*(.*)', line.strip())
                if if_match:
                    condition1 = if_match.group(1)
                    operator = if_match.group(2)
                    condition2 = if_match.group(3)
                    fixed_lines.append(f"{indent}{condition1}")
                    fixed_lines.append(f"{indent}    {operator} {condition2}")
                    continue

        # Pattern 4: Long variable assignments with calculations
        assign_match = re.match(r'(\s*[^=]*=)\s*(.*);', line.strip())
        if assign_match and len(line) > 80:
            indent = re.match(r'^(\s*)', line).group(1)
            left_side = assign_match.group(1)
            right_side = assign_match.group(2)

            # Check if right side is a complex expression
            if ('(' in right_side and ')' in right_side) or ('+' in right_side and len(right_side) > 40):
                fixed_lines.append(f"{indent}{left_side}")
                fixed_lines.append(f"{indent}    {right_side};")
                continue

        # If no pattern matches, keep the original line
        fixed_lines.append(original_line)

    return '\n'.join(fixed_lines)

def main():
    filepath = "/Users/justin/Documents/Github/ESP32-Temp-Sensor/firmware/arduino/src/main.cpp"
    try:
        with open(filepath, 'r') as f:
            content = f.read()

        fixed_content = fix_remaining_patterns(content)

        with open(filepath, 'w') as f:
            f.write(fixed_content)

        print(f"Fixed remaining line length issues in {filepath}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
