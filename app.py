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

# --- AI LOGIC ---
def parse_input_with_llm(user_input):
    today_str = date.today().strftime("%Y-%m-%d")
    system_prompt = f"""
    Extract data into JSON. Today is {today_str}.
    Fields: activity, amount, entity, payment_mode, category, remark, extracted_date (YYYY-MM-DD or null).
    Return ONLY JSON.
    """
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
st.title("🗒️ Personal Tracker & Analytics")
tab1, tab2 = st.tabs(["➕ Add Entry", "📊 Dashboard & History"])

with tab1:
    st.subheader("Quick Log")
    user_input = st.text_input("Enter details", placeholder="Swiggy dinner for 500 via UPI", key="main_input")
    
    if st.button("Analyze Input"):
        if user_input:
            with st.spinner("Processing..."):
                data = parse_input_with_llm(user_input)
                if data: st.session_state['temp_data'] = data

    if 'temp_data' in st.session_state:
        data = st.session_state['temp_data']
        ai_date_str = data.get('extracted_date')
        initial_date = datetime.strptime(ai_date_str, "%Y-%m-%d").date() if ai_date_str else date.today()

        with st.form("confirm_form", clear_on_submit=True):
            log_date = st.date_input("Date", value=initial_date)
            c1, c2 = st.columns(2)
            with c1:
                activity = st.text_input("Activity", data.get('activity'))
                amount = st.number_input("Amount", value=float(data.get('amount', 0)))
                entity = st.text_input("Entity", data.get('entity'))
            with c2:
                mode = st.text_input("Mode of Payment", data.get('payment_mode'))
                category = st.text_input("Category", data.get('category'))
                remark = st.text_area("Remark", data.get('remark'))
            
            if st.form_submit_button("Save Entry"):
                db.save_entry(str(log_date), activity, amount, entity, mode, category, remark)
                st.success("✅ Saved!"); del st.session_state['temp_data']; st.rerun()

with tab2:
    df = db.fetch_all_logs()
    if not df.empty:
        # Pre-process Analytics
        df['log_date'] = pd.to_datetime(df['log_date'])
        df['Month'] = df['log_date'].dt.strftime('%b %Y')
        
        # --- FILTERS & METRICS ---
        st.subheader("📅 Monthly Analytics")
        available_months = sorted(df['Month'].unique(), 
                                 key=lambda x: datetime.strptime(x, '%b %Y'), 
                                 reverse=True)
        selected_month = st.selectbox("Filter by Month", ["All Time"] + available_months)
        
        filtered_df = df if selected_month == "All Time" else df[df['Month'] == selected_month]
        
        # Clean Date Formatting for Display (Removes 00:00:00)
        display_df = filtered_df.copy()
        display_df['log_date'] = display_df['log_date'].dt.date
        
        m1, m2, m3 = st.columns(3)
        m1.metric("Total Expense", f"₹{filtered_df['amount'].sum():,.2f}")
        m2.metric("Average Spending", f"₹{filtered_df['amount'].mean():,.2f}")
        m3.metric("Logs Count", len(filtered_df))

        # --- CHARTS & TOP 5 ---
        st.divider()
        col_c1, col_c2 = st.columns(2)
        with col_c1:
            st.write("#### Category Breakdown")
            cat_data = filtered_df.groupby('category')['amount'].sum().reset_index()
            st.bar_chart(data=cat_data, x='category', y='amount', color='#ff4b4b')
            
        with col_c2:
            st.write("#### Top 5 Most Expensive Items")
            # Cleaning date and using dataframe for better ID rendering
            top_5 = display_df.nlargest(5, 'amount')[['activity', 'entity', 'amount', 'log_date']]
            st.dataframe(top_5, width='stretch', hide_index=True)

        st.divider()
        st.write("#### Spending Trend (Monthly)")
        trend_df = df.groupby('Month')['amount'].sum().reset_index()
        trend_df['Sort_Key'] = trend_df['Month'].apply(lambda x: datetime.strptime(x, '%b %Y'))
        trend_df = trend_df.sort_values('Sort_Key')
        st.bar_chart(data=trend_df, x='Month', y='amount', color='#29b5e8')

        # --- RECORDS & MANAGEMENT ---
        st.divider()
        st.subheader("📂 Manage Records")
        # hide_index=True fixes the issue with ID 11 wrapping to two lines
        st.dataframe(display_df.sort_values('log_date', ascending=False).drop(columns=['Month']), 
                     use_container_width=True, hide_index=True)
        
        with st.expander("Edit or Delete Entry"):
            edit_id = st.selectbox("Select ID to Modify", filtered_df['id'].tolist())
            row = filtered_df[filtered_df['id'] == edit_id].iloc[0]
            
            ce1, ce2 = st.columns(2)
            with ce1:
                u_act = st.text_input("Update Activity", row['activity'])
                u_amt = st.number_input("Update Amount", value=float(row['amount']))
                u_cat = st.text_input("Update Category", row['category'])
            with ce2:
                u_ent = st.text_input("Update Entity", row['entity'])
                u_mod = st.text_input("Update Payment Mode", row['payment_mode'])
                u_rem = st.text_input("Update Remark", row['remark'])
            
            b1, b2 = st.columns(2)
            if b1.button("Apply Changes", type="primary"):
                db.update_entry(u_act, u_amt, u_cat, u_ent, u_mod, u_rem, edit_id)
                st.rerun()
            if b2.button("🗑️ Delete Record"):
                db.delete_entry(edit_id)
                st.rerun()
    else:
        st.info("No logs found. Add an entry to get started!")