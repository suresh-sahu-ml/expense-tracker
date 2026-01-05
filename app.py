import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime, date
from openai import AzureOpenAI
from dotenv import load_dotenv
import database as db

# 1. Configuration & Setup
print("Starting app...")
load_dotenv()
print(f"Endpoint: {os.getenv('AZURE_OPENAI_ENDPOINT')}")
client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version="2024-02-01",
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
)
DEPLOYMENT_NAME = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")

st.set_page_config(page_title="Personal Tracker & Analytics", layout="wide")
db.init_db()

# --- AZURE AUTHENTICATION ---
def get_current_user():
    headers = st.context.headers
    user_email = headers.get("X-MS-CLIENT-PRINCIPAL-NAME")
    if not user_email:
        return "local_test_user@example.com"
    return user_email

USER_EMAIL = get_current_user()

# --- AI PARSING & CATEGORIES ---
FIXED_CATEGORIES = [
    "Food", "Grocery", "Utilities", "Jewellery", "Bill", 
    "Medicine", "Furniture", "Maintenance", "Transport", 
    "Shopping", "Health", "Entertainment", "Education", "Others"
]

def parse_input_with_llm(user_input):
    today_str = date.today().strftime("%Y-%m-%d")
    cat_list_str = ", ".join(FIXED_CATEGORIES)
    
    system_prompt = (
        f"Extract data into JSON. Reference date (today) is {today_str}. "
        f"Fields: activity, amount, entity, payment_mode, category, remark, extracted_date. "
        f"CRITICAL: If the user mentions a specific date, use THAT for 'extracted_date'. "
        f"Otherwise, use {today_str}. Use ONLY these categories: {cat_list_str}."
    )
    
    try:
        response = client.chat.completions.create(
            model=DEPLOYMENT_NAME,
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_input}],
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        st.error(f"AI Error: {e}"); return None

# --- UI SETUP ---
st.sidebar.title("Account")
st.sidebar.success(f"Logged in: {USER_EMAIL}")

tab1, tab2 = st.tabs(["➕ Add Entry", "📊 Dashboard"])

with tab1:
    user_input = st.text_input("What did you spend on?", placeholder="e.g., Paid 1089.20 for Medicine from Apollo on 02 Jan 2026")
    if st.button("Analyze Input"):
        if user_input:
            data = parse_input_with_llm(user_input)
            if data: st.session_state['temp_data'] = data
        else: st.warning("Please enter some text.")

    if 'temp_data' in st.session_state:
        data = st.session_state['temp_data']
        with st.form("confirm_form", clear_on_submit=True):
            # AI-extracted date handling
            try:
                default_date = pd.to_datetime(data.get('extracted_date')).date()
            except:
                default_date = date.today()

            log_date = st.date_input("Date", value=default_date)
            activity = st.text_input("Activity", data.get('activity'))
            amount = st.number_input("Amount", value=float(data.get('amount', 0)))
            entity = st.text_input("Entity", data.get('entity'))
            mode = st.text_input("Payment Mode", data.get('payment_mode'))
            
            suggested_cat = data.get('category', 'Others')
            cat_idx = FIXED_CATEGORIES.index(suggested_cat) if suggested_cat in FIXED_CATEGORIES else FIXED_CATEGORIES.index("Others")
            category = st.selectbox("Category", FIXED_CATEGORIES, index=cat_idx)
            
            remark = st.text_area("Remark", data.get('remark'))
            
            if st.form_submit_button("Save Entry"):
                db.save_entry(USER_EMAIL, log_date, activity, amount, entity, mode, category, remark)
                st.success("✅ Saved!")
                del st.session_state['temp_data']
                st.rerun()

