# =========================================================
# services_containers.py
# Returnable Containers Service Layer
# =========================================================
# Principles:
#   - Issuing a container to a customer = a liability (deposit owed back)
#   - Returning a container = liability reduces; deposit refunded
#   - Lost / damaged = liability forfeited, no refund
#   - Never edit a posted issue/return. Post reversals (out of scope).
# =========================================================

import streamlit as st
from datetime import datetime, date, timedelta
from sqlalchemy import text
from database import get_db_connection, log_audit, read_sql


DEFAULT_GRACE_DAYS = 30


# =========================================================
# NUMBER GENERATION
# =========================================================
def _seq(table, column, prefix):
    conn = get_db_connection()
    if not conn:
        return f"{prefix}-{datetime.now().year}-0001"
    try:
        year = datetime.now().year
        pattern = f"{prefix}-{year}-%"
        result = conn.execute(text(f"""
            SELECT {column} FROM {table}
            WHERE {column} LIKE :pat
            ORDER BY id DESC LIMIT 1
        """), {"pat": pattern}).fetchone()
        if result and result[0]:
            try:
                n = int(result[0].split("-")[-1])
                return f"{prefix}-{year}-{str(n + 1).zfill(4)}"
            except:
                return f"{prefix}-{year}-0001"
        return f"{prefix}-{year}-0001"
    except:
        return f"{prefix}-{year}-0001"
    finally:
        conn.close()


def generate_issue_number():
    return _seq("container_issues", "issue_number", "CIS")


def generate_return_number():
    return _seq("container_returns", "return_number", "CRT")


# =========================================================
# ISSUE CONTAINERS
# =========================================================
def issue_containers(customer_id, issue_date=None, order_id=None, dispatch_id=None,
                     due_date=None, notes=None, items=None):
    """
    Issue containers to a customer.
    items: [{container_id, quantity}, ...]
    deposit_per_unit is fetched from the containers table.
    """
    if not customer_id:
        return False, "Customer required", None
    if not items:
        return False, "At least one container line required", None
    
    conn = get_db_connection()
    if not conn:
        return False, "DB failed", None
    try:
        issue_number = generate_issue_number()
        issue_date = issue_date or date.today()
        due_date = due_date or (issue_date + timedelta(days=DEFAULT_GRACE_DAYS))
        
        # Fetch deposit per container
        enriched = []
        total_deposit = 0.0
        for it in items:
            c = conn.execute(text("""
                SELECT container_code, container_name, deposit_amount, is_active
                FROM containers WHERE id = :id
            """), {"id": it['container_id']}).fetchone()
            if not c:
                return False, f"Container {it['container_id']} not found", None
            if not c[3]:
                return False, f"Container '{c[1]}' is inactive", None
            if float(it['quantity']) <= 0:
                return False, f"Quantity must be positive for {c[1]}", None
            
            deposit_per_unit = float(c[2] or 0)
            line_deposit = deposit_per_unit * float(it['quantity'])
            total_deposit += line_deposit
            enriched.append({
                "container_id": it['container_id'],
                "quantity": float(it['quantity']),
                "deposit_per_unit": deposit_per_unit,
                "line_deposit": line_deposit,
            })
        
        result = conn.execute(text("""
            INSERT INTO container_issues (
                issue_number, customer_id, order_id, dispatch_id,
                issue_date, status, due_date, total_deposit,
                refunded_amount, forfeited_amount, notes, created_by,
                created_at, updated_at
            ) VALUES (
                :num, :cid, :oid, :did,
                :idate, 'Issued', :ddate, :total,
                0, 0, :notes, :uid,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            ) RETURNING id
        """), {
            "num": issue_number, "cid": customer_id, "oid": order_id,
            "did": dispatch_id, "idate": issue_date, "ddate": due_date,
            "total": total_deposit, "notes": notes,
            "uid": st.session_state.get('user_id'),
        })
        issue_id = result.fetchone()[0]
        
        for it in enriched:
            conn.execute(text("""
                INSERT INTO container_issue_items (
                    issue_id, container_id, quantity_issued,
                    quantity_returned, quantity_lost,
                    deposit_per_unit, line_deposit, created_at
                ) VALUES (
                    :iid, :cid, :qty,
                    0, 0,
                    :dpu, :line, CURRENT_TIMESTAMP
                )
            """), {
                "iid": issue_id, "cid": it['container_id'], "qty": it['quantity'],
                "dpu": it['deposit_per_unit'], "line": it['line_deposit'],
            })
        
        conn.commit()
        log_audit("ISSUE_CONTAINERS", "container_issues", issue_id,
                  new_values={"issue_number": issue_number,
                              "customer_id": customer_id,
                              "total_deposit": total_deposit})
        return True, f"✅ Issue {issue_number} created — deposit KES {total_deposit:,.2f}", issue_id
    except Exception as e:
        conn.rollback()
        return False, f"Error: {str(e)}", None
    finally:
        conn.close()


