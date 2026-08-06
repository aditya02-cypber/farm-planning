# ============ STEP 1: LOAD MODULES ============
import os
import json
import streamlit as st

from langchain.agents import create_agent
from langchain_core.tools import tool
from langchain_core.messages import AIMessage, HumanMessage

# =============STEP 2: API KEYS=====================
st.set_page_config(
    page_title="Farm Planning & Profit Estimator",
    page_icon="🌾",
    layout="wide"
)

st.sidebar.title("SET API CONFIG")
st.title("🌾 Farm Planning & Profit Estimator (AGR-02)")
st.caption("Agent + Calculator Tool · Season/Location Crop Recommendation · Profit Estimation")

GOOGLE_API_KEY = st.sidebar.text_input(
    "GOOGLE_API_KEY",
    type="password")
os.environ["GOOGLE_API_KEY"] = GOOGLE_API_KEY

# ==================== STEP 3: STATIC KNOWLEDGE BASE ====================
# Simple season/location -> crop suitability table.
# In a fuller build this would come from an agri-database or weather API.
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
# Used by the calculator tool for profit estimation.
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

# ==================== STEP 4: CUSTOM TOOLS ====================
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
    yield_per_acre_override: optional, override default yield (quintal/acre) if user gives their own estimate.
    price_per_quintal_override: optional, override default market price (Rs/quintal) if user gives their own estimate."""
    crop_key = crop.strip().lower()
    econ = CROP_ECONOMICS.get(crop_key)
    if not econ and (not yield_per_acre_override or not price_per_quintal_override):
        return (f"No default economic data for '{crop}'. Please supply yield_per_acre_override and "
                f"price_per_quintal_override so I can calculate profit.")

    yield_per_acre = yield_per_acre_override or econ["yield_per_acre"]
    price_per_quintal = price_per_quintal_override or econ["price_per_quintal"]

    total_yield = yield_per_acre * land_acres
    gross_revenue = total_yield * price_per_quintal
    net_profit = gross_revenue - total_cost_rs
    roi_pct = (net_profit / total_cost_rs * 100) if total_cost_rs > 0 else 0

    result = {
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
    return json.dumps(result, indent=2)


TOOLS = [crop_recommendation_tool, profit_calculator_tool]

# ==================== STEP 5: BUILD THE AGENT ====================
SYSTEM_PROMPT = """You are an agricultural planning assistant for Indian farmers.
You help with two things:
1. Recommending suitable crops for a season (kharif/rabi/zaid) and region (north/south/east/west) using the crop_recommendation_tool.
2. Estimating farming profit using the profit_calculator_tool, which needs crop name, land in acres, and total estimated cost in rupees.

Always use the tools for factual/numeric answers instead of guessing. If the user hasn't given enough
details (season, region, land size, or cost) ask a short clarifying question before calling a tool.
Explain the result in simple, farmer-friendly language after the tool responds, and mention this is an
estimate based on average figures, not a guarantee."""

@st.cache_resource
def build_agent(_api_key):
    return create_agent(
        model="google_genai:gemini-2.5-flash",
        tools=TOOLS,
        system_prompt=SYSTEM_PROMPT,
    )

# ==================== STEP 6: SIDEBAR QUICK-CALC (DIRECT TOOL ACCESS) ====================
st.sidebar.markdown("---")
st.sidebar.subheader("Quick Profit Calculator")
qc_crop = st.sidebar.text_input("Crop", value="wheat")
qc_land = st.sidebar.number_input("Land (acres)", min_value=0.1, value=2.0, step=0.5)
qc_cost = st.sidebar.number_input("Total Cost (₹)", min_value=0.0, value=25000.0, step=1000.0)
if st.sidebar.button("Calculate"):
    st.sidebar.code(profit_calculator_tool.invoke({
        "crop": qc_crop, "land_acres": qc_land, "total_cost_rs": qc_cost
    }))

# ==================== STEP 7: CHAT INTERFACE ====================
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

for msg in st.session_state.chat_history:
    role = "user" if isinstance(msg, HumanMessage) else "assistant"
    with st.chat_message(role):
        st.write(msg.content)

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
                answer = response["messages"][-1].content
                st.write(answer)

        st.session_state.chat_history.append(HumanMessage(content=user_question))
        st.session_state.chat_history.append(AIMessage(content=answer))
