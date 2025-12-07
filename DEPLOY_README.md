# How to Deploy to Render (Free Cloud)

1.  **Push to GitHub**
    *   Create a new repository on GitHub.
    *   Run these commands in your terminal:
        ```bash
        git init
        git add .
        git commit -m "Initial deploy"
        git branch -M main
        git remote add origin https://github.com/pratikuse29-star/mob_violation_detection_system.git
        git push -u origin main
        ```

2.  **Deploy on Render**
    *   Go to [dashboard.render.com](https://dashboard.render.com/).
    *   Click **New +** -> **Web Service**.
    *   Connect your GitHub repository.
    *   **Settings**:
        *   **Name**: `mob-violation-app` (or similar)
        *   **Runtime**: `Python 3`
        *   **Build Command**: `pip install -r requirements.txt`
        *   **Start Command**: `gunicorn app:app`
    *   Click **Create Web Service**.

3.  **Wait & Done!**
    *   It will take about 5 minutes to build.
    *   Once done, you will get a URL like `https://mob-violation-app.onrender.com`.
    *   Send that URL to your client!
