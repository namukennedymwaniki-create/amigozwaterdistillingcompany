# =========================================================
# services_permissions.py
# Role-based access control for reports & menus
# =========================================================

# Menu visibility by role
# Roles matching this file must match those seeded in database.py:
#   Administrator, Managing Director, Production Manager,
#   Quality Control Officer, Storekeeper, Procurement Officer,
#   Sales Officer, Accountant, Driver


ROLE_MENUS = {
    "Administrator": "*",  # everything
    "Managing Director": "*",
    "Production Manager": [
        "Dashboard", "Products", "Inventory", "Quality Control",
        "Procurement", "Reports", "Settings",
    ],
    "Quality Control Officer": [
        "Dashboard", "Products", "Quality Control", "Reports",
    ],
    "Storekeeper": [
        "Dashboard", "Products", "Inventory", "Warehouse",
        "Procurement", "Reports",
    ],
    "Procurement Officer": [
        "Dashboard", "Products", "Suppliers", "Procurement", "Reports",
    ],
    "Sales Officer": [
        "Dashboard", "Products", "Customers", "Sales",
        "Deliveries", "Containers", "Reports",
    ],
    "Accountant": [
        "Dashboard", "Customers", "Sales", "Procurement",
        "Reports", "Settings",
    ],
    "Driver": [
        "Dashboard", "Deliveries",
    ],
}


def get_visible_menu(role, all_items):
    """all_items: list of menu keys. Returns visible subset."""
    if not role:
        return ["Dashboard"]
    
    allowed = ROLE_MENUS.get(role, ["Dashboard"])
    if allowed == "*":
        return all_items
    
    return [m for m in all_items if m in allowed]


# Permissions matrix (static reference)
PERMISSIONS_MATRIX = [
    # (Capability, Administrator, Managing Director, Production Mgr, QC Officer,
    #  Storekeeper, Procurement Off, Sales Off, Accountant, Driver)
    ("View Dashboard",              "✅","✅","✅","✅","✅","✅","✅","✅","✅"),
    ("Manage Products",             "✅","❌","✅","✅","✅","❌","❌","❌","❌"),
    ("Manage Inventory",            "✅","❌","✅","❌","✅","❌","❌","❌","❌"),
    ("Manage Quality Control",      "✅","❌","✅","✅","❌","❌","❌","❌","❌"),
    ("Manage Suppliers",            "✅","❌","❌","❌","✅","✅","❌","❌","❌"),
    ("Manage Purchase Orders",      "✅","❌","❌","❌","✅","✅","❌","❌","❌"),
    ("Receive Goods (GRN)",         "✅","❌","❌","❌","✅","✅","❌","❌","❌"),
    ("Manage Customers",            "✅","✅","❌","❌","❌","❌","✅","✅","❌"),
    ("Manage Sales Orders",         "✅","✅","❌","❌","❌","❌","✅","✅","❌"),
    ("Manage Warehouse/Dispatch",   "✅","✅","❌","❌","✅","❌","❌","❌","❌"),
    ("Confirm Delivery",            "✅","✅","❌","❌","❌","❌","✅","❌","✅"),
    ("Manage Containers",           "✅","✅","❌","❌","✅","❌","✅","❌","❌"),
    ("Generate Invoices",           "✅","✅","❌","❌","❌","❌","✅","✅","❌"),
    ("Mark Refund Paid",            "✅","✅","❌","❌","❌","❌","❌","✅","❌"),
    ("View Reports",                "✅","✅","✅","✅","✅","✅","✅","✅","❌"),
    ("View Audit Trail",            "✅","✅","❌","❌","❌","❌","❌","✅","❌"),
    ("Backup & Restore",            "✅","❌","❌","❌","❌","❌","❌","❌","❌"),
    ("Manage Users",                "✅","❌","❌","❌","❌","❌","❌","❌","❌"),
    ("System Settings",             "✅","❌","❌","❌","❌","❌","❌","❌","❌"),
]
