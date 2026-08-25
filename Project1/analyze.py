import os
import re
import glob
import ast
import jinja2.meta

CONTROLLERS_DIR = (
    r"c:\Users\Sanjivkumar Naik\Documents\Rajivkumar Naik\Project1\controller"
)
TEMPLATES_DIR = (
    r"c:\Users\Sanjivkumar Naik\Documents\Rajivkumar Naik\Project1\templates"
)


class RenderTemplateVisitor(ast.NodeVisitor):
    def __init__(self):
        self.renders = []

    def visit_Call(self, node):
        if isinstance(node.func, ast.Name) and node.func.id == "render_template":
            if node.args and isinstance(node.args[0], ast.Constant):
                template_name = node.args[0].value
                kwargs = [kw.arg for kw in node.keywords if kw.arg]
                self.renders.append((template_name, kwargs))
        self.generic_visit(node)


all_renders = {}
for py_file in glob.glob(os.path.join(CONTROLLERS_DIR, "*.py")):
    with open(py_file, "r", encoding="utf-8-sig") as f:
        try:
            tree = ast.parse(f.read(), filename=py_file)
            visitor = RenderTemplateVisitor()
            visitor.visit(tree)
            for tpl, kwargs in visitor.renders:
                if tpl not in all_renders:
                    all_renders[tpl] = set()
                all_renders[tpl].update(kwargs)
        except Exception as e:
            print(f"Error parsing {py_file}: {e}")
print("--- VARIABLES PASSED BY CONTROLLERS ---")
for tpl, kwargs in sorted(all_renders.items()):
    print(f"{tpl}: {', '.join(kwargs)}")
print("\n--- POSSIBLE MISMATCHES IN TEMPLATES ---")
env = jinja2.Environment()
for html_file in glob.glob(os.path.join(TEMPLATES_DIR, "*.html")):
    basename = os.path.basename(html_file)
    with open(html_file, "r", encoding="utf-8-sig") as f:
        content = f.read()
    try:
        ast_jinja = env.parse(content)
        undeclared = jinja2.meta.find_undeclared_variables(ast_jinja)
        # Context processors injected variables:
        builtins = {
            "request",
            "session",
            "g",
            "current_user",
            "current_employee",
            "get_flashed_messages",
            "url_for",
            "config",
            "str",
            "int",
            "len",
            "dict",
            "portal",
            "summary",
            "Role",
        }
        # We only care about top-level variable dependencies
        required_vars = undeclared - builtins
        if basename in all_renders:
            passed = all_renders[basename]
            # Missing means the template requires it, but the controller doesn't explicitly pass it
            missing = required_vars - passed
            # Filter out some known safe ones that might be passed differently
            if missing:
                print(f"[{basename}] Missing variables: {missing} (Passed: {passed})")
        else:
            # Not rendered explicitly or via base
            if basename not in ["base.html", "error.html"] and required_vars:
                print(
                    f"[{basename}] Not directly rendered in controller, but requires: {required_vars}"
                )
    except Exception as e:
        pass