# =========================================================
# RETURN CONTAINERS
# =========================================================
def return_containers(issue_id, return_date=None, notes=None, items=None):
    """
    Return containers against an existing issue.
    items: [{issue_item_id, container_id, quantity_returned,
             quantity_lost, loss_reason}, ...]
    """
    if not items:
        return False, "At least one return line required", None
    
    conn = get_db_connection()
    if not conn:
        return False, "DB failed", None
    try:
        issue = conn.execute(text("""
            SELECT issue_number, customer_id, status FROM container_issues WHERE id = :id
        """), {"id": issue_id}).fetchone()
        if not issue:
            return False, "Issue not found", None
        if issue[2] == 'Fully Returned':
            return False, "This issue is already fully returned", None
        
        return_number = generate_return_number()
        return_date = return_date or date.today()
        
        # Validate and compute
        enriched = []
        refund_total = 0.0
        forfeit_total = 0.0
        
        for it in items:
            qi = conn.execute(text("""
                SELECT quantity_issued, quantity_returned, quantity_lost,
                       deposit_per_unit, container_id
                FROM container_issue_items WHERE id = :id
            """), {"id": it['issue_item_id']}).fetchone()
            if not qi:
                return False, f"Issue item {it['issue_item_id']} not found", None
            
            q_issued, q_returned, q_lost, dpu, container_id = qi
            q_issued = float(q_issued or 0)
            q_returned = float(q_returned or 0)
            q_lost = float(q_lost or 0)
            dpu = float(dpu or 0)
            
            outstanding = q_issued - q_returned - q_lost
            this_return = float(it.get('quantity_returned', 0) or 0)
            this_lost = float(it.get('quantity_lost', 0) or 0)
            
            if this_return < 0 or this_lost < 0:
                return False, "Quantities cannot be negative", None
            if this_return + this_lost > outstanding + 0.0001:
                return False, (f"Line {it['issue_item_id']}: return ({this_return}) + "
                              f"lost ({this_lost}) exceeds outstanding ({outstanding})"), None
            if this_lost > 0 and not it.get('loss_reason'):
                return False, "Loss reason required when lost > 0", None
            
            refund_line = this_return * dpu
            forfeit_line = this_lost * dpu
            refund_total += refund_line
            forfeit_total += forfeit_line
            
            enriched.append({
                "issue_item_id": it['issue_item_id'],
                "container_id": container_id,
                "quantity_returned": this_return,
                "quantity_lost": this_lost,
                "loss_reason": it.get('loss_reason'),
                "deposit_per_unit": dpu,
                "refund_line": refund_line,
                "forfeited_line": forfeit_line,
            })
        
        # Create return header
        result = conn.execute(text("""
            INSERT INTO container_returns (
                return_number, issue_id, customer_id, return_date,
                status, refund_amount, refund_status, notes,
                received_by, created_at, updated_at
            ) VALUES (
                :num, :iid, :cid, :rdate,
                'Received', :refund, 'Pending', :notes,
                :uid, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            ) RETURNING id
        """), {
            "num": return_number, "iid": issue_id, "cid": issue[1],
            "rdate": return_date, "refund": refund_total, "notes": notes,
            "uid": st.session_state.get('user_id'),
        })
        return_id = result.fetchone()[0]
        
        # Create return items + update issue items
        for it in enriched:
            conn.execute(text("""
                INSERT INTO container_return_items (
                    return_id, issue_item_id, container_id,
                    quantity_returned, quantity_lost, loss_reason,
                    deposit_per_unit, refund_line, forfeited_line, created_at
                ) VALUES (
                    :rid, :iiid, :cid,
                    :qret, :qlost, :lreason,
                    :dpu, :refund, :forfeit, CURRENT_TIMESTAMP
                )
            """), {
                "rid": return_id, "iiid": it['issue_item_id'],
                "cid": it['container_id'],
                "qret": it['quantity_returned'], "qlost": it['quantity_lost'],
                "lreason": it['loss_reason'], "dpu": it['deposit_per_unit'],
                "refund": it['refund_line'], "forfeit": it['forfeited_line'],
            })
            
            conn.execute(text("""
                UPDATE container_issue_items
                SET quantity_returned = quantity_returned + :qret,
                    quantity_lost = quantity_lost + :qlost
                WHERE id = :id
            """), {
                "qret": it['quantity_returned'],
                "qlost": it['quantity_lost'],
                "id": it['issue_item_id'],
            })
        
        # Update issue header status
        _refresh_issue_status(conn, issue_id)
        
        # Update refunded/forfeited totals on issue header
        conn.execute(text("""
            UPDATE container_issues
            SET refunded_amount = refunded_amount + :r,
                forfeited_amount = forfeited_amount + :f,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = :id
        """), {"r": refund_total, "f": forfeit_total, "id": issue_id})
        
        conn.commit()
        log_audit("RETURN_CONTAINERS", "container_returns", return_id,
                  new_values={"return_number": return_number,
                              "issue_id": issue_id,
                              "refund": refund_total,
                              "forfeited": forfeit_total})
        
        return True, (f"✅ Return {return_number} created — "
                     f"refund KES {refund_total:,.2f}, "
                     f"forfeited KES {forfeit_total:,.2f}"), return_id
    except Exception as e:
        conn.rollback()
        return False, f"Error: {str(e)}", None
    finally:
        conn.close()


