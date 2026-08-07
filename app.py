# ============ STEP 1: LOAD MODULES ============
import os
import json
import pandas as pd
import streamlit as st

from langgraph.prebuilt import create_react_agent
from langchain_core.tools import tool
from langchain_core.messages import AIMessage, HumanMessage

# =============STEP 2: PAGE CONFIG & BACKGROUND=====================
st.set_page_config(
    page_title="Farm Planning & Profit Estimator",
    page_icon="🌾",
    layout="wide"
)

st.sidebar.title("SET API CONFIG")

# --- Background: sunrise over crop rows (free, Unsplash License, no attribution required) ---
BACKGROUND_IMAGE_URL = "https://images.unsplash.com/photo-1663263687797-c0d079b662b7?fm=jpg&q=80&w=2400&auto=format&fit=crop"

st.markdown(
    f"""
    <style>
    [data-testid="stAppViewContainer"] {{
        background-image: linear-gradient(rgba(10, 20, 10, 0.55), rgba(10, 20, 10, 0.65)),
                           url("{BACKGROUND_IMAGE_URL}");
        background-size: cover;
        background-position: center;
        background-attachment: fixed;
    }}
    [data-testid="stHeader"] {{ background: rgba(0, 0, 0, 0); }}
    [data-testid="stSidebar"] {{
        background-color: rgba(20, 30, 20, 0.75);
        backdrop-filter: blur(4px);
    }}
    .stApp, .stApp p, .stApp label, .stApp span {{ color: #f2f2ea; }}
    [data-testid="stChatMessage"] {{
        background-color: rgba(255, 255, 255, 0.9);
        border-radius: 12px;
    }}
    [data-testid="stChatMessage"] * {{ color: #1a1a1a !important; }}
    [data-testid="stChatMessage"] a {{ color: #0b5c1f !important; text-decoration: underline; }}
    [data-testid="stChatMessage"] code {{
        background-color: rgba(0, 0, 0, 0.06);
        color: #1a1a1a !important;
        padding: 1px 4px;
        border-radius: 4px;
    }}
    [data-testid="stMetric"] {{
        background-color: rgba(0, 0, 0, 0.35);
        border: 1px solid rgba(255, 255, 255, 0.25);
        border-radius: 12px;
        padding: 12px;
    }}
    [data-testid="stMetric"] label,
    [data-testid="stMetric"] div,
    [data-testid="stMetricLabel"] *,
    [data-testid="stMetricValue"] *,
    [data-testid="stMetricDelta"] * {{
        color: #f2f2ea !important;
    }}
    [data-testid="stTabs"] button p {{ color: #f2f2ea; font-weight: 600; }}
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("🌾 Farm Planning & Profit Estimator (AGR-02)")
st.caption("Agent + Calculator Tool · Season/Location Crop Recommendation · Profit Estimation")

GOOGLE_API_KEY = st.sidebar.text_input("GOOGLE_API_KEY", type="password")
os.environ["GOOGLE_API_KEY"] = GOOGLE_API_KEY

# ==================== STEP 3: STATIC KNOWLEDGE BASE ====================
# Simple season/location -> crop suitability table.
CROP_DATA = {
    "kharif": {
        "north":  ["Rice", "Maize", "Cotton", "Soybean"],
        "south":  ["Rice", "Groundnut", "Sugarcane", "Millet"],
        "east":   ["Rice", "Jute", "Maize"],
        "west":   ["Cotton", "Groundnut", "Bajra"],
    },
    "rabi": {
        "north":  ["Wheat", "Mustard", "Barley", "Gram"],
        "south":  ["Sorghum (Jowar)", "Sunflower", "Gram"],
        "east":   ["Wheat", "Lentil", "Mustard"],
        "west":   ["Wheat", "Gram", "Mustard"],
    },
    "zaid": {
        "north":  ["Watermelon", "Cucumber", "Moong Dal"],
        "south":  ["Vegetables", "Fodder Crops"],
        "east":   ["Vegetables", "Moong Dal"],
        "west":   ["Watermelon", "Fodder Crops"],
    },
}

# Rough average market price (Rs/quintal) and yield (quintal/acre) reference table.
CROP_ECONOMICS = {
    "rice":        {"yield_per_acre": 22, "price_per_quintal": 2100},
    "maize":       {"yield_per_acre": 25, "price_per_quintal": 1900},
    "cotton":      {"yield_per_acre": 8,  "price_per_quintal": 6800},
    "soybean":     {"yield_per_acre": 10, "price_per_quintal": 4500},
    "groundnut":   {"yield_per_acre": 12, "price_per_quintal": 5500},
    "sugarcane":   {"yield_per_acre": 350,"price_per_quintal": 340},
    "millet":      {"yield_per_acre": 9,  "price_per_quintal": 2300},
    "jute":        {"yield_per_acre": 10, "price_per_quintal": 4800},
    "bajra":       {"yield_per_acre": 11, "price_per_quintal": 2100},
    "wheat":       {"yield_per_acre": 20, "price_per_quintal": 2275},
    "mustard":     {"yield_per_acre": 8,  "price_per_quintal": 5400},
    "barley":      {"yield_per_acre": 16, "price_per_quintal": 1850},
    "gram":        {"yield_per_acre": 9,  "price_per_quintal": 5335},
    "sorghum (jowar)": {"yield_per_acre": 10, "price_per_quintal": 3180},
    "sunflower":   {"yield_per_acre": 7,  "price_per_quintal": 6400},
    "lentil":      {"yield_per_acre": 7,  "price_per_quintal": 6425},
    "watermelon":  {"yield_per_acre": 90, "price_per_quintal": 800},
    "cucumber":    {"yield_per_acre": 60, "price_per_quintal": 900},
    "moong dal":   {"yield_per_acre": 6,  "price_per_quintal": 8500},
    "vegetables":  {"yield_per_acre": 70, "price_per_quintal": 1200},
    "fodder crops":{"yield_per_acre": 120,"price_per_quintal": 400},
}

# ==================== STEP 4: CORE LOGIC (plain functions, reused by tools + UI) ====================
def estimate_profit(crop: str, land_acres: float, total_cost_rs: float,
                     yield_per_acre_override: float = 0, price_per_quintal_override: float = 0) -> dict:
    """Core profit-estimation logic. Raises ValueError if crop is unknown and no overrides given."""
    crop_key = crop.strip().lower()
    econ = CROP_ECONOMICS.get(crop_key)
    if not econ and (not yield_per_acre_override or not price_per_quintal_override):
        raise ValueError(
            f"No default economic data for '{crop}'. Supply yield_per_acre_override and "
            f"price_per_quintal_override, or pick a known crop."
        )

    yield_per_acre = yield_per_acre_override or econ["yield_per_acre"]
    price_per_quintal = price_per_quintal_override or econ["price_per_quintal"]

    total_yield = yield_per_acre * land_acres
    gross_revenue = total_yield * price_per_quintal
    net_profit = gross_revenue - total_cost_rs
    roi_pct = (net_profit / total_cost_rs * 100) if total_cost_rs > 0 else 0

    return {
        "crop": crop,
        "land_acres": land_acres,
        "assumed_yield_per_acre_quintal": yield_per_acre,
        "assumed_price_per_quintal_rs": price_per_quintal,
        "total_expected_yield_quintal": round(total_yield, 2),
        "gross_revenue_rs": round(gross_revenue, 2),
        "total_cost_rs": total_cost_rs,
        "net_profit_rs": round(net_profit, 2),
        "roi_percent": round(roi_pct, 2),
    }


# ==================== STEP 5: LANGCHAIN TOOLS ====================
@tool
def crop_recommendation_tool(season: str, region: str) -> str:
    """Recommend suitable crops for a given cropping season and region.
    season must be one of: kharif, rabi, zaid.
    region must be one of: north, south, east, west."""
    season = season.strip().lower()
    region = region.strip().lower()
    crops = CROP_DATA.get(season, {}).get(region)
    if not crops:
        return f"No data found for season='{season}', region='{region}'. Valid seasons: kharif, rabi, zaid. Valid regions: north, south, east, west."
    return f"Recommended crops for {season} season in the {region} region: {', '.join(crops)}."


@tool
def profit_calculator_tool(crop: str, land_acres: float, total_cost_rs: float,
                            yield_per_acre_override: float = 0,
                            price_per_quintal_override: float = 0) -> str:
    """Estimate profit for growing a crop.
    crop: crop name (e.g. 'wheat', 'rice', 'cotton').
    land_acres: land area in acres.
    total_cost_rs: total estimated farming cost in rupees (seeds, labour, fertilizer, irrigation etc).
    yield_per_acre_override: optional, override default yield (quintal/acre).
    price_per_quintal_override: optional, override default market price (Rs/quintal)."""
    try:
        result = estimate_profit(crop, land_acres, total_cost_rs,
                                  yield_per_acre_override, price_per_quintal_override)
    except ValueError as e:
        return str(e)
    return json.dumps(result, indent=2)


TOOLS = [crop_recommendation_tool, profit_calculator_tool]


def extract_text(content) -> str:
    """Gemini 3.x can return message.content as a plain string OR a list of
    content blocks like {"type": "text", "text": "...", "extras": {...}}.
    Normalize either shape down to plain text for display."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
            elif isinstance(block, str):
                parts.append(block)
        return "\n".join(p for p in parts if p)
    return str(content)

# ==================== STEP 6: BUILD THE AGENT ====================
SYSTEM_PROMPT = """You are an agricultural planning assistant for Indian farmers.
You help with two things:
1. Recommending suitable crops for a season (kharif/rabi/zaid) and region (north/south/east/west) using crop_recommendation_tool.
2. Estimating farming profit using profit_calculator_tool (needs crop name, land in acres, total estimated cost in rupees).

Always use the tools for factual/numeric answers instead of guessing. If the user hasn't given enough
details ask a short clarifying question before calling a tool. Explain results in simple, farmer-friendly
language, and mention profit figures are estimates based on average data, not a guarantee."""

@st.cache_resource
def build_agent(_api_key):
    return create_react_agent(
        model="google_genai:gemini-3.6-flash",
        tools=TOOLS,
        prompt=SYSTEM_PROMPT,
    )

# ==================== STEP 7: TABBED LAYOUT ====================
tab_chat, tab_calc = st.tabs(["💬 Chat Advisor", "🧮 Profit Calculator"])

# ---------- TAB 1: CHAT ADVISOR ----------
with tab_chat:
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    for msg in st.session_state.chat_history:
        role = "user" if isinstance(msg, HumanMessage) else "assistant"
        with st.chat_message(role):
            st.write(extract_text(msg.content))

    user_question = st.chat_input(
        "e.g. What should I grow in kharif season in the north, and what's the profit on 3 acres of rice with ₹40000 cost?"
    )

    if user_question:
        if not GOOGLE_API_KEY:
            st.warning("Please add your GOOGLE_API_KEY in the sidebar first.")
        else:
            with st.chat_message("user"):
                st.write(user_question)

            agent = build_agent(GOOGLE_API_KEY)

            with st.chat_message("assistant"):
                with st.spinner("Thinking..."):
                    history_msgs = st.session_state.chat_history + [HumanMessage(content=user_question)]
                    response = agent.invoke({"messages": history_msgs})
                    answer = extract_text(response["messages"][-1].content)
                    st.write(answer)

            st.session_state.chat_history.append(HumanMessage(content=user_question))
            st.session_state.chat_history.append(AIMessage(content=answer))

# ---------- TAB 2: PROFIT CALCULATOR (metrics + sensitivity chart + CSV export) ----------
with tab_calc:
    st.subheader("Profit Estimator")
    c1, c2, c3 = st.columns(3)
    with c1:
        calc_crop = st.text_input("Crop", value="wheat", key="calc_crop")
    with c2:
        calc_land = st.number_input("Land (acres)", min_value=0.1, value=2.0, step=0.5, key="calc_land")
    with c3:
        calc_cost = st.number_input("Total Cost (₹)", min_value=0.0, value=25000.0, step=1000.0, key="calc_cost")

    if st.button("Calculate Profit", type="primary"):
        try:
            result = estimate_profit(calc_crop, calc_land, calc_cost)
            st.session_state["last_estimate"] = result
        except ValueError as e:
            st.error(str(e))

    if "last_estimate" in st.session_state:
        result = st.session_state["last_estimate"]

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Expected Yield", f"{result['total_expected_yield_quintal']} qtl")
        m2.metric("Gross Revenue", f"₹{result['gross_revenue_rs']:,.0f}")
        m3.metric("Net Profit", f"₹{result['net_profit_rs']:,.0f}")
        m4.metric("ROI", f"{result['roi_percent']:.1f}%")

        st.markdown("##### Profit Sensitivity to Market Price (±20%)")
        price = result["assumed_price_per_quintal_rs"]
        rows = []
        for pct in range(-20, 21, 5):
            adj_price = price * (1 + pct / 100)
            adj = estimate_profit(
                result["crop"], result["land_acres"], result["total_cost_rs"],
                price_per_quintal_override=adj_price,
            )
            rows.append({"price_change_%": pct, "net_profit_rs": adj["net_profit_rs"]})
        sens_df = pd.DataFrame(rows).set_index("price_change_%")
        st.line_chart(sens_df)

        st.markdown("##### Download Report")
        report_df = pd.DataFrame([result])
        csv_bytes = report_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "Download Estimate as CSV",
            data=csv_bytes,
            file_name=f"{result['crop']}_profit_estimate.csv",
            mime="text/csv",
        )
    else:
        st.info("Enter your crop, land size, and cost above, then click Calculate Profit.")
