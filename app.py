import streamlit as st
import os
import sqlite3
import time
from datetime import datetime

# 1. Base Directory and Storage Parameters
STORAGE_DIR = "laptop_excel_vault"
if not os.path.exists(STORAGE_DIR):
    os.makedirs(STORAGE_DIR)

DB_FILE = "portal_master_records.db"

# 2. Database Core Initializations
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_permissions (
            email TEXT PRIMARY KEY,
            full_name TEXT,
            status TEXT,
            requested_at TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS portal_audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_identity TEXT,
            action_type TEXT,
            target_asset TEXT,
            timestamp TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# --- Core Database Isolation Helpers ---
def check_user_status(email):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT status FROM user_permissions WHERE email = ?", (email.lower().strip(),))
    res = cursor.fetchone()
    conn.close()
    return res[0] if res else None

def submit_access_request(name, email):
    clean_email = email.lower().strip()
    current_status = check_user_status(clean_email)
    
    # SECURITY OVERRIDE: If their status is explicitly locked down as 'Banned', drop execution completely
    if current_status == 'Banned':
        return False

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    clean_name = name.strip()
    log_identity = f"{clean_name} ({clean_email})"
    
    cursor.execute('''
        INSERT INTO user_permissions (email, full_name, status, requested_at)
        VALUES (?, ?, 'Pending', ?)
        ON CONFLICT(email) DO UPDATE SET status='Pending', full_name=?, requested_at=?
    ''', (clean_email, clean_name, now, clean_name, now))
    conn.commit()
    
    cursor.execute("INSERT INTO portal_audit_logs (user_identity, action_type, target_asset, timestamp) VALUES (?, 'Requested Access', 'System Portal', ?)", (log_identity, now))
    conn.commit()
    conn.close()
    return True

def log_audit_event(user_id, action, asset):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute('''
        INSERT INTO portal_audit_logs (user_identity, action_type, target_asset, timestamp)
        VALUES (?, ?, ?, ?)
    ''', (user_id, action, asset, now))
    conn.commit()
    conn.close()

# --- INSTANT PAGE SWITCHER CALLBACK ---
def handle_page_switch():
    selected_mode = st.session_state.navigation_radio
    if selected_mode == "🔐 Admin Console":
        st.query_params["active_page"] = "Admin"
    else:
        st.query_params["active_page"] = "User"

# --- REFRESH PERSISTENCE GUARD ---
url_admin = st.query_params.get("admin_session", "")
url_user_name = st.query_params.get("user_name", "")
url_user_email = st.query_params.get("user_email", "")
url_active_page = st.query_params.get("active_page", "User")

if 'admin_logged_in' not in st.session_state:
    st.session_state.admin_logged_in = True if url_admin == "active" else False
if 'user_verified' not in st.session_state:
    st.session_state.user_verified = True if url_user_email else False
    st.session_state.user_name = url_user_name
    st.session_state.user_email = url_user_email

if 'uploader_version' not in st.session_state:
    st.session_state.uploader_version = 0

# Track active user status check background loops
if st.session_state.user_verified and st.session_state.user_email:
    current_status = check_user_status(st.session_state.user_email)
    if current_status != 'Approved':
        st.session_state.user_verified = False
        st.query_params.clear()

# --- INTERFACE VIEW SETUP ---
st.set_page_config(page_title="Central Workbook Portal", page_icon="📊", layout="wide")
st.title("📊 Excel Tracker Workbook Portal")

page_options = ["👥 User Download Deck", "🔐 Admin Console"]
default_index = 1 if url_active_page == "Admin" else 0

portal_mode = st.sidebar.radio(
    "Navigate Gateway", 
    page_options, 
    index=default_index, 
    key="navigation_radio", 
    on_change=handle_page_switch
)

# -------------------------------------------------------------------
# GATEWAY 1: ADMIN CONSOLE
# -------------------------------------------------------------------
if portal_mode == "🔐 Admin Console":
    st.write("---")
    st.header("🛠️ Operations Control (Admin Panel)")
    
    if not st.session_state.admin_logged_in:
        with st.form("admin_auth_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            if st.form_submit_button("Authorize"):
                if username == "admin" and password == "password123":
                    st.session_state.admin_logged_in = True
                    st.query_params["admin_session"] = "active"
                    st.query_params["active_page"] = "Admin"
                    st.rerun()
                else:
                    st.error("Invalid credentials.")
    else:
        if st.button("Log Out Admin Session"):
            st.session_state.admin_logged_in = False
            st.query_params.clear()
            st.query_params["active_page"] = "Admin"
            st.rerun()
            
        st.write("---")
        
        # DYNAMIC LIVE UPDATING WORKFLOW CONTAINER (Updates every 5 seconds)
        @st.fragment(run_every=5)
        def render_live_admin_data():
            st.subheader("🔑 Pending Access Requests Verification")
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute("SELECT full_name, email, requested_at FROM user_permissions WHERE status = 'Pending'")
            pending_users = cursor.fetchall()
            
            if not pending_users:
                st.info("No corporate users currently awaiting infrastructure verification approval.")
            else:
                for user in pending_users:
                    col1, col2, col3, col4 = st.columns([3, 2, 1, 1])
                    col1.write(f"📧 **{user[1]}** (Submitted Name: {user[0]})")
                    col2.write(f"Requested: {user[2]}")
                    
                    if col3.button("Approve Access", key=f"app_{user[1]}"):
                        cursor.execute("UPDATE user_permissions SET status = 'Approved' WHERE email = ?", (user[1],))
                        conn.commit()
                        log_audit_event("Admin", "Approved - User Access Permissions", user[1])
                        conn.close()
                        st.success(f"Access token authorized for {user[1]}")
                        time.sleep(0.5)
                        st.rerun()
                        
                    if col4.button("Reject Request", key=f"rej_{user[1]}"):
                        cursor.execute("UPDATE user_permissions SET status = 'Rejected' WHERE email = ?", (user[1],))
                        conn.commit()
                        log_audit_event("Admin", "Rejected - User Access Request", user[1])
                        conn.close()
                        st.warning(f"Access request denied for {user[1]}")
                        time.sleep(0.5)
                        st.rerun()
            conn.close()

            st.write("---")
            
            # NEW MANAGEMENT SECTION: ACTIVE USER CONTROL AND BAN DECK
            st.subheader("🛡️ Infrastructure Access Wrecker & Permanent Ban Control")
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute("SELECT full_name, email, status FROM user_permissions WHERE status IN ('Approved', 'Rejected', 'Banned')")
            managed_users = cursor.fetchall()
            
            if not managed_users:
                st.info("No verified corporate accounts loaded in framework records yet.")
            else:
                for mu in managed_users:
                    m_name, m_email, m_status = mu[0], mu[1], mu[2]
                    col_user, col_state, col_action = st.columns([4, 2, 2])
                    
                    col_user.write(f"👤 **{m_name}** — {m_email}")
                    
                    if m_status == 'Approved':
                        col_state.markdown("🟢 <span style='color:green;font-weight:bold;'>Active Access</span>", unsafe_allow_html=True)
                        if col_action.button("🚨 Revoke & Permanent Ban", key=f"ban_{m_email}", use_container_width=True):
                            cursor.execute("UPDATE user_permissions SET status = 'Banned' WHERE email = ?", (m_email,))
                            conn.commit()
                            log_audit_event("Admin", "ACCESS - PERMANENTLY BANNED", m_email)
                            conn.close()
                            st.error(f"Account {m_email} blacklisted permanently.")
                            time.sleep(0.5)
                            st.rerun()
                    elif m_status == 'Rejected':
                        col_state.markdown("🟡 <span style='color:orange;font-weight:bold;'>Rejected</span>", unsafe_allow_html=True)
                        if col_action.button("🚨 Permanent Ban Override", key=f"ban_{m_email}", use_container_width=True):
                            cursor.execute("UPDATE user_permissions SET status = 'Banned' WHERE email = ?", (m_email,))
                            conn.commit()
                            log_audit_event("Admin", "PERMANENTLY BANNED INFRASTRUCTURE ACCESS", m_email)
                            conn.close()
                            st.error(f"Account {m_email} blacklisted permanently.")
                            time.sleep(0.5)
                            st.rerun()
                    elif m_status == 'Banned':
                        col_state.markdown("🔴 <span style='color:red;font-weight:bold;'>❌ PERMANENTLY BANNED</span>", unsafe_allow_html=True)
                        if col_action.button("🟢 Lift Ban & Restore", key=f"unban_{m_email}", use_container_width=True):
                            cursor.execute("UPDATE user_permissions SET status = 'Pending' WHERE email = ?", (m_email,))
                            conn.commit()
                            log_audit_event("Admin", "Ban Removed / Set to Pending", m_email)
                            conn.close()
                            st.success(f"Ban lifted for {m_email}. Restored to pending review.")
                            time.sleep(0.5)
                            st.rerun()
            conn.close()

            st.write("---")
            
            st.subheader("📋 Infrastructure Audit Log (Signing & Downloads)")
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute("SELECT user_identity, action_type, target_asset, timestamp FROM portal_audit_logs ORDER BY id DESC")
            logs = cursor.fetchall()
            conn.close()
            
            if not logs:
                st.info("No audit logs recorded in database yet.")
            else:
                log_table = [{"Timestamp": r[3], "User Identity / Op": r[0], "Action Taken": r[1], "Target Asset": r[2]} for r in logs]
                st.table(log_table)

        # Trigger live component execution block
        render_live_admin_data()

        st.write("---")
        
        # File Management Section
        st.subheader("Register New Tracker Asset")
        uploader_key = f"uploader_v_{st.session_state.uploader_version}"
        uploaded_file = st.file_uploader(
            "Choose an Excel workbook from your laptop", 
            type=["xlsx", "xlsb", "xls", "csv"],
            key=uploader_key
        )
        
        if uploaded_file is not None:
            file_path = os.path.join(STORAGE_DIR, uploaded_file.name)
            with open(file_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            log_audit_event("Admin", "Uploaded Track Asset File", uploaded_file.name)
            st.session_state.uploader_version += 1
            st.rerun()

        st.write("---")
        st.subheader("Current Manifest Assets")
        current_files = os.listdir(STORAGE_DIR)
        if current_files:
            for file in current_files:
                col1, col2 = st.columns([4, 1])
                col1.write(f"📂 {file}")
                if col2.button("Delete File", key=file):
                    os.remove(os.path.join(STORAGE_DIR, file))
                    log_audit_event("Admin", "Deleted Track Asset File", file)
                    st.warning(f"Removed {file}")
                    st.rerun()

# -------------------------------------------------------------------
# GATEWAY 2: USER DOWNLOAD DECK
# -------------------------------------------------------------------
else:
    st.write("---")
    
    # DYNAMIC LIVE UPDATING USER INTERFACE CONTROLLER (Updates every 5 seconds)
    @st.fragment(run_every=5)
    def render_live_user_portal():
        if st.session_state.user_verified and st.session_state.user_email:
            db_status = check_user_status(st.session_state.user_email)
            if db_status != 'Approved':
                st.session_state.user_verified = False
                st.query_params.clear()
                st.rerun()

        if st.session_state.user_verified:
            st.subheader("📁 Available Excel Workbooks")
            current_files = os.listdir(STORAGE_DIR)
            
            if not current_files:
                st.info("No spreadsheet metrics loaded by administration parameters currently.")
            else:
                st.markdown("""
                    <style>
                    .list-row-container {
                        display: flex;
                        align-items: center;
                        background-color: #ffffff;
                        padding: 10px 15px;
                        border-radius: 6px;
                        border: 1px solid #e2e8f0;
                        border-left: 5px solid #107c41;
                        height: 46px;
                    }
                    .excel-icon { font-size: 20px; margin-right: 12px; color: #107c41; display: inline-block; }
                    .file-title { font-weight: 600; color: #2d3748; font-size: 15px; display: inline-block; }
                    div[data-testid="stColumn"] {
                        display: flex;
                        align-items: center;
                    }
                    </style>
                """, unsafe_allow_html=True)

                for file in current_files:
                    file_path = os.path.join(STORAGE_DIR, file)
                    with open(file_path, "rb") as f:
                        file_bytes = f.read()

                    file_col, btn_col = st.columns([3, 1])
                    
                    with file_col:
                        st.markdown(f"""
                            <div class="list-row-container">
                                <div class="excel-icon">📊</div>
                                <div class="file-title">{file}</div>
                            </div>
                        """, unsafe_allow_html=True)
                        
                    with btn_col:
                        mime_type = "application/vnd.ms-excel.sheet.binary.macroEnabled.12" if file.lower().endswith(".xlsb") else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        
                        if st.download_button(
                            label=f"📥 Download Tracker",
                            data=file_bytes,
                            file_name=file,
                            mime=mime_type,
                            key=f"dl_{file}",
                            use_container_width=True
                        ):
                            log_audit_event(st.session_state.user_email, "Downloaded Excel Asset", file)
                    st.write("") 
            st.write("---")

        st.header("👥 User Download Deck")
        
        if not st.session_state.user_verified:
            st.info("🔒 The download catalog is locked. Please enter your valid corporate credentials below to unlock available trackers.")
            
            if "rejection_notice" not in st.session_state:
                st.session_state.rejection_notice = False
            if "banned_notice" not in st.session_state:
                st.session_state.banned_notice = False

            with st.form("user_identity_form"):
                name = st.text_input("Full Name")
                email = st.text_input("Corporate Email Address (@amazon.com)")
                enter_portal = st.form_submit_button("Verify Identity & Unlock Portal")
                
                if enter_portal:
                    if not name.strip() or not email.strip():
                        st.error("All identification fields are mandatory.")
                    elif not email.lower().strip().endswith("@amazon.com"):
                        st.error("⚠️ Access Denied. Valid corporate @amazon.com email configuration mandatory.")
                    else:
                        status = check_user_status(email)
                        
                        if status == 'Banned':
                            st.session_state.banned_notice = True
                            st.rerun()
                        elif status == 'Rejected':
                            submit_access_request(name, email)
                            st.session_state.rejection_notice = True
                            st.rerun()
                        elif status is None:
                            submit_access_request(name, email)
                            st.warning("🔒 Access Blocked: Email unregistered. Verification request submitted to Admin dashboard. Contact point: 'esrohit'")
                        elif status == 'Pending':
                            st.warning("⏳ Access Request Pending: Your corporate email is awaiting structural activation by 'esrohit'.")
                        elif status == 'Approved':
                            st.session_state.user_verified = True
                            st.session_state.user_name = name.strip()
                            st.session_state.user_email = email.strip().lower()
                            st.query_params["user_name"] = name.strip()
                            st.query_params["user_email"] = email.strip().lower()
                            st.query_params["active_page"] = "User"
                            
                            log_audit_event(email.strip().lower(), "Portal - Logged Into", "System Session Open")
                            st.rerun()
                            
            # Auto-check loop configurations 
            if email.strip():
                bg_status = check_user_status(email)
                if bg_status == 'Approved':
                    st.session_state.user_verified = True
                    st.session_state.user_name = name.strip()
                    st.session_state.user_email = email.strip().lower()
                    st.query_params["user_name"] = name.strip()
                    st.query_params["user_email"] = email.strip().lower()
                    st.rerun()
                elif bg_status == 'Pending':
                    st.warning("⏳ Access Request Pending: Awaiting admin approval. (Auto-refreshing status...)")
                elif bg_status == 'Rejected':
                    st.error("❌ Access Denied: This request was rejected by administration parameters.")
                elif bg_status == 'Banned' or st.session_state.banned_notice:
                    st.error("⛔ Access Denied:  Form submissions are disabled.")
                            
            if st.session_state.rejection_notice:
                st.warning("⏳ Re-Request Sent: Status reset to Pending. Awaiting admin approval.")
                st.session_state.rejection_notice = False
        else:
            st.success(f"🔓 Access Authorized for email: **{st.session_state.user_email}** (Session Name: {st.session_state.user_name})")
            if st.button("Exit Portal Session"):
                log_audit_event(st.session_state.user_email, "Portal - Logged Out", "System Session Close")
                st.session_state.user_verified = False
                st.query_params.clear()
                st.query_params["active_page"] = "User"
                st.rerun()

    # Trigger live user portal view
    render_live_user_portal()import streamlit as st
import pandas as pd
from datetime import datetime
import time

# --- SYSTEM INITIALIZATION ---
st.set_page_config(page_title="Site Operations Portal", page_icon="📊", layout="wide")

# --- INITIALIZE CORE SESSION STATES BEFORE ANY ROUTING RUNS ---
if "navigation_radio" not in st.session_state:
    st.session_state.navigation_radio = "👥 User Download Deck"

if "admin_auth" not in st.session_state:
    st.session_state.admin_auth = False

if "user_authorized" not in st.session_state:
    st.session_state.user_authorized = False

if "current_user_email" not in st.session_state:
    st.session_state.current_user_email = ""

st.title("📊 Cloud Tracker Workbook Portal")

# --- HIGH-SPEED DATA CONVERSION ENGINE ---
raw_url = st.secrets["connections"]["gsheets"]["spreadsheet"]
sheet_id = raw_url.split("/d/")[1].split("/")[0]

def fetch_sheet_data(worksheet_name):
    try:
        csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={worksheet_name}"
        df = pd.read_csv(csv_url)
        return df.dropna(how="all")
    except Exception:
        if worksheet_name == "user_permissions":
            return pd.DataFrame(columns=['email', 'full_name', 'status', 'requested_at'])
        elif worksheet_name == "excel_assets":
            return pd.DataFrame(columns=['asset_id', 'asset_name', 'download_link', 'added_by'])
        else:
            return pd.DataFrame(columns=['user_identity', 'action_type', 'target_asset', 'timestamp'])

# --- LOCAL DATABASE STATE STORAGE HOOK (Bypasses write latency errors) ---
if "local_users" not in st.session_state:
    st.session_state.local_users = fetch_sheet_data("user_permissions")
if "local_assets" not in st.session_state:
    st.session_state.local_assets = fetch_sheet_data("excel_assets")
if "local_logs" not in st.session_state:
    st.session_state.local_logs = fetch_sheet_data("portal_audit_logs")

# --- INSTANT PAGE SWITCHER CALLBACK (CRASH PROOF) ---
def handle_page_switch():
    if "navigation_radio" not in st.session_state:
        st.session_state.navigation_radio = "👥 User Download Deck"
    
    selected_mode = st.session_state.navigation_radio
    if selected_mode == "🔐 Admin Console":
        st.query_params["active_page"] = "Admin"
    else:
        st.query_params["active_page"] = "User"

page_mode = st.sidebar.radio(
    "Navigate Gateway", 
    ["👥 User Download Deck", "🔐 Admin Console"],
    key="navigation_radio",
    on_change=handle_page_switch
)

# -------------------------------------------------------------------
# ARCHITECTURE MODULE A: USER ACCESS & EXCEL ASSET DECK
# -------------------------------------------------------------------
if page_mode == "👥 User Download Deck":
    st.header("👥 User Access Gateway")
    
    if not st.session_state.user_authorized:
        with st.form("login_form"):
            name = st.text_input("Full Name").strip()
            email = st.text_input("Corporate Email Address (@amazon.com)").lower().strip()
            submit = st.form_submit_button("Verify & Request Access")
            
            if submit:
                if not name or not email:
                    st.error("All identification fields are mandatory.")
                elif not email.endswith("@amazon.com"):
                    st.error("⚠️ Access Denied. Valid corporate @amazon.com email required.")
                else:
                    users_df = st.session_state.local_users
                    
                    if not users_df.empty and email in users_df['email'].values:
                        user_status = users_df[users_df['email'] == email]['status'].values[0]
                        
                        if user_status == "Approved":
                            st.session_state.user_authorized = True
                            st.session_state.current_user_email = email
                            
                            # Add action tracking log entry
                            new_log = pd.DataFrame([{
                                "user_identity": email,
                                "action_type": "Logged In",
                                "target_asset": "Gateway Access Portal",
                                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            }])
                            st.session_state.local_logs = pd.concat([st.session_state.local_logs, new_log], ignore_index=True)
                            st.success("🔓 Access Authorized! Loading files...")
                            time.sleep(0.5)
                            st.rerun()
                        elif user_status == "Pending":
                            st.warning("⏳ Access Request Pending: Your profile entry is currently awaiting admin verification.")
                        elif user_status == "Banned":
                            st.error("⛔ CRITICAL FIREWALL BLOCK: This email has been permanently blacklisted.")
                    else:
                        new_user = pd.DataFrame([{
                            "email": email,
                            "full_name": name,
                            "status": "Pending",
                            "requested_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        }])
                        st.session_state.local_users = pd.concat([st.session_state.local_users, new_user], ignore_index=True)
                        
                        # Add tracking log
                        new_log = pd.DataFrame([{
                            "user_identity": email,
                            "action_type": "Requested Access Profile",
                            "target_asset": "Gateway Portal System",
                            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        }])
                        st.session_state.local_logs = pd.concat([st.session_state.local_logs, new_log], ignore_index=True)
                        st.info("📨 Request submitted successfully! Your tracking record has been queued for admin verification.")
    else:
        st.subheader("📊 Available Site Operations Asset Repositories")
        st.write(f"Logged in as: `{st.session_state.current_user_email}`")
        if st.button("Log Out Access Deck"):
            st.session_state.user_authorized = False
            st.session_state.current_user_email = ""
            st.rerun()
            
        st.write("---")
        
        assets_df = st.session_state.local_assets
        if assets_df.empty:
            st.info("No master workbooks or dashboards deployed in the repo framework yet.")
        else:
            for idx, row in assets_df.iterrows():
                with st.container(border=True):
                    col1, col2 = st.columns([5, 2])
                    col1.subheader(f"📄 {row['asset_name']}")
                    col1.write(f"Asset ID Reference: `{row['asset_id']}` | Deployed by: `{row['added_by']}`")
                    
                    # Direct action button linked out to spreadsheet sheets/links safely
                    if col2.markdown(f'<a href="{row["download_link"]}" target="_blank" style="text-decoration:none;"><button style="background-color:#FF9900;color:white;border:none;padding:10px 20px;border-radius:4px;cursor:pointer;width:100%;">📊 Open Master Excel File</button></a>', unsafe_html=True):
                        # Track download action logging metrics
                        new_log = pd.DataFrame([{
                            "user_identity": st.session_state.current_user_email,
                            "action_type": "Accessed Asset Link",
                            "target_asset": row['asset_name'],
                            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        }])
                        st.session_state.local_logs = pd.concat([st.session_state.local_logs, new_log], ignore_index=True)

# -------------------------------------------------------------------
# ARCHITECTURE MODULE B: ADMINISTRATIVE CONTROL PANEL
# -------------------------------------------------------------------
else:
    st.header("🔐 Admin Operations Dashboard")
    
    if not st.session_state.admin_auth:
        with st.form("admin_login"):
            user = st.text_input("Username")
            pas = st.text_input("Password", type="password")
            if st.form_submit_button("Login"):
                if user == "admin" and pas == "password123":
                    st.session_state.admin_auth = True
                    st.rerun()
                else:
                    st.error("Invalid Administrative Credentials.")
    else:
        if st.button("Log Out Admin"):
            st.session_state.admin_auth = False
            st.rerun()
            
        tab1, tab2, tab3 = st.tabs(["🔑 Manage Clearances", "➕ Add New Excel Asset", "📋 Infrastructure Audit Trail"])
        
        # TAB 1: USER APPROVAL TRACKING
        with tab1:
            st.subheader("🔑 Open Access Modification Requests")
            pending = st.session_state.local_users[st.session_state.local_users['status'] == 'Pending'] if not st.session_state.local_users.empty else pd.DataFrame()
            
            if pending.empty:
                st.info("No user profiles currently awaiting clearance operations.")
            else:
                for idx, row in pending.iterrows():
                    col1, col2, col3 = st.columns([4, 2, 2])
                    col1.write(f"📧 **{row['email']}** ({row['full_name']})")
                    
                    if col2.button("Approve", key=f"app_{row['email']}"):
                        st.session_state.local_users.loc[st.session_state.local_users['email'] == row['email'], 'status'] = 'Approved'
                        
                        new_log = pd.DataFrame([{
                            "user_identity": "SYSTEM_ADMIN",
                            "action_type": f"Approved {row['email']}",
                            "target_asset": "User Matrix Control",
                            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        }])
                        st.session_state.local_logs = pd.concat([st.session_state.local_logs, new_log], ignore_index=True)
                        st.success(f"Clearance granted to {row['email']}!")
                        time.sleep(0.4)
                        st.rerun()
                        
                    if col3.button("Ban", key=f"ban_{row['email']}"):
                        st.session_state.local_users.loc[st.session_state.local_users['email'] == row['email'], 'status'] = 'Banned'
                        
                        new_log = pd.DataFrame([{
                            "user_identity": "SYSTEM_ADMIN",
                            "action_type": f"Blacklisted {row['email']}",
                            "target_asset": "User Matrix Control",
                            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        }])
                        st.session_state.local_logs = pd.concat([st.session_state.local_logs, new_log], ignore_index=True)
                        st.warning(f"Profile {row['email']} blacklisted.")
                        time.sleep(0.4)
                        st.rerun()
                        
        # TAB 2: DEPLOY NEW WORKBOOKS
        with tab2:
            st.subheader("➕ Add Master Excel Asset to Repository")
            with st.form("add_asset_form"):
                a_name = st.text_input("Excel Tool / Dashboard Name (e.g., Roster Tracker V2)")
                a_link = st.text_input("Master Spreadsheet Link (Google Sheet or Sharepoint Link)")
                a_submit = st.form_submit_button("Deploy Asset to Portal")
                
                if a_submit:
                    if not a_name or not a_link:
                        st.error("All file deployment details are mandatory.")
                    else:
                        new_id = f"ASSET-{int(time.time())}"
                        new_asset = pd.DataFrame([{
                            "asset_id": new_id,
                            "asset_name": a_name,
                            "download_link": a_link,
                            "added_by": "SYSTEM_ADMIN"
                        }])
                        st.session_state.local_assets = pd.concat([st.session_state.local_assets, new_asset], ignore_index=True)
                        
                        # Add tracking audit log
                        new_log = pd.DataFrame([{
                            "user_identity": "SYSTEM_ADMIN",
                            "action_type": f"Deployed Asset: {a_name}",
                            "target_asset": new_id,
                            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        }])
                        st.session_state.local_logs = pd.concat([st.session_state.local_logs, new_log], ignore_index=True)
                        st.success(f"Successfully deployed '{a_name}' directly into the active download deck!")
                        time.sleep(0.5)
                        st.rerun()

        # TAB 3: INFRASTRUCTURE LOGS RUNTIME VIEW
        with tab3:
            st.subheader("📋 Infrastructure Live Audit Trail Logs")
            if not st.session_state.local_logs.empty:
                st.dataframe(st.session_state.local_logs.iloc[::-1], use_container_width=True)
            else:
                st.info("Log tracking records reading empty array structures.")import streamlit as st
import pandas as pd
from datetime import datetime
import time

# --- SYSTEM SETTINGS ---
st.set_page_config(page_title="Site Operations Portal", page_icon="📊", layout="wide")

if "navigation_radio" not in st.session_state:
    st.session_state.navigation_radio = "👥 User Download Deck"

if "admin_auth" not in st.session_state:
    st.session_state.admin_auth = False

st.title("📊 Cloud Tracker Workbook Portal")

# --- HIGH-SPEED DATA CONVERSION ENGINE ---
raw_url = st.secrets["connections"]["gsheets"]["spreadsheet"]
sheet_id = raw_url.split("/d/")[1].split("/")[0]

def fetch_sheet_data(worksheet_name):
    try:
        # Pulls data cleanly as a structural frame via public read-link endpoints
        csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={worksheet_name}"
        df = pd.read_csv(csv_url)
        return df.dropna(how="all")
    except Exception:
        if worksheet_name == "user_permissions":
            return pd.DataFrame(columns=['email', 'full_name', 'status', 'requested_at'])
        else:
            return pd.DataFrame(columns=['user_identity', 'action_type', 'target_asset', 'timestamp'])

# --- STATE LIFECYCLE MEMORY CACHE ---
if "local_users" not in st.session_state:
    st.session_state.local_users = fetch_sheet_data("user_permissions")
if "local_logs" not in st.session_state:
    st.session_state.local_logs = fetch_sheet_data("portal_audit_logs")

# --- INSTANT PAGE SWITCHER CALLBACK (CRASH PROOF) ---
def handle_page_switch():
    if "navigation_radio" not in st.session_state:
        st.session_state.navigation_radio = "👥 User Download Deck"
    
    selected_mode = st.session_state.navigation_radio
    if selected_mode == "🔐 Admin Console":
        st.query_params["active_page"] = "Admin"
    else:
        st.query_params["active_page"] = "User"

page_mode = st.sidebar.radio(
    "Navigate Gateway", 
    ["👥 User Download Deck", "🔐 Admin Console"],
    key="navigation_radio",
    on_change=handle_page_switch
)

# -------------------------------------------------------------------
# ARCHITECTURE MODULE A: USER ACCESS INTERFACE
# -------------------------------------------------------------------
if page_mode == "👥 User Download Deck":
    st.header("👥 User Access Gateway")
    
    with st.form("login_form"):
        name = st.text_input("Full Name").strip()
        email = st.text_input("Corporate Email Address (@amazon.com)").lower().strip()
        submit = st.form_submit_button("Verify & Request Access")
        
        if submit:
            if not name or not email:
                st.error("All identification fields are mandatory.")
            elif not email.endswith("@amazon.com"):
                st.error("⚠️ Access Denied. Valid corporate @amazon.com email required.")
            else:
                users_df = st.session_state.local_users
                
                if not users_df.empty and email in users_df['email'].values:
                    user_status = users_df[users_df['email'] == email]['status'].values[0]
                    
                    if user_status == "Approved":
                        st.success("🔓 Access Authorized! Connection confirmed.")
                        st.markdown(f"[📊 Open Master Site Operations Workbook Link]({raw_url})")
                    elif user_status == "Pending":
                        st.warning("⏳ Access Request Pending: Your profile entry is currently awaiting admin verification.")
                    elif user_status == "Banned":
                        st.error("⛔ CRITICAL FIREWALL BLOCK: This email has been permanently blacklisted.")
                else:
                    new_user = pd.DataFrame([{
                        "email": email,
                        "full_name": name,
                        "status": "Pending",
                        "requested_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }])
                    st.session_state.local_users = pd.concat([st.session_state.local_users, new_user], ignore_index=True)
                    st.info("📨 Request submitted successfully! Your tracking record has been queued inside the dashboard.")

# -------------------------------------------------------------------
# ARCHITECTURE MODULE B: ADMINISTRATIVE CONTROL PANEL
# -------------------------------------------------------------------
else:
    st.header("🔐 Admin Operations Dashboard")
    
    if not st.session_state.admin_auth:
        with st.form("admin_login"):
            user = st.text_input("Username")
            pas = st.text_input("Password", type="password")
            if st.form_submit_button("Login"):
                if user == "admin" and pas == "password123":
                    st.session_state.admin_auth = True
                    st.rerun()
                else:
                    st.error("Invalid Administrative Credentials.")
    else:
        if st.button("Log Out Admin"):
            st.session_state.admin_auth = False
            st.rerun()
            
        st.write("---")
        
        st.subheader("🔑 Open Access Modification Requests")
        pending = st.session_state.local_users[st.session_state.local_users['status'] == 'Pending'] if not st.session_state.local_users.empty else pd.DataFrame()
        
        if pending.empty:
            st.info("No corporate profiles currently awaiting clearance operations.")
        else:
            for idx, row in pending.iterrows():
                col1, col2, col3 = st.columns([4, 2, 2])
                col1.write(f"📧 **{row['email']}** ({row['full_name']})")
                
                if col2.button("Approve", key=f"app_{row['email']}"):
                    st.session_state.local_users.loc[st.session_state.local_users['email'] == row['email'], 'status'] = 'Approved'
                    st.success("User Profile Granted System Access!")
                    time.sleep(0.4)
                    st.rerun()
                    
                if col3.button("Ban", key=f"ban_{row['email']}"):
                    st.session_state.local_users.loc[st.session_state.local_users['email'] == row['email'], 'status'] = 'Banned'
                    st.warning("User Profile Blacklisted.")
                    time.sleep(0.4)
                    st.rerun()

        st.write("---")
        st.subheader("📋 Infrastructure Live Audit Trail Logs")
        if not st.session_state.local_logs.empty:
            st.dataframe(st.session_state.local_logs.iloc[::-1], use_container_width=True)
        else:
            st.info("Log records verified active.")
