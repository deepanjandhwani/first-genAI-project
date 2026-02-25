# Deploy this app on Streamlit Cloud (and fix “old UI” after update)

If you still see **sidebar + “Restaurant Recommendations”** instead of **red ZOMATO header + form in the middle**, Streamlit Cloud is running an **old deployment**. Do this:

## 1. Push the latest code to GitHub

From your project root (first-genAI-project), run:

```bash
git status
git add streamlit_app.py .streamlit/config.toml
git commit -m "Streamlit: Zomato header and main-area form"
git push origin main
```

Confirm on GitHub (in your repo in the browser) that `streamlit_app.py` contains the red **ZOMATO** header and that the form is **not** inside `with st.sidebar:`.

## 2. Force Streamlit Cloud to use the new code

**Option A – Redeploy (if available)**  
- Open your app on [share.streamlit.io](https://share.streamlit.io).  
- Click **“Manage app”** (bottom right).  
- If you see **“Redeploy”** or **“Rebuild”**, use it so the app pulls the latest commit.

**Option B – Delete and recreate the app (most reliable)**  
- In Streamlit Cloud, **delete** the current app.  
- Click **“New app”**.  
- Repository: `deepanjandhwani/first-genAI-project`  
- Branch: `main`  
- Main file path: `streamlit_app.py`  
- Click **Deploy**.

After a successful deploy of the new code you should see:

- A **red bar** at the top with **“ZOMATO”** and **“AI Restaurant Recommendation Platform”**
- The form (PLACE, MAX PRICE, MIN RATING, etc.) in the **main area** (no form in the sidebar)
- Sidebar **collapsed** by default (you can open it with the arrow; it will be empty)

If you still see the old UI, the app is still running an old commit: double-check the repo and branch on Streamlit Cloud and that you pushed to `main`.
