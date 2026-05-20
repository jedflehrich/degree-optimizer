# Degree Optimizer

A web app that helps students find the optimal 4-year course plan by leveraging overlaps between degree requirements.

## What it does

- Input your current credits and transfer/AP equivalencies
- Select one or more degrees (double major, major + minor, certificates)
- Get an optimized semester-by-semester plan that minimizes redundancy and time-to-graduation

## Tech Stack

- **Frontend:** React (Vite)
- **Backend:** Python + FastAPI
- **Data:** UW-Madison degree requirements (expanding to other universities later)

## Project Structure

```
degree-optimizer/
├── frontend/       # React app
├── backend/        # FastAPI server + optimizer logic
│   └── data/       # Degree requirement definitions
└── README.md
```

## Status

Under active development. Currently targeting UW-Madison.