with tab2:
    df = db.fetch_user_logs(USER_EMAIL)
    
    if not df.empty:
        df['log_date'] = pd.to_datetime(df['log_date'])
        df['MonthYear'] = df['log_date'].dt.strftime('%B %Y')
        
        # --- 1. FILTERING ---
        st.subheader("📊 Analytics & History")
        month_options = ["All Time"] + sorted(df['MonthYear'].unique().tolist(), reverse=True)
        selected_month = st.selectbox("Filter by Month", month_options)
        
        # Determine the target month for budget calculations
        if selected_month == "All Time":
            target_month_str = datetime.now().strftime('%B %Y')
            display_df = df
        else:
            target_month_str = selected_month
            display_df = df[df['MonthYear'] == selected_month]

        # --- 2. DYNAMIC BUDGET PROGRESS ---
        with st.expander("🎯 Monthly Budget Settings"):
            budget_goal = st.number_input("Monthly Limit (₹):", value=50000, step=1000)
        
        # Progress is calculated based on the selected (or current) month
        budget_df = df[df['MonthYear'] == target_month_str]
        this_period_total = budget_df['amount'].sum()
        progress = min(this_period_total / budget_goal, 1.0)
        
        st.write(f"**Spend for {target_month_str}: ₹{this_period_total:,.2f} / ₹{budget_goal:,.2f}**")
        st.progress(progress)
        if this_period_total > budget_goal: st.error(f"⚠️ Budget for {target_month_str} Exceeded!")

        # --- 3. METRICS ---
        st.divider()
        m1, m2, m3 = st.columns(3)
        m1.metric(f"Total ({selected_month})", f"₹{display_df['amount'].sum():,.2f}")
        m2.metric(f"Avg Spend ({selected_month})", f"₹{display_df['amount'].mean():,.2f}")
        m3.metric("Records", len(display_df))

        # --- 4. CHARTS & TOP 5 ---
        st.write("#### 📈 Spending Trends")
        df_trend = df.groupby(df['log_date'].dt.to_period('M').astype(str))['amount'].sum().reset_index()
        st.line_chart(df_trend.set_index('log_date'))

        # Clean display copy for UI elements
        ui_df = display_df.copy()
        ui_df['log_date'] = ui_df['log_date'].dt.date

        c1, c2 = st.columns(2)
        with c1:
            st.write("#### 📊 By Category")
            cat_plot = ui_df.groupby('category')['amount'].sum().reset_index()
            st.bar_chart(cat_plot.set_index('category'))
        with c2:
            st.write("#### 🏆 Top 5 Expenses")
            top_5 = ui_df.nlargest(5, 'amount')[['log_date', 'activity', 'entity', 'amount']]
            st.dataframe(top_5, hide_index=True, width='stretch')

        # --- 5. DETAILED TABLE & EDIT ---
        st.divider()
        st.write(f"#### 📄 Detailed Records: {selected_month}")
        st.dataframe(ui_df.drop(columns=['user_email', 'MonthYear']), width='stretch', hide_index=True)

        with st.expander("📝 Edit or Delete Records"):
            edit_id = st.selectbox("Select ID", ui_df['id'].tolist())
            curr = ui_df[ui_df['id'] == edit_id].iloc[0]
            with st.form(f"edit_{edit_id}"):
                e_date = st.date_input("Date", value=curr['log_date'])
                e_act = st.text_input("Activity", curr['activity'])
                e_amt = st.number_input("Amount", value=float(curr['amount']))
                e_cat = st.selectbox("Category", FIXED_CATEGORIES, index=FIXED_CATEGORIES.index(curr['category']) if curr['category'] in FIXED_CATEGORIES else 0)
                e_ent = st.text_input("Entity", curr['entity'])
                e_mod = st.text_input("Mode", curr['payment_mode'])
                e_rem = st.text_area("Remark", curr['remark'])
                if st.form_submit_button("Update"):
                    db.update_entry(e_date, e_act, e_amt, e_cat, e_ent, e_mod, e_rem, edit_id, USER_EMAIL)
                    st.rerun()
                if st.form_submit_button("Delete Record", type="primary"):
                    db.delete_entry(edit_id, USER_EMAIL)
                    st.rerun()
    else:
        st.info("No records found. Start adding entries in the first tab!")