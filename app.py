import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
from datetime import datetime
import time

# --- STAGE 1: SYSTEM & THEME INITIALIZATION ---
st.set_page_config(page_title="Site Operations Portal", page_icon="📊", layout="wide")

# --- INITIALIZE CORE SESSION STATES BEFORE ANY ROUTING RUNS ---
if "navigation_radio" not in st.session_state:
    st.session_state.navigation_radio = "👥 User Download Deck"

if "admin_auth" not in st.session_state:
    st.session_state.admin_auth = False

st.title("📊 Cloud Tracker Workbook Portal")

# --- STAGE 2: INITIALIZE GOOGLE CLOUD CONNECTION ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error("Configuration framework missing. Please verify your Streamlit Advanced Settings -> Secrets panel.")
    st.stop()

# --- DATABASE READ/WRITE ENGINE FUNCTIONS ---
def fetch_sheet_data(worksheet_name):
    try:
        # Reads direct rows from the target tab with zero-delay live cache overrides
        df = conn.read(worksheet=worksheet_name, ttl="0d")
        return df.dropna(how="all")
    except Exception:
        # Emergency schema structural fallback if the spreadsheet tab is completely empty
        if worksheet_name == "user_permissions":
            return pd.DataFrame(columns=['email', 'full_name', 'status', 'requested_at'])
        else:
            return pd.DataFrame(columns=['user_identity', 'action_type', 'target_asset', 'timestamp'])

def commit_rows_to_sheet(df, worksheet_name):
    # Overwrites the target worksheet tab with the updated data framework securely
    conn.update(worksheet=worksheet_name, data=df)

# --- INSTANT PAGE SWITCHER CALLBACK (CRASH PROOF) ---
def handle_page_switch():
    if "navigation_radio" not in st.session_state:
        st.session_state.navigation_radio = "👥 User Download Deck"
        
    selected_mode = st.session_state.navigation_radio
    if selected_mode == "🔐 Admin Console":
        st.query_params["active_page"] = "Admin"
    else:
        st.query_params["active_page"] = "User"

# --- SIDEBAR INTERFACE STRUCTURE ---
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
    st.write("Enter your structural details below to pull your site's master operational workbook files.")
    
    with st.form("login_form"):
        name = st.text_input("Full Name").strip()
        email = st.text_input("Corporate Email Address (@amazon.com)").lower().strip()
        submit = st.form_submit_button("Verify & Request Access")
        
        if submit:
            if not name or not email:
                st.error("All identification fields are mandatory.")
            elif not email.endswith("@amazon.com"):
                st.error("⚠️ Access Denied. Valid corporate @amazon.com email configuration required.")
            else:
                # Pull current live matrix from 'db' Google Sheet
                users_df = fetch_sheet_data("user_permissions")
                
                # Check for existing system match record
                if not users_df.empty and email in users_df['email'].values:
                    user_status = users_df[users_df['email'] == email]['status'].values[0]
                    
                    if user_status == "Approved":
                        st.success(f"🔓 Access Authorized! Click the deployment connection portal link below:")
                        # Paste your direct download link or final target spreadsheet dashboard link below
                        st.markdown("[📊 Open Master Site Operations Workbook Link](https://docs.google.com)")
                        
                        # Capture access download execution log
                        logs_df = fetch_sheet_data("portal_audit_logs")
                        new_log = pd.DataFrame([{
                            "user_identity": f"{name} ({email})",
                            "action_type": "Downloaded Workbook",
                            "target_asset": "Master Operations File",
                            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        }])
                        logs_df = pd.concat([logs_df, new_log], ignore_index=True)
                        commit_rows_to_sheet(logs_df, "portal_audit_logs")
                        
                    elif user_status == "Pending":
                        st.warning("⏳ Access Request Pending: Your profile entry is currently awaiting admin verification.")
                    elif user_status == "Banned":
                        st.error("⛔ CRITICAL FIREWALL BLOCK: This corporate email has been permanently blacklisted.")
                else:
                    # Append new pending user metrics profile to the sheet rows
                    new_user = pd.DataFrame([{
                        "email": email,
                        "full_name": name,
                        "status": "Pending",
                        "requested_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }])
                    users_df = pd.concat([users_df, new_user], ignore_index=True)
                    commit_rows_to_sheet(users_df, "user_permissions")
                    
                    # Capture creation trail into audit sheet logs tab
                    logs_df = fetch_sheet_data("portal_audit_logs")
                    new_log = pd.DataFrame([{
                        "user_identity": f"{name} ({email})",
                        "action_type": "Requested Access Entry",
                        "target_asset": "Gateway Portal System",
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }])
                    logs_df = pd.concat([logs_df, new_log], ignore_index=True)
                    commit_rows_to_sheet(logs_df, "portal_audit_logs")
                    
                    st.info("📨 Request submitted successfully! Please alert your local operations manager for clearance.")

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
        
        # Load active permission matrix sheets
        users_df = fetch_sheet_data("user_permissions")
        
        st.subheader("🔑 Open Access Modification Requests")
        pending = users_df[users_df['status'] == 'Pending'] if not users_df.empty else pd.DataFrame()
        
        if pending.empty:
            st.info("No corporate profiles currently awaiting clearance operations.")
        else:
            for idx, row in pending.iterrows():
                col1, col2, col3 = st.columns([4, 2, 2])
                col1.write(f"📧 **{row['email']}** ({row['full_name']})")
                
                if col2.button("Approve", key=f"app_{row['email']}"):
                    users_df.loc[users_df['email'] == row['email'], 'status'] = 'Approved'
                    commit_rows_to_sheet(users_df, "user_permissions")
                    
                    # Log approval execution sequence
                    logs_df = fetch_sheet_data("portal_audit_logs")
                    new_log = pd.DataFrame([{
                        "user_identity": "SYSTEM_ADMIN",
                        "action_type": f"Approved Access for {row['email']}",
                        "target_asset": "Permissions Matrix Table",
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }])
                    logs_df = pd.concat([logs_df, new_log], ignore_index=True)
                    commit_rows_to_sheet(logs_df, "portal_audit_logs")
                    
                    st.success("User Profile Granted System Access!")
                    time.sleep(0.4)
                    st.rerun()
                    
                if col3.button("Ban", key=f"ban_{row['email']}"):
                    users_df.loc[users_df['email'] == row['email'], 'status'] = 'Banned'
                    commit_rows_to_sheet(users_df, "user_permissions")
                    
                    # Log ban blacklisting execution sequence
                    logs_df = fetch_sheet_data("portal_audit_logs")
                    new_log = pd.DataFrame([{
                        "user_identity": "SYSTEM_ADMIN",
                        "action_type": f"Permanently Banned {row['email']}",
                        "target_asset": "Blacklist System Module",
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }])
                    logs_df = pd.concat([logs_df, new_log], ignore_index=True)
                    commit_rows_to_sheet(logs_df, "portal_audit_logs")
                    
                    st.warning("User Profile Blacklisted.")
                    time.sleep(0.4)
                    st.rerun()

        st.write("---")
        st.subheader("📋 Infrastructure Live Audit Trail Logs")
        
        # Pull latest metrics log rows and reverse order so freshest events sit right at the top layout
        logs_df = fetch_sheet_data("portal_audit_logs")
        if not logs_df.empty:
            st.dataframe(logs_df.iloc[::-1], use_container_width=True)
        else:
            st.info("Log database arrays currently reading blank data fields.")
