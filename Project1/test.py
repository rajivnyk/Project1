import os

path = r"c:\Users\Sanjivkumar Naik\Documents\Rajivkumar Naik\Project1\controller\travel_controller.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

old_code = """            if tr.status == 'APPROVED':
            flash(f"Travel request {tr.request_no} auto-approved (no manager assigned).", "success")
        else:
            flash(f"Travel request {tr.request_no} submitted for manager approval.", "success")"""

new_code = """            if tr.status.name == 'APPROVED' or tr.status == 'APPROVED':
                flash(f"Travel request {tr.request_no} auto-approved (no manager assigned).", "success")
            else:
                flash(f"Travel request {tr.request_no} submitted for manager approval.", "success")"""

# The existing text is a bit messed up, let me re-write it correctly using regex or standard replace.
# Looking closely at the output:
#             if tr.status == 'APPROVED':
#             flash(f"Travel request {tr.request_no} auto-approved (no manager assigned).", "success")
#         else:
#             flash(f"Travel request {tr.request_no} submitted for manager approval.", "success")

# I'll just rewrite the whole function.
