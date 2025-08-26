#!/usr/bin/env python3
"""
Fix function parameter line length issues in main.cpp
"""

import re


def fix_function_parameters(content):
    """Fix long function parameter lines"""
    lines = content.split('\n')
    fixed_lines = []

    i = 0
    while i < len(lines):
        line = lines[i]

        # Look for function definitions that span multiple lines
        if 'static inline void' in line and '(' in line and not line.rstrip().endswith(');'):
            # Find the complete function signature
            func_lines = [line]
            j = i + 1
            while j < len(lines) and not lines[j].rstrip().endswith('{'):
                func_lines.append(lines[j])
                j += 1

            if j < len(lines):
                func_lines.append(lines[j])  # Add the opening brace line

                # Join all function lines and check length
                full_func = ' '.join([line.strip() for line in func_lines])

                if len(full_func) > 80 and ',' in full_func:
                    # Reformat the function parameters
                    indent = re.match(r'^(\s*)', func_lines[0]).group(1)

                    # Extract function name and return type
                    func_match = re.match(r'(\s*static inline \w+\s+\w+)\s*\(', func_lines[0])
                    if func_match:
                        func_start = func_match.group(1)

                        # Collect all parameters
                        current_param = ""
                        in_parens = False

                        for func_line in func_lines:
                            if '(' in func_line:
                                in_parens = True
                                # Extract from first parenthesis
                                paren_start = func_line.find('(')
                                current_param = func_line[paren_start + 1:]

                            elif in_parens:
                                current_param += ' ' + func_line.strip()

                            if ')' in func_line:
                                in_parens = False
                                # Remove the closing paren and brace
                                current_param = current_param.replace(') {', '').strip()
                                break

                        # Split parameters by comma
                        if ',' in current_param:
                            param_list = [p.strip() for p in current_param.split(',')]

                            # Reformat with each parameter on new line
                            fixed_lines.append(f"{indent}{func_start}(")
                            for k, param in enumerate(param_list):
                                comma = ',' if k < len(param_list) - 1 else ') {'
                                fixed_lines.append(f"{indent}    {param}{comma}")

                            i = j  # Skip processed lines
                            continue

        # If no special handling, just add the line
        fixed_lines.append(line)
        i += 1

    return '\n'.join(fixed_lines)

def main():
    filepath = "/Users/justin/Documents/Github/ESP32-Temp-Sensor/firmware/arduino/src/main.cpp"
    try:
        with open(filepath, 'r') as f:
            content = f.read()

        fixed_content = fix_function_parameters(content)

        with open(filepath, 'w') as f:
            f.write(fixed_content)

        print(f"Fixed function parameter formatting in {filepath}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
