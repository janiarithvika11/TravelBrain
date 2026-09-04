<h1 align="center">🧠 TravelBrain</h1>

<p align="center">
  <strong>An Autonomous Multi-Agent AI Travel Planner & Itinerary Assistant</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/status-active-success.svg" alt="Status">
  <a href="https://github.com/janiarithvika11/TravelBrain/issues"><img src="https://img.shields.io/github/issues/janiarithvika11/TravelBrain.svg" alt="GitHub Issues"></a>
  <a href="https://github.com/janiarithvika11/TravelBrain/pulls"><img src="https://img.shields.io/github/issues-pr/janiarithvika11/TravelBrain.svg" alt="GitHub Pull Requests"></a>
</p>

---

<p align="center">
  Describe your dream vacation in plain English, and TravelBrain coordinates a team of specialized AI agents to research flights, hotels, live weather forecasts, and day-by-day itineraries — delivering a realistic travel plan in seconds.
</p>

## 📝 Table of Contents

- [About TravelBrain](#about)
- [Key Features](#features)
- [Multi-Agent Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Installation & Setup](#installation)
  - [Environment Variables](#environment-variables)
  - [Running the Application](#running)
- [Usage Guide](#usage)
- [Troubleshooting](#troubleshooting)
- [Author & Contributor](#author)

---

## 🧐 About TravelBrain <a name="about"></a>

Traditional trip planning involves dozens of open tabs — comparing flights, checking accommodations, verifying weather forecasts, and manually structuring daily activities. 

**TravelBrain** streamlines this process into a seamless conversational AI experience. Driven by LangGraph and Groq LLMs, TravelBrain orchestrates dedicated agent specialists that simultaneously research each aspect of your journey:

| Agent Specialist | Role & Responsibilities |
|---|---|
| ✈️ **Flight Agent** | Researches flight routes, nearby airports, airline operators, and fare ranges |
| 🏨 **Hotel Agent** | Discovers curated accommodations matching your destination, group size, and budget |
| 🌤️ **Weather Agent** | Analyzes live weather conditions and season forecasts with packing recommendations |
| 🗺️ **Itinerary Agent** | Formulates realistic, hour-by-hour and day-by-day travel schedules |
| 💰 **Budget Specialist** | Calculates an estimated financial breakdown tailored to your spending style |

Trips are automatically persisted in PostgreSQL so you can resume your plans, ask follow-up questions, or export your itinerary at any time.

---

## ✨ Key Features <a name="features"></a>

- **🔐 Built-in User Authentication**: Secure user registration, login, and session persistence using PBKDF2 password hashing and HMAC-signed HTTP-only session cookies.
- **🛡️ Isolated User Sessions**: Multi-tenant state isolation ensuring your trip histories and conversations remain strictly private.
- **🤖 Autonomous Multi-Agent Orchestration**: Modular agent graph built with **LangGraph** coordinating specialized tasks in parallel.
- **⚡ High-Speed AI Inference**: Powered by **Groq** for near-instant reasoning and itinerary generation.
- **🌐 Real-Time Live Data**: Integrations with Tavily, AviationStack, and OpenWeather for accurate, up-to-date travel data.
- **🎛️ Interactive Trip Builder**: Visual parameters modal allowing you to configure origins, destinations, dates, budgets, and travel interests.
- **📜 Chat History & Management**: Full thread history in a ChatGPT-style sidebar with instant resume and deletion capabilities.
- **📄 Export & Sharing**: Download itineraries as Markdown, print formatted travel summaries, or copy directly to your clipboard.
- **🌓 Dark / Light Mode**: Sleek modern UI with dark and light aesthetic themes.

---

## 🏗️ Multi-Agent Architecture <a name="architecture"></a>

TravelBrain utilizes a stateful multi-agent workflow directed by LangGraph:

```
[User Request]
       │
       ▼
[Destination Agent] ─── Validates travel details, locations, and traveler preferences
       │
 ┌─────┴─────────────────────────┐
 │                               │
 ▼                               ▼
[Flight Agent]            [Hotel Agent]
 (AviationStack)             (Tavily)
 │                               │
 └─────┬─────────────────────────┘
       ▼
[Weather Agent] (OpenWeather / Tavily)
       │
       ▼
[Itinerary Agent] ─── Synthesizes day-by-day schedules & activity maps
       │
       ▼
[Final Agent] ─── Collates comprehensive plan, budgets, and actionable summaries
       │
       ▼
[Client Interface / PostgreSQL Checkpointer]
```

---

## 💻 Tech Stack <a name="tech-stack"></a>

- **Backend Framework**: Python 3.11, [FastAPI](https://fastapi.tiangolo.com/), Uvicorn
- **Agent Orchestration**: [LangGraph](https://github.com/langchain-ai/langgraph), [LangChain](https://github.com/langchain-ai/langchain)
- **AI Inference Engine**: [Groq](https://console.groq.com/)
- **Database & State Storage**: PostgreSQL (with LangGraph checkpointing)
- **External APIs**:
  - [Tavily Search API](https://tavily.com/) (Hotel & destination discovery)
  - [AviationStack API](https://aviationstack.com/) (Flight & airport data)
  - [OpenWeather API](https://openweathermap.org/) (Weather & climate outlooks)
- **Frontend**: Responsive HTML5, Vanilla JavaScript, Modern CSS3 with CSS variables
- **Dependency Management**: [uv](https://docs.astral.sh/uv/)

---

## 🏁 Getting Started <a name="getting-started"></a>

### Prerequisites <a name="prerequisites"></a>

Ensure you have the following installed on your system:
- **Python 3.11+**
- **[uv](https://docs.astral.sh/uv/)** (recommended package manager) or `pip`
- **PostgreSQL Database** (local instance or hosted service like Render / Supabase)
- API Keys (all offer free tiers):
  - [Groq Console](https://console.groq.com/)
  - [Tavily](https://tavily.com/)
  - [AviationStack](https://aviationstack.com/)
  - [OpenWeather](https://openweathermap.org/api)

### Installation & Setup <a name="installation"></a>

1. **Clone the Repository**:
   ```bash
   git clone https://github.com/janiarithvika11/TravelBrain.git
   cd TravelBrain
   ```

2. **Install Dependencies**:
   Using `uv`:
   ```bash
   uv sync
   ```
   *Or with standard pip:*
   ```bash
   pip install -r requirements.txt
   ```

### Environment Variables <a name="environment-variables"></a>

Create a `.env` file in the project root by copying the example:

```bash
cp .env.example .env
```

Configure your credentials:

```dotenv
# AI & Database Configuration (Required)
GROQ_API_KEY=your_groq_api_key
DATABASE_URL=postgresql://user:password@localhost:5432/travelbrain
SECRET_KEY=your_random_secret_key_for_session_auth

# External Travel APIs
TAVILY_API_KEY=your_tavily_api_key
AVIATIONSTACK_API_KEY=your_aviationstack_api_key
OPENWEATHER_API_KEY=your_openweather_api_key

# Optional Model Configuration
GROQ_MODEL=openai/gpt-oss-20b
```

### Running the Application <a name="running"></a>

Start the FastAPI application with `uv`:

```bash
uv run python app.py
```

Or run directly with `uvicorn`:

```bash
uvicorn app:app --host 127.0.0.1 --port 8000 --reload
```

Open your browser and navigate to:
**`http://127.0.0.1:8000`**

---

## 🎈 Usage Guide <a name="usage"></a>

1. **Create an Account / Sign In**:
   - Register a new account or sign in to your existing session on the `/login` page.
2. **Describe Your Vacation**:
   - Enter a prompt in the message box, e.g.:
     > *"Plan a 7-day culinary and cultural adventure in Tokyo and Kyoto for two people in October with a moderate budget."*
3. **Trip Builder Modal**:
   - Click the sliders icon next to the chat bar to specify origin, destination, travel dates, duration, number of travelers, and activity interests.
4. **Explore Structured Results**:
   - Switch between detailed sections: **Overview Plan**, **Day-by-Day Itinerary**, **Flight Details**, **Hotels & Accommodations**, and **Weather Outlook**.
5. **Manage History**:
   - Saved conversations appear in your sidebar. Reopen any past trip to continue tailoring details or delete trips you no longer need.
6. **Export & Print**:
   - Download the plan as a `.md` markdown file or click Print for an export-ready travel guide.

---

## 🤔 Troubleshooting <a name="troubleshooting"></a>

<details>
<summary><b>API Connection shows as disconnected</b></summary>

Ensure `app.py` is actively running. Check your terminal output to verify Uvicorn is bound to port `8000`.
</details>

<details>
<summary><b>DATABASE_URL Error on startup</b></summary>

Ensure your PostgreSQL instance is running and the connection string in `.env` is formatted properly: `postgresql://user:password@host:port/dbname`.
</details>

<details>
<summary><b>Groq Model Deprecated or Unavailable</b></summary>

Update the `GROQ_MODEL` variable in your `.env` to any active model supported by Groq (e.g., `llama-3.3-70b-versatile` or `mixtral-8x7b-32768`).
</details>

---

## 👤 Author & Contributor <a name="author"></a>

This project is authored, maintained, and contributed to by:

- **janiarithvika11** — [@janiarithvika11](https://github.com/janiarithvika11) · [janiarithvikasimma@gmail.com](mailto:janiarithvikasimma@gmail.com)
