# pages_users.py
# User Management UI

import streamlit as st
import pandas as pd
from datetime import datetime
from database import read_sql
from services_users import (
    get_users, get_user, create_user, update_user,
    deactivate_user, activate_user, reset_password, change_own_password,
    get_roles, get_role, create_role, update_role,
    get_users_count_by_role, get_user_activity, get_user_login_history,
    generate_temp_password,
)


def users_page():
    st.markdown("""
    <style>
        .stApp { background: linear-gradient(135deg, #e0f2fe 0%, #f0f9ff 50%, #e0f7fa 100%) !important; }
        h1, h2, h3, h4, h5, h6 { color: #0c4a6e !important; }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("<h2 style='color: #0c4a6e;'>👤 User Management</h2>", unsafe_allow_html=True)
    st.caption("Create users, assign roles, reset passwords, and manage access")

    role = st.session_state.get('role') or 'Viewer'
    is_admin = role == 'Administrator'
    is_md = role == 'Managing Director'
    can_manage = is_admin  # Only Administrator can create/edit

    tabs = ["📋 Users", "➕ Add User", "✏️ Edit User", "🛡️ Roles", "🔑 My Profile"]
    t1, t2, t3, t4, t5 = st.tabs(tabs)

    # ============================================
    # TAB 1: USERS LIST
    # ============================================
    with t1:
        st.markdown("#### 📋 Users")

        col1, col2, col3 = st.columns([2, 2, 1])
        with col1:
            search = st.text_input("🔍 Search", key="usr_search")
        with col2:
            roles_df = get_roles(active_only=False)
            role_opts = {"All Roles": None}
            role_opts.update({r['name']: r['id'] for _, r in roles_df.iterrows()})
            role_sel = st.selectbox("Role", list(role_opts.keys()), key="usr_role_filter")
        with col3:
            active_only = st.checkbox("Active only", value=False, key="usr_active_only")

        df = get_users(search=search or None,
                       role_id=role_opts[role_sel],
                       active_only=active_only)

        if df.empty:
            st.info("No users match the filter.")
        else:
            # KPI cards
            total = len(df)
            active = int((df['is_active'] == True).sum()) if 'is_active' in df.columns else 0
            c1, c2, c3 = st.columns(3)
            with c1: st.metric("Total Users", total)
            with c2: st.metric("Active", active)
            with c3: st.metric("Inactive", total - active)

            st.markdown("---")

            display = df.copy()
            display['last_login'] = display['last_login'].astype(str).replace('None', '—')
            display['is_active'] = display['is_active'].apply(lambda x: "✅ Active" if x else "❌ Inactive")
            display['must_change_password'] = display['must_change_password'].apply(
                lambda x: "🔑 Temp" if x else ""
            )
            display['full_name'] = display.apply(
                lambda r: f"{r['first_name'] or ''} {r['last_name'] or ''}".strip() or '—',
                axis=1,
            )
            display = display[['id', 'username', 'full_name', 'email', 'phone',
                              'role_name', 'is_active', 'must_change_password', 'last_login']]
            display.columns = ['ID', 'Username', 'Name', 'Email', 'Phone',
                              'Role', 'Status', 'Temp Pwd', 'Last Login']
            st.dataframe(display, use_container_width=True, hide_index=True, height=400)

            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Download Users CSV", csv,
                              f"users_{datetime.now().strftime('%Y%m%d')}.csv",
                              "text/csv")

            # User count by role
            st.markdown("---")
            st.markdown("#### 👥 Users by Role")
            by_role = get_users_count_by_role()
            if not by_role.empty:
                st.dataframe(by_role, use_container_width=True, hide_index=True)

    # ============================================
    # TAB 2: ADD USER
    # ============================================
    with t2:
        st.markdown("#### ➕ Add New User")

        if not can_manage:
            st.warning("⚠️ Only Administrator can create users.")
        else:
            roles_df = get_roles(active_only=True)
            role_opts = {r['name']: r['id'] for _, r in roles_df.iterrows()}

            with st.form("add_user_form"):
                c1, c2 = st.columns(2)
                with c1:
                    username = st.text_input("Username *", placeholder="e.g., jdoe")
                    first_name = st.text_input("First Name")
                    email = st.text_input("Email")
                    phone = st.text_input("Phone")
                with c2:
                    last_name = st.text_input("Last Name")
                    role_sel = st.selectbox("Role *", list(role_opts.keys()),
                                          key="add_usr_role")
                    is_superuser = st.checkbox("Superuser (full access)", value=False)
                    force_change = st.checkbox("Force password change on first login",
                                             value=True)

                notes = st.text_area("Notes", height=60)

                st.markdown("##### 🔑 Password")
                pwd_mode = st.radio("Password mode",
                                   ["Auto-generate temporary password",
                                    "Set a specific password"],
                                   horizontal=True, key="add_usr_pwd_mode")

                manual_pwd = None
                if pwd_mode == "Set a specific password":
                    manual_pwd = st.text_input("Password", type="password",
                                              placeholder="Min 6 characters")

                submitted = st.form_submit_button("💾 Create User", type="primary",
                                                 use_container_width=True)

                if submitted:
                    if not username:
                        st.error("❌ Username is required")
                    elif pwd_mode == "Set a specific password" and (not manual_pwd or len(manual_pwd) < 6):
                        st.error("❌ Password must be at least 6 characters")
                    else:
                        ok, msg, uid, temp_pwd = create_user(
                            username=username,
                            email=email,
                            password=manual_pwd,
                            first_name=first_name,
                            last_name=last_name,
                            phone=phone,
                            role_id=role_opts[role_sel],
                            is_superuser=is_superuser,
                            must_change_password=force_change,
                            notes=notes,
                        )
                        if ok:
                            st.success(msg)
                            if temp_pwd and pwd_mode != "Set a specific password":
                                st.warning(f"📌 Temporary password: **`{temp_pwd}`**")
                                st.info("Copy this now — it will NOT be shown again.")
                            st.balloons()
                            st.rerun()
                        else:
                            st.error(msg)

    # ============================================
    # TAB 3: EDIT USER
    # ============================================
    with t3:
        st.markdown("#### ✏️ Edit / Manage User")

        if not can_manage:
            st.warning("⚠️ Only Administrator can edit users.")
        else:
            users_df = get_users()
            if users_df.empty:
                st.info("No users yet.")
            else:
                options = {f"{r['username']} — {r.get('role_name') or 'No role'}": r['id']
                           for _, r in users_df.iterrows()}
                sel = st.selectbox("Select User", list(options.keys()), key="edit_usr_sel")
                uid = options[sel]

                u = get_user(uid)
                if u is not None:
                    roles_df = get_roles(active_only=True)
                    role_opts = {r['name']: r['id'] for _, r in roles_df.iterrows()}

                    with st.form("edit_user_form"):
                        c1, c2 = st.columns(2)
                        with c1:
                            st.text_input("Username", value=u['username'], disabled=True)
                            first_name = st.text_input("First Name", value=u['first_name'] or "")
                            email = st.text_input("Email", value=u['email'] or "")
                            phone = st.text_input("Phone", value=u['phone'] or "")
                        with c2:
                            last_name = st.text_input("Last Name", value=u['last_name'] or "")
                            current_role = u.get('role_name') or list(role_opts.keys())[0]
                            role_sel = st.selectbox("Role", list(role_opts.keys()),
                                                   index=list(role_opts.keys()).index(current_role)
                                                   if current_role in role_opts else 0)
                            is_superuser = st.checkbox("Superuser", value=bool(u['is_superuser']))
                            is_active = st.checkbox("Active", value=bool(u['is_active']))

                        notes = st.text_area("Notes", value=u.get('notes') or "", height=60)

                        c_a, c_b = st.columns(2)
                        with c_a:
                            save = st.form_submit_button("💾 Save Changes", type="primary",
                                                        use_container_width=True)
                        with c_b:
                            deactivate = st.form_submit_button("🚫 Deactivate",
                                                              use_container_width=True)

                        if save:
                            ok, msg = update_user(
                                uid,
                                first_name=first_name, last_name=last_name,
                                email=email, phone=phone,
                                role_id=role_opts[role_sel],
                                is_superuser=1 if is_superuser else 0,
                                is_active=1 if is_active else 0,
                                notes=notes,
                            )
                            if ok:
                                st.success(msg); st.rerun()
                            else:
                                st.error(msg)

                        if deactivate:
                            ok, msg = deactivate_user(uid)
                            if ok:
                                st.success("✅ User deactivated"); st.rerun()
                            else:
                                st.error(msg)

                    st.markdown("---")
                    st.markdown("#### 🔑 Reset Password")
                    st.caption("Generates a temporary password the user must change on next login.")

                    if st.button("🔄 Reset Password", key="usr_reset_pwd"):
                        ok, msg, temp = reset_password(uid, must_change=True)
                        if ok:
                            st.success(msg)
                            st.warning(f"📌 Temporary password: **`{temp}`**")
                            st.info("Copy this now — it will NOT be shown again.")

                    st.markdown("---")
                    st.markdown("#### 📊 Recent Activity")
                    activity = get_user_activity(uid, limit=30)
                    if activity.empty:
                        st.caption("No activity recorded.")
                    else:
                        st.dataframe(activity, use_container_width=True, hide_index=True)

                    st.markdown("##### 🔐 Login History")
                    logins = get_user_login_history(uid, limit=20)
                    if logins.empty:
                        st.caption("No login history.")
                    else:
                        st.dataframe(logins, use_container_width=True, hide_index=True)

    # ============================================
    # TAB 4: ROLES
    # ============================================
    with t4:
        st.markdown("#### 🛡️ Roles")

        roles_df = get_roles(active_only=False)

        if roles_df.empty:
            st.info("No roles yet.")
        else:
            st.dataframe(roles_df, use_container_width=True, hide_index=True)

        st.markdown("---")
        st.markdown("#### ➕ Add Role")

        if not can_manage:
            st.warning("⚠️ Only Administrator can add roles.")
        else:
            with st.form("add_role_form"):
                name = st.text_input("Role Name *", placeholder="e.g., Sales Manager")
                description = st.text_area("Description", height=60)
                if st.form_submit_button("💾 Create Role", type="primary",
                                        use_container_width=True):
                    if not name:
                        st.error("Role name required")
                    else:
                        ok, msg, _ = create_role(name, description)
                        if ok:
                            st.success(msg); st.rerun()
                        else:
                            st.error(msg)

        if not roles_df.empty and can_manage:
            st.markdown("---")
            st.markdown("#### ✏️ Edit Role")
            role_options = {r['name']: r['id'] for _, r in roles_df.iterrows()}
            rsel = st.selectbox("Select Role", list(role_options.keys()),
                              key="edit_role_sel")
            r = get_role(role_options[rsel])

            if r is not None:
                with st.form("edit_role_form"):
                    new_name = st.text_input("Name", value=r['name'])
                    new_desc = st.text_area("Description", value=r['description'] or "",
                                          height=60)
                    new_active = st.checkbox("Active", value=bool(r['is_active']))
                    if st.form_submit_button("💾 Save Role", type="primary",
                                           use_container_width=True):
                        ok, msg = update_role(r['id'],
                                             name=new_name,
                                             description=new_desc,
                                             is_active=1 if new_active else 0)
                        if ok:
                            st.success(msg); st.rerun()
                        else:
                            st.error(msg)

    # ============================================
    # TAB 5: MY PROFILE
    # ============================================
    with t5:
        st.markdown("#### 🔑 My Profile")

        current_id = st.session_state.get('user_id')
        current = get_user(current_id) if current_id else None

        if current is None:
            st.info("No user session.")
        else:
            c1, c2 = st.columns(2)
            with c1:
                st.info(f"**Username:** {current['username']}")
                st.info(f"**Role:** {current.get('role_name') or '—'}")
                st.info(f"**Email:** {current['email'] or '—'}")
            with c2:
                st.info(f"**Name:** {current['first_name'] or ''} {current['last_name'] or ''}")
                st.info(f"**Phone:** {current['phone'] or '—'}")
                st.info(f"**Last Login:** {current['last_login'] or '—'}")

            st.markdown("---")
            st.markdown("#### 🔒 Change My Password")

            with st.form("my_pwd_form"):
                old = st.text_input("Current Password", type="password")
                new1 = st.text_input("New Password", type="password")
                new2 = st.text_input("Confirm New Password", type="password")

                if st.form_submit_button("🔐 Change Password", type="primary",
                                        use_container_width=True):
                    if not old or not new1 or not new2:
                        st.error("All fields required")
                    elif new1 != new2:
                        st.error("New passwords do not match")
                    elif len(new1) < 6:
                        st.error("New password must be at least 6 characters")
                    else:
                        ok, msg = change_own_password(current_id, old, new1)
                        if ok:
                            st.success(msg)
                        else:
                            st.error(msg)
