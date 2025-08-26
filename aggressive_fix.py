#!/usr/bin/env python3
"""
Aggressive fix for remaining clang lint issues - target under 20
"""

import re


def aggressive_fix(content):
    """Aggressively fix remaining issues"""
    lines = content.split('\n')
    fixed_lines = []

    for line in lines:
        # Strip trailing whitespace first
        line = line.rstrip()

        # Skip if line is already <= 80 characters
        if len(line) <= 80:
            fixed_lines.append(line)
            continue

        # Pattern 1: Very long lines - break at any reasonable point
        if len(line) > 90:
            # Try breaking at various operators
            operators = [' && ', ' || ', ' + ', ' - ', ' * ', ' / ', ' == ', ' != ', ' < ', ' > ', ' <= ', ' >= ', ', ']
            for operator in operators:
                if operator in line and len(line) > 80:
                    parts = line.split(operator, 1)  # Split only on first occurrence
                    if len(parts) == 2:
                        indent = re.match(r'^(\s*)', line).group(1)
                        fixed_lines.append(f"{indent}{parts[0]}{operator}")
                        fixed_lines.append(f"{indent}    {parts[1]}")
                        break
            else:
                # If no operator found, try breaking at spaces in long comments
                if '//' in line and len(line) > 80:
                    comment_pos = line.find('//')
                    if comment_pos > 0:
                        code_part = line[:comment_pos].rstrip()
                        comment_part = line[comment_pos + 2:].strip()
                        indent = re.match(r'^(\s*)', line).group(1)

                        if len(comment_part) > 50:
                            words = comment_part.split(' ')
                            if len(words) > 2:
                                # Take first 3 words for first line
                                first_part = ' '.join(words[:3])
                                rest = ' '.join(words[3:])

                                fixed_lines.append(f"{code_part}  // {first_part}")
                                fixed_lines.append(f"{indent}// {rest}")
                                continue

                # Last resort: just keep the line as is if it's critical
                fixed_lines.append(line)
        else:
            # For lines 80-90 characters, try simpler breaks
            if '(' in line and ')' in line and ',' in line:
                # Function calls with multiple parameters
                paren_start = line.find('(')
                if paren_start > 0 and paren_start < 50:
                    indent = re.match(r'^(\s*)', line).group(1)
                    func_name = line[:paren_start + 1]
                    args = line[paren_start + 1:]

                    if len(args) > 50:
                        fixed_lines.append(f"{indent}{func_name}")
                        fixed_lines.append(f"{indent}    {args}")
                        continue

            # Try breaking at assignment operators
            if '=' in line and not line.strip().startswith('//') and not line.strip().startswith('#'):
                assign_match = re.match(r'(\s*[^=]*=)\s*(.*);?', line.strip())
                if assign_match:
                    indent = re.match(r'^(\s*)', line).group(1)
                    left_side = assign_match.group(1)
                    right_side = assign_match.group(2).rstrip(';')

                    if len(right_side) > 40:
                        fixed_lines.append(f"{indent}{left_side}")
                        fixed_lines.append(f"{indent}    {right_side};")
                        continue

            # Keep the line as is
            fixed_lines.append(line)

    return '\n'.join(fixed_lines)

def main():
    filepath = "/Users/justin/Documents/Github/ESP32-Temp-Sensor/firmware/arduino/src/main.cpp"
    try:
        with open(filepath, 'r') as f:
            content = f.read()

        fixed_content = aggressive_fix(content)

        with open(filepath, 'w') as f:
            f.write(fixed_content)

        print(f"Applied aggressive fixes to {filepath}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
