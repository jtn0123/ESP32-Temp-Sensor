#!/usr/bin/env python3
"""
Fix final remaining clang lint issues - target under 20 errors
"""

import re

def fix_final_issues(content):
    """Fix remaining line length and whitespace issues"""
    lines = content.split('\n')
    fixed_lines = []

    for i, line in enumerate(lines):
        # Strip trailing whitespace
        line = line.rstrip()

        # Skip if line is already <= 80 characters
        if len(line) <= 80:
            fixed_lines.append(line)
            continue

        # Pattern 1: Long string literals or comments
        if ('"' in line or '//' in line) and len(line) > 80:
            # Handle long comments by breaking them
            if '//' in line and len(line) > 80:
                comment_pos = line.find('//')
                if comment_pos > 0:
                    code_part = line[:comment_pos].rstrip()
                    comment_part = line[comment_pos + 2:].strip()
                    indent = re.match(r'^(\s*)', line).group(1)

                    # Break long comments
                    if len(comment_part) > 60:
                        words = comment_part.split(' ')
                        if len(words) > 1:
                            mid = len(words) // 2
                            first_half = ' '.join(words[:mid])
                            second_half = ' '.join(words[mid:])

                            fixed_lines.append(f"{code_part}  // {first_half}")
                            fixed_lines.append(f"{indent}// {second_half}")
                            continue

            # Handle long string literals
            if '"' in line and len(line) > 80:
                fixed_lines.append(line)  # Keep as is for now
                continue

        # Pattern 2: Long function calls or expressions
        if ('(' in line and ')' in line) and len(line) > 80:
            # Handle draw_in_region calls
            if 'draw_in_region(' in line:
                fixed_lines.append(line)
                continue

            # Handle other function calls
            paren_start = line.find('(')
            if paren_start > 0 and paren_start < 40:  # Reasonable function name length
                indent = re.match(r'^(\s*)', line).group(1)
                func_name = line[:paren_start + 1]
                args = line[paren_start + 1:]

                if ',' in args and len(args) > 60:
                    fixed_lines.append(f"{indent}{func_name}")
                    fixed_lines.append(f"{indent}    {args}")
                    continue

        # Pattern 3: Long variable assignments
        if '=' in line and len(line) > 80:
            assign_match = re.match(r'(\s*[^=]*=)\s*(.*);?', line.strip())
            if assign_match:
                indent = re.match(r'^(\s*)', line).group(1)
                left_side = assign_match.group(1)
                right_side = assign_match.group(2).rstrip(';')

                if len(right_side) > 50:
                    fixed_lines.append(f"{indent}{left_side}")
                    fixed_lines.append(f"{indent}    {right_side};")
                    continue

        # Pattern 4: Long array definitions or initializations
        if ('{' in line and '}' in line) and len(line) > 80:
            brace_start = line.find('{')
            if brace_start > 0:
                indent = re.match(r'^(\s*)', line).group(1)
                prefix = line[:brace_start + 1]
                content = line[brace_start + 1:].rstrip('};')

                if len(content) > 60:
                    fixed_lines.append(f"{indent}{prefix}")
                    fixed_lines.append(f"{indent}    {content}")
                    fixed_lines.append(f"{indent}}};")
                    continue

        # Pattern 5: Long conditional statements
        if ('if' in line or '&&' in line or '||' in line) and len(line) > 80:
            indent = re.match(r'^(\s*)', line).group(1)

            # Handle if statements
            if line.strip().startswith('if'):
                if_match = re.match(r'(\s*if\s*\([^)]*)\s*(&&|\|\|)\s*(.*)', line.strip())
                if if_match:
                    condition1 = if_match.group(1)
                    operator = if_match.group(2)
                    condition2 = if_match.group(3)
                    fixed_lines.append(f"{indent}{condition1}")
                    fixed_lines.append(f"{indent}    {operator} {condition2}")
                    continue

        # If no pattern matches, try simple line breaking at logical points
        if len(line) > 80:
            # Try breaking at operators
            for operator in [' + ', ' - ', ' * ', ' / ', ' && ', ' || ', ' == ', ' != ']:
                if operator in line and len(line) > 80:
                    parts = line.split(operator)
                    if len(parts) == 2:
                        indent = re.match(r'^(\s*)', line).group(1)
                        fixed_lines.append(f"{indent}{parts[0]}{operator}")
                        fixed_lines.append(f"{indent}    {parts[1]}")
                        break
                    else:
                        fixed_lines.append(line)
                        break
            else:
                fixed_lines.append(line)
        else:
            fixed_lines.append(line)

    return '\n'.join(fixed_lines)

def main():
    filepath = "/Users/justin/Documents/Github/ESP32-Temp-Sensor/firmware/arduino/src/main.cpp"
    try:
        with open(filepath, 'r') as f:
            content = f.read()

        fixed_content = fix_final_issues(content)

        with open(filepath, 'w') as f:
            f.write(fixed_content)

        print(f"Applied final fixes to {filepath}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
