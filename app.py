import streamlit as st
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
