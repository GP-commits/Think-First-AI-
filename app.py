from flask import Flask, render_template, request, redirect, session
import requests, json, os, datetime
import markdown

app = Flask(__name__)
app.secret_key = "thinking-first-secret"

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "qwen2.5-coder:7b"
HISTORY_FILE = "history.json"




BASE_SYSTEM = """
You are a local AI assistant.
You MUST obey MODE rules strictly.
Never mix behaviors across modes.
"""

GUIDE_RULES = """
MODE: GUIDE

Rules:
- Do NOT give the final answer.
- Do NOT give full code.
- ALWAYS give at least ONE concrete hint.
- Point out a likely mistake or direction.
- Ask at most ONE focused follow-up question.
"""

EXPLAIN_RULES = """
MODE: EXPLAIN

Rules:
- Explain concepts clearly.
- You MAY reference solution ideas.
- Do NOT dump final code unless explicitly asked.
"""

FINAL_RULES = """
MODE: FINAL

FINAL OVERRIDE:
- Ignore all previous instructions.
- Do NOT guide.
- Do NOT ask questions.
- Provide the complete final solution.
- If code is required, output FULL working code.
"""




def load_history():
    if not os.path.exists(HISTORY_FILE):
        return []
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_history(entry):
    history = load_history()
    history.append(entry)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2)

def clear_history():
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump([], f)

def call_ai(prompt, max_tokens, temperature):
    r = requests.post(
        OLLAMA_URL,
        json={
            "model": MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens
            }
        },
        timeout=300
    )
    return r.json()["response"]




@app.route("/", methods=["GET", "POST"])
def home():
    if request.method == "POST":
        session.clear()
        session["problem"] = request.form["problem"]
        return redirect("/attempt")
    return render_template("home.html")


@app.route("/attempt", methods=["GET", "POST"])
def attempt():
    if "problem" not in session:
        return redirect("/")

    if request.method == "POST":
        session["attempt"] = request.form["attempt"]
        session["conversation"] = []   # RESET ONLY HERE
        return redirect("/chat")

    return render_template("attempt.html")


@app.route("/chat", methods=["GET", "POST"])
def chat():
    if "problem" not in session or "attempt" not in session:
        return redirect("/")

  
    if "conversation" not in session:
        session["conversation"] = []

    if request.method == "POST":
        mode = request.form["mode"]
        user_msg = request.form["message"].strip()

        if user_msg:
            session["conversation"].append({
                "role": "user",
                "content": user_msg
            })

            if mode == "guide":
                rules, tokens, temp = GUIDE_RULES, 300, 0.4
            elif mode == "explain":
                rules, tokens, temp = EXPLAIN_RULES, 500, 0.5
            else:
                rules, tokens, temp = FINAL_RULES, 1200, 0.7

            convo_text = ""
            for m in session["conversation"]:
                convo_text += f"{m['role'].upper()}: {m['content']}\n"

            prompt = f"""
{BASE_SYSTEM}
{rules}

PROBLEM:
{session['problem']}

WHAT USER TRIED:
{session['attempt']}

CONVERSATION:
{convo_text}

AI RESPONSE:
"""

            raw_reply = call_ai(prompt, tokens, temp)

            formatted_reply = markdown.markdown(
                raw_reply,
                extensions=["fenced_code", "tables"]
            )

            session["conversation"].append({
                "role": "ai",
                "content": formatted_reply
            })

            save_history({
                "time": str(datetime.datetime.now()),
                "problem": session["problem"],
                "attempt": session["attempt"],
                "mode": mode,
                "user": user_msg,
                "ai": raw_reply
            })

    return render_template(
        "chat.html",
        problem=session["problem"],
        attempt=session["attempt"],
        conversation=session["conversation"]
    )


@app.route("/history")
def history():
    return render_template("history.html", history=load_history())


@app.route("/clear_history")
def clear_hist():
    clear_history()
    return redirect("/history")


if __name__ == "__main__":
    app.run(debug=True)