def _refresh_issue_status(conn, issue_id):
    """Internal helper: update issue status based on outstanding qty"""
    row = conn.execute(text("""
        SELECT 
            SUM(quantity_issued) as issued,
            SUM(quantity_returned + quantity_lost) as done
        FROM container_issue_items
        WHERE issue_id = :iid
    """), {"iid": issue_id}).fetchone()
    
    if not row or row[0] is None:
        return
    issued = float(row[0] or 0)
    done = float(row[1] or 0)
    
    if done < issued - 0.0001:
        new_status = 'Partially Returned' if done > 0 else 'Issued'
    else:
        new_status = 'Fully Returned'
    
    conn.execute(text("""
        UPDATE container_issues SET status = :st, updated_at = CURRENT_TIMESTAMP
        WHERE id = :id
    """), {"st": new_status, "id": issue_id})


# =========================================================
# MARK REFUND PAID
# =========================================================
def mark_refund_paid(return_id, notes=None):
    """Finance marks refund as paid"""
    conn = get_db_connection()
    if not conn:
        return False, "DB failed"
    try:
        row = conn.execute(text("""
            SELECT return_number, refund_status FROM container_returns WHERE id = :id
        """), {"id": return_id}).fetchone()
        if not row:
            return False, "Return not found"
        if row[1] == 'Paid':
            return False, "Refund already marked paid"
        
        conn.execute(text("""
            UPDATE container_returns
            SET refund_status = 'Paid',
                refunded_by = :uid,
                refunded_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP,
                notes = COALESCE(notes,'') || COALESCE(:notes,'')
            WHERE id = :id
        """), {"id": return_id, "uid": st.session_state.get('user_id'),
               "notes": f"\n[REFUNDED] {notes or ''}"})
        conn.commit()
        log_audit("MARK_REFUND_PAID", "container_returns", return_id)
        return True, f"✅ Refund marked paid for {row[0]}"
    except Exception as e:
        conn.rollback()
        return False, f"Error: {e}"
    finally:
        conn.close()


