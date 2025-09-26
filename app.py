import streamlit as st
import yfinance as yf
import pandas as pd

# ---------- Page setup ----------
st.set_page_config(page_title="Stock/ETF Data Viewer", layout="wide")

# Minimal dark styling for the table only
TABLE_CSS = """
<style>
/* make tables dark-only, leave the rest of app normal */
table { background-color: #111 !important; color: #eaeaea !important; }
thead th { background-color: #1a1a1a !important; color: #eaeaea !important; }
tbody tr:nth-child(even) { background-color: #161616 !important; }
tbody tr:nth-child(odd) { background-color: #0f0f0f !important; }
td, th { border-color: #333 !important; }
</style>
"""
st.markdown(TABLE_CSS, unsafe_allow_html=True)

# ---------- Session state for steps ----------
if "step" not in st.session_state:
    st.session_state.step = 1

def go_next():
    st.session_state.step = min(2, st.session_state.step + 1)

def go_back():
    st.session_state.step = max(1, st.session_state.step - 1)

# ---------- Step 1: Inputs ----------
if st.session_state.step == 1:
    st.subheader("Step 1 — Choose Ticker & Date Range")

    from datetime import date
    MIN_DAY = date(2000, 1, 1)
    MAX_DAY = date.today()

    col1, col2 = st.columns([1, 2])
    with col1:
        ticker = st.text_input(
            "Ticker (ETF/stock)",
            value=st.session_state.get("ticker", "SPY")
        ).strip().upper()
    with col2:
        start = st.date_input(
            "Start date",
            value=pd.to_datetime(st.session_state.get("start", "2010-01-01")).date(),
            min_value=MIN_DAY,
            max_value=MAX_DAY,
        )
        end = st.date_input(
            "End date",
            value=MAX_DAY,
            min_value=MIN_DAY,
            max_value=MAX_DAY,
        )

    # persist inputs
    st.session_state.ticker = ticker
    st.session_state.start = start
    st.session_state.end = end

    st.button("Review →", on_click=go_next, type="primary")


# ---------- Step 2: Review & Fetch ----------
elif st.session_state.step == 2:
    st.subheader("Step 2 — Review & Get Data")

    with st.container(border=True):
        st.markdown(
            f"""
            **Ticker:** `{st.session_state.ticker}`  
            **Range:** `{st.session_state.start:%m/%d/%Y}` → `{st.session_state.end:%m/%d/%Y}`
            """
        )
    cols = st.columns([1, 1, 6])
    with cols[0]:
        st.button("← Back", on_click=go_back)
    with cols[1]:
        fetch = st.button("Get Data", type="primary")
    with cols[2]:
        st.write("")

    # If user clicks "Get Data", fetch and store in session
    if fetch:
        @st.cache_data(show_spinner=True)
        def load_prices(tkr: str, start_date, end_date) -> pd.DataFrame:
            df = yf.download(tkr, start=start_date, end=end_date, progress=False)
            return df

        st.session_state.df = load_prices(
            st.session_state.ticker,
            st.session_state.start,
            st.session_state.end,
        )

    # Only continue if we have data stored
    if "df" in st.session_state and not st.session_state.df.empty:
        df = st.session_state.df.copy()
        df.index = pd.to_datetime(df.index)  # ensure datetime index

        # ---------- Frequency choice ----------
        freq = st.radio(
            "Choose return frequency",
            ["Daily", "Weekly", "Monthly"],
            horizontal=True,
        )

        # ---------- Compute returns ----------
        if freq == "Daily":
            out = df[["Close"]].copy()
            out["Return (%)"] = out["Close"].pct_change() * 100

        elif freq == "Weekly":
            weekly = df["Close"].resample("W-FRI").last()
            out = pd.DataFrame(weekly)
            out.rename(columns={out.columns[0]: "Close"}, inplace=True)
            out["Return (%)"] = out["Close"].pct_change() * 100

        elif freq == "Monthly":
            monthly = df["Close"].resample("M").last()
            out = pd.DataFrame(monthly)
            out.rename(columns={out.columns[0]: "Close"}, inplace=True)
            out["Return (%)"] = out["Close"].pct_change() * 100

        out.dropna(inplace=True)

        # ---------- Display table ----------
        st.markdown("---")
        st.subheader(f"{freq} Returns — {st.session_state.ticker}")

        out_display = out.reset_index()
        out_display.rename(columns={"index": "Date"}, inplace=True)

        # Flatten MultiIndex columns into simple names
        out_display.columns = [c if isinstance(c, str) else c[0] for c in out_display.columns]

        if "Close" in out_display and "Return (%)" in out_display:
            # Format Date
            out_display["Date"] = pd.to_datetime(out_display["Date"]).dt.strftime("%m/%d/%Y")

            # Ensure numeric
            out_display["Close"] = pd.to_numeric(out_display["Close"], errors="coerce").round(2)
            out_display["Return (%)"] = pd.to_numeric(out_display["Return (%)"], errors="coerce").round(2)

            # Drop invalid rows
            out_display.dropna(subset=["Close", "Return (%)"], inplace=True)

            st.dataframe(
                out_display[["Date", "Close", "Return (%)"]],
                use_container_width=True,
                hide_index=True
            )
        else:
            st.warning("No valid Close/Return columns found in output.")

        # ---------- Summary stats ----------
        st.markdown("### 📊 Return Statistics")

        total_obs = len(out)
        win_rate = (out["Return (%)"] > 0).mean() * 100
        loss_rate = (out["Return (%)"] < 0).mean() * 100
        flat_rate = (out["Return (%)"] == 0).mean() * 100

        stats = {
            "Observations": total_obs,
            "Mean Return (%)": out["Return (%)"].mean(),
            "Min Return (%)": out["Return (%)"].min(),
            "Max Return (%)": out["Return (%)"].max(),
            "Std Dev (%)": out["Return (%)"].std(),
            "Win Rate (%)": win_rate,
            "Loss Rate (%)": loss_rate,
            "Flat Rate (%)": flat_rate,
        }

        stats_df = pd.DataFrame(stats, index=[0]).T.reset_index()
        stats_df.columns = ["Metric", "Value"]

        stats_df["Value"] = stats_df["Value"].apply(
            lambda v: f"{v:,.2f}" if isinstance(v, (int, float)) else v
        )

        st.dataframe(
            stats_df,
            use_container_width=True,
            hide_index=True
        )
