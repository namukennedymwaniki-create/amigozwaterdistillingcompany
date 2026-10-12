# =========================================================
# services_permissions.py
# Role-based access control for reports & menus
# =========================================================
# Roles must match those seeded in database.py:
#   Administrator, Managing Director, Production Manager,
#   Quality Control Officer, Storekeeper, Procurement Officer,
#   Sales Officer, Accountant, Driver
# =========================================================


# =========================================================
# ROLE → MENU VISIBILITY
# =========================================================
# "*" means the role sees every menu item.
# Otherwise, only items in the list are shown.
# =========================================================

ROLE_MENUS = {
    "Administrator": "*",   # everything
    "Managing Director": "*",

    "Production Manager": [
        "Dashboard",
        "Products",
        "Inventory",
        "Quality Control",
        "Procurement",
        "Reports",
        "Settings",
    ],

    "Quality Control Officer": [
        "Dashboard",
        "Products",
        "Quality Control",
        "Reports",
    ],

    "Storekeeper": [
        "Dashboard",
        "Products",
        "Inventory",
        "Warehouse",
        "Procurement",
        "Reports",
    ],

    "Procurement Officer": [
        "Dashboard",
        "Products",
        "Suppliers",
        "Procurement",
        "Payments",       # can record supplier payments
        "Reports",
    ],

    "Sales Officer": [
        "Dashboard",
        "Products",
        "Customers",
        "Sales",
        "Deliveries",
        "Containers",
        "Payments",       # can record customer receipts
        "Reports",
    ],

    "Accountant": [
        "Dashboard",
        "Customers",
        "Sales",
        "Procurement",
        "Payments",       # core role for payments
        "Reports",
        "Settings",
    ],

    "Driver": [
        "Dashboard",
        "Deliveries",
    ],
}


def get_visible_menu(role, all_items):
    """
    Filter menu items by role.

    all_items: list of menu keys (e.g. ["Dashboard", "Products", ...])
    role: role name string (e.g. "Administrator")

    Returns a list containing only the items visible to that role.
    """
    if not role:
        return ["Dashboard"]

    allowed = ROLE_MENUS.get(role, ["Dashboard"])
    if allowed == "*":
        return all_items

    return [m for m in all_items if m in allowed]


# =========================================================
# PERMISSIONS MATRIX (Reference)
# =========================================================
# Column order:
#   Capability | Administrator | Managing Director | Production Manager
#              | Quality Control Officer | Storekeeper | Procurement Officer
#              | Sales Officer | Accountant | Driver
#
# Legend: ✅ = allowed, ❌ = not allowed
# =========================================================

PERMISSIONS_MATRIX = [
    # Core
    ("View Dashboard",
     "✅","✅","✅","✅","✅","✅","✅","✅","✅"),

    # Products & Inventory
    ("Manage Products",
     "✅","❌","✅","✅","✅","❌","❌","❌","❌"),
    ("Manage Inventory",
     "✅","❌","✅","❌","✅","❌","❌","❌","❌"),

    # Quality
    ("Manage Quality Control",
     "✅","❌","✅","✅","❌","❌","❌","❌","❌"),

    # Procurement
    ("Manage Suppliers",
     "✅","❌","❌","❌","✅","✅","❌","❌","❌"),
    ("Manage Purchase Orders",
     "✅","❌","❌","❌","✅","✅","❌","❌","❌"),
    ("Receive Goods (GRN)",
     "✅","❌","❌","❌","✅","✅","❌","❌","❌"),

    # Sales
    ("Manage Customers",
     "✅","✅","❌","❌","❌","❌","✅","✅","❌"),
    ("Manage Sales Orders",
     "✅","✅","❌","❌","❌","❌","✅","✅","❌"),

    # Warehouse & Dispatch
    ("Manage Warehouse/Dispatch",
     "✅","✅","❌","❌","✅","❌","❌","❌","❌"),

    # Delivery
    ("Confirm Delivery",
     "✅","✅","❌","❌","❌","❌","✅","❌","✅"),

    # Containers
    ("Manage Containers",
     "✅","✅","❌","❌","✅","❌","✅","❌","❌"),
    ("Mark Refund Paid",
     "✅","✅","❌","❌","❌","❌","❌","✅","❌"),

    # Invoicing
    ("Generate Invoices",
     "✅","✅","❌","❌","❌","❌","✅","✅","❌"),

    # PAYMENTS (new)
    ("Record Customer Receipts",
     "✅","✅","❌","❌","❌","❌","✅","✅","❌"),
    ("Record Supplier Payments",
     "✅","✅","❌","❌","❌","✅","❌","✅","❌"),
    ("Reverse Payments",
     "✅","✅","❌","❌","❌","❌","❌","✅","❌"),
    ("View Payment Register",
     "✅","✅","❌","❌","❌","✅","✅","✅","❌"),
    ("View Customer Statements",
     "✅","✅","❌","❌","❌","❌","✅","✅","❌"),
    ("View AR Aging",
     "✅","✅","❌","❌","❌","❌","✅","✅","❌"),

    # Reporting & Controls
    ("View Reports",
     "✅","✅","✅","✅","✅","✅","✅","✅","❌"),
    ("View Audit Trail",
     "✅","✅","❌","❌","❌","❌","❌","✅","❌"),
    ("Backup & Restore",
     "✅","❌","❌","❌","❌","❌","❌","❌","❌"),
    ("Manage Users",
     "✅","❌","❌","❌","❌","❌","❌","❌","❌"),
    ("System Settings",
     "✅","❌","❌","❌","❌","❌","❌","❌","❌"),
]


# =========================================================
# OPTIONAL: programmatic capability check
# =========================================================
def has_permission(role, capability):
    """
    Check if a role is allowed a capability by looking up the matrix.

    Usage:
        if has_permission("Accountant", "Reverse Payments"):
            ...
    """
    if not role or not capability:
        return False

    # Administrator always allowed
    if role == "Administrator":
        return True

    for row in PERMISSIONS_MATRIX:
        if row[0].lower() == capability.lower():
            # Column index by role
            role_col = {
                "Administrator": 1,
                "Managing Director": 2,
                "Production Manager": 3,
                "Quality Control Officer": 4,
                "Storekeeper": 5,
                "Procurement Officer": 6,
                "Sales Officer": 7,
                "Accountant": 8,
                "Driver": 9,
            }.get(role)

            if role_col is None:
                return False

            return row[role_col] == "✅"

    return False