# =========================================================
# AUTO-ISSUE FOR AN ORDER
# =========================================================
def auto_issue_for_order(order_id, dispatch_id=None, notes=None):
    """
    Given a sales order, look for products that are returnable containers
    (products whose category is 'Containers' or product_code starts with 'CON-')
    and auto-issue them. Requires the order to have those lines.
    
    NOTE: Only issues lines that match a `containers.container_code` exactly.
    """
    conn = get_db_connection()
    if not conn:
        return False, "DB failed", None
    try:
        cust = conn.execute(text("""
            SELECT customer_id, order_number FROM sales_orders WHERE id = :id
        """), {"id": order_id}).fetchone()
        if not cust:
            return False, "Order not found", None
        customer_id, order_number = cust
        
        # Find matching container lines
        rows = conn.execute(text("""
            SELECT soi.product_id, soi.quantity_ordered, p.product_code,
                   c.id as container_id
            FROM sales_order_items soi
            JOIN products p ON soi.product_id = p.id
            JOIN containers c ON UPPER(c.container_code) = UPPER(p.product_code)
            WHERE soi.order_id = :oid
        """), {"oid": order_id}).fetchall()
        
        if not rows:
            return False, "No returnable container lines found on this order", None
        
        items = [{"container_id": r[3], "quantity": float(r[1])} for r in rows]
        
        return issue_containers(
            customer_id=customer_id,
            order_id=order_id,
            dispatch_id=dispatch_id,
            notes=notes or f"Auto-issue for order {order_number}",
            items=items,
        )
    except Exception as e:
        return False, f"Error: {str(e)}", None
    finally:
        conn.close()


# =========================================================
# QUERIES
# =========================================================
def get_containers(active_only=True):
    q = "SELECT * FROM containers WHERE 1=1"
    if active_only:
        q += " AND is_active = 1"
    q += " ORDER BY container_code"
    return read_sql(q)


def get_issues(status_filter=None, customer_id=None, search=None):
    q = """
        SELECT 
            ci.id, ci.issue_number, ci.issue_date, ci.due_date, ci.status,
            ci.total_deposit, ci.refunded_amount, ci.forfeited_amount,
            c.customer_code, c.customer_name,
            so.order_number,
            (SELECT COUNT(*) FROM container_issue_items WHERE issue_id = ci.id) as items_count
        FROM container_issues ci
        LEFT JOIN customers c ON ci.customer_id = c.id
        LEFT JOIN sales_orders so ON ci.order_id = so.id
        WHERE 1=1
    """
    params = {}
    if status_filter and status_filter != "All":
        q += " AND ci.status = :st"; params["st"] = status_filter
    if customer_id:
        q += " AND ci.customer_id = :cid"; params["cid"] = customer_id
    if search:
        q += " AND (LOWER(ci.issue_number) LIKE :s OR LOWER(c.customer_name) LIKE :s)"
        params["s"] = f"%{search.lower()}%"
    q += " ORDER BY ci.id DESC LIMIT 500"
    return read_sql(q, params if params else None)


def get_issue(issue_id):
    df = read_sql("""
        SELECT ci.*, c.customer_code, c.customer_name,
               c.address as customer_address, c.phone as customer_phone,
               so.order_number
        FROM container_issues ci
        LEFT JOIN customers c ON ci.customer_id = c.id
        LEFT JOIN sales_orders so ON ci.order_id = so.id
        WHERE ci.id = :id
    """, {"id": issue_id})
    return None if df.empty else df.iloc[0]


def get_issue_items(issue_id):
    return read_sql("""
        SELECT cii.*, c.container_code, c.container_name,
               (cii.quantity_issued - cii.quantity_returned - cii.quantity_lost) as outstanding
        FROM container_issue_items cii
        JOIN containers c ON cii.container_id = c.id
        WHERE cii.issue_id = :iid
        ORDER BY cii.id
    """, {"iid": issue_id})


