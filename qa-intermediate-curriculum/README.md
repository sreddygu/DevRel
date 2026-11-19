# Qualcomm Academy Intermediate Curriculum

| **Projects** | **Status** | **Owner** |
|--------------|------------|-----------|
| Sinewave | Complete | Derrick |
| Wakeword Detection | In progress | Srinivas |
| Gesture Recognition | In progress | Sanjana |
| LLM | In progress | Derrick |

## Rules for Collaboration

| Action | Git Command | Notes |
|--------|-------------|-------|
| Create a new branch | git checkout -b dev/<your_name> | Always start from `main` before creating your dev branch |
| Switch to an existing branch | git checkout dev/<your_name> | Continue working on your branch |
| Update local main | git checkout main && git pull | Keeps your local main up to date |
| Stage changes | git add \<file> | Use `git add .` to stage everything |
| Commit changes | git commit -m "Meaningful message" | Write clear, descriptive commit messages |
| Push your branch | git push -u origin dev/<your_name> | First push sets upstream tracking |
| Open a Pull Request | *Done on GitHub/GitLab UI* | Target `main`, add description |
| Fetch latest remote branches | git fetch | Useful before creating a PR or updating your branch |
| Update your branch with main | git merge main | Run this inside your dev branch |
| Resolve merge conflicts | *Manual editing required* | After resolving: `git add .` + `git commit` |
| After PR approval, merge | *Done on GitHub/GitLab UI* | Never merge without approval |
| Delete your branch after merge | git branch -d dev/<your_name> | Optional cleanup |

## Python Environment

- Recommended: Python `3.11.15`
- Create venv: `python3.11 -m venv .venv` (or `python3 -m venv .venv` if `python3` is 3.11)
- Install deps: `python3 -m pip install -r requirements.txt`
