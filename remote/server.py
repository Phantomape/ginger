from flask import Flask, request, jsonify
import subprocess

app = Flask(__name__)

# 👉 简单token（防止别人乱调用）
SECRET = "ying"

# 👉 可执行的脚本列表
SCRIPTS = {
    "job1": r"C:\path\to\your1.ps1",
    "job2": r"C:\path\to\your2.ps1"
}

@app.route("/run")
def run():
    token = request.args.get("token")

    if token != SECRET:
        return jsonify({"error": "unauthorized"}), 403

    try:
        subprocess.Popen([
            "powershell",
            "-ExecutionPolicy", "Bypass",
            "-Command",
            r"& 'D:\Github\ginger\.venv\Scripts\Activate.ps1'; & 'D:\Github\ginger\loop.ps1'"
        ])
        return jsonify({"status": "started", "job": "loop.ps1"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)