def get_returns(status_filter=None, search=None):
    q = """
        SELECT 
            cr.id, cr.return_number, cr.return_date, cr.status,
            cr.refund_amount, cr.refund_status,
            c.customer_code, c.customer_name,
            ci.issue_number,
            (SELECT COUNT(*) FROM container_return_items WHERE return_id = cr.id) as items_count
        FROM container_returns cr
        LEFT JOIN customers c ON cr.customer_id = c.id
        LEFT JOIN container_issues ci ON cr.issue_id = ci.id
        WHERE 1=1
    """
    params = {}
    if status_filter and status_filter != "All":
        q += " AND cr.refund_status = :st"; params["st"] = status_filter
    if search:
        q += " AND (LOWER(cr.return_number) LIKE :s OR LOWER(c.customer_name) LIKE :s)"
        params["s"] = f"%{search.lower()}%"
    q += " ORDER BY cr.id DESC LIMIT 500"
    return read_sql(q, params if params else None)


def get_return(return_id):
    df = read_sql("""
        SELECT cr.*, c.customer_code, c.customer_name, ci.issue_number
        FROM container_returns cr
        LEFT JOIN customers c ON cr.customer_id = c.id
        LEFT JOIN container_issues ci ON cr.issue_id = ci.id
        WHERE cr.id = :id
    """, {"id": return_id})
    return None if df.empty else df.iloc[0]


def get_return_items(return_id):
    return read_sql("""
        SELECT cri.*, c.container_code, c.container_name
        FROM container_return_items cri
        JOIN containers c ON cri.container_id = c.id
        WHERE cri.return_id = :id
        ORDER BY cri.id
    """, {"id": return_id})


# =========================================================
# CUSTOMER CONTAINER BALANCE
# =========================================================
def get_customer_container_balance(customer_id=None):
    """For each customer, show outstanding containers by type"""
    q = """
        SELECT
            c.id as customer_id,
            c.customer_code,
            c.customer_name,
            cnt.container_code,
            cnt.container_name,
            SUM(cii.quantity_issued - cii.quantity_returned - cii.quantity_lost) as outstanding_qty,
            SUM((cii.quantity_issued - cii.quantity_returned - cii.quantity_lost) * cii.deposit_per_unit) as outstanding_deposit
        FROM container_issue_items cii
        JOIN container_issues ci ON cii.issue_id = ci.id
        JOIN customers c ON ci.customer_id = c.id
        JOIN containers cnt ON cii.container_id = cnt.id
        WHERE ci.status != 'Fully Returned'
    """
    params = {}
    if customer_id:
        q += " AND c.id = :cid"
        params["cid"] = customer_id
    q += """
        GROUP BY c.id, c.customer_code, c.customer_name,
                 cnt.container_code, cnt.container_name
        HAVING SUM(cii.quantity_issued - cii.quantity_returned - cii.quantity_lost) > 0
        ORDER BY c.customer_name, cnt.container_code
    """
    return read_sql(q, params if params else None)


def get_overdue_issues():
    """Issues past due_date with outstanding containers"""
    today = date.today()
    return read_sql("""
        SELECT 
            ci.id, ci.issue_number, ci.issue_date, ci.due_date,
            ci.status, ci.total_deposit, ci.refunded_amount, ci.forfeited_amount,
            c.customer_name,
            (ci.due_date - :today) as days_overdue
        FROM container_issues ci
        JOIN customers c ON ci.customer_id = c.id
        WHERE ci.status IN ('Issued', 'Partially Returned')
          AND ci.due_date < :today
        ORDER BY ci.due_date ASC
    """, {"today": today})


def get_company_balance():
    """Company-wide container position"""
    return read_sql("""
        SELECT
            cnt.container_code,
            cnt.container_name,
            SUM(cii.quantity_issued) as total_issued,
            SUM(cii.quantity_returned) as total_returned,
            SUM(cii.quantity_lost) as total_lost,
            SUM(cii.quantity_issued - cii.quantity_returned - cii.quantity_lost) as still_with_customers,
            SUM((cii.quantity_issued - cii.quantity_returned - cii.quantity_lost) * cii.deposit_per_unit) as deposits_held
        FROM container_issue_items cii
        JOIN containers cnt ON cii.container_id = cnt.id
        GROUP BY cnt.container_code, cnt.container_name
        ORDER BY cnt.container_code
    """)
