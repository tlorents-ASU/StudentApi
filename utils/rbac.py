# ROLE_DEFAULTS = {
#     "admin":  {
#         "assignment_adder":1,"applications":1,"phd_applications":1,"student_summary_page":1,
#         "bulk_upload_assignments":1,"manage_assignments":1,"login":1,"master_dashboard":1
#     },
#     "level1": {
#         "assignment_adder":0,"applications":1,"phd_applications":1,"student_summary_page":1,
#         "bulk_upload_assignments":1,"manage_assignments":1,"login":0,"master_dashboard":0
#     },
#     "level2": {
#         "assignment_adder": 1, "applications": 1, "phd_applications": 1, "student_summary_page": 0,
#         "bulk_upload_assignments": 0, "manage_assignments": 0, "login":0, "master_dashboard":0
#     }
# }
#
# def merged_perms(role:str, row:dict|None):
#     base = ROLE_DEFAULTS.get(role, {})
#     if not row: return base
#     # overlay row flags over role defaults
#     out = dict(base)
#     for k in base.keys():
#         if k in row and row[k] is not None:
#             out[k] = 1 if row[k] else 0
#     return out



ROLE_DEFAULTS = {
    "admin": {
        "assignment_adder": True,
        "applications": True,
        "phd_applications": True,
        "student_summary_page": True,
        "bulk_upload_assignments": True,
        "manage_assignments": True,
        "login": True,
        "master_dashboard": True,
        "faculty_dashboard":True,
    },
    "level1": {
        "assignment_adder": False,
        "applications": True,
        "phd_applications": True,
        "student_summary_page": True,
        "bulk_upload_assignments": True,
        "manage_assignments": True,
        "login": False,
        "master_dashboard": False,
        "faculty_dashboard": True,
    },
    "level2": {
        "assignment_adder": True,
        "applications": True,
        "phd_applications": True,
        "student_summary_page": False,
        "bulk_upload_assignments": False,
        "manage_assignments": False,
        "login": False,
        "master_dashboard": False,
        "faculty_dashboard": True,
    },
    "default": {
        "assignment_adder": False,
        "applications": False,
        "phd_applications": False,
        "student_summary_page": False,
        "bulk_upload_assignments": False,
        "manage_assignments": False,
        "login": True,
        "master_dashboard": False,
        "faculty_dashboard": True,
    },
}

def merged_perms(role: str, row: dict | None) -> dict:
    """
    Start with role defaults (if any), then overlay ANY boolean keys from row.
    This makes 'custom' work because it has no defaults; we just take the row flags.
    """
    out = ROLE_DEFAULTS.get(role, {}).copy()
    if row:
        for k, v in row.items():
            if isinstance(v, bool):  # accept any boolean flag from DB row
                out[k] = v
    out["is_admin"] = (role == "admin")
    return out

# def merged_perms(role: str, row: dict | None):
#     base = ROLE_DEFAULTS.get(role, {}).copy()
#     if not row:
#         base["is_admin"] = role == "admin"
#         return base
#
#     out = dict(base)
#     for k, v in row.items():
#         if k in out:
#             out[k] = bool(v)
#     out["is_admin"] = role == "admin"
#     return out