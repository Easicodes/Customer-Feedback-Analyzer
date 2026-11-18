# Customer Feedback Analyzer for Product Review and Aggregation

A runnable Flask web application implementing a five-stage customer-review pipeline:

1. **Data ingestion** — manual review entry and CSV import. Reviews can be tagged as Amazon, Trustpilot, or another source. The app does not scrape either platform automatically; use authorized exports/APIs and follow each platform's terms.
2. **Preprocessing** — HTML/URL cleanup, whitespace normalization, and stored cleaned text.
3. **Sentiment analysis** — aspect keyword identification across Product Quality, Price, Delivery, Customer Service, and Packaging, with positive/negative/neutral classification.
4. **Aggregation and storage** — SQLite stores products, reviews, and aspect-level sentiment results; product pages show aggregated counts and source comparisons.
5. **Visualization** — dashboard, product analytics, review browser, and CSV export.

## Important implementation and research note

The submitted research document describes a fine-tuned BERT-SVM hybrid, comparison against Naive Bayes, Logistic Regression and LSTM, and evaluation using accuracy, precision, recall, F1-score and SUS. This delivered codebase is a practical, locally runnable implementation of the system workflow. Its included sentiment engine is a transparent lexicon-based baseline, **not a trained BERT-SVM model**. It does not claim the performance numbers printed in the research document as results from this software.

For a defensible final-year evaluation, obtain an annotated review dataset, split it into train/validation/test sets, train and compare the proposed models, and report measured results. Do not copy illustrative numbers into Chapter Four unless they were actually produced by your experiments. The project can be extended with a trained BERT-SVM model when a suitable labelled dataset and compute environment are available.

## Run locally (Windows)

1. Install Python 3.10 or 3.11 from https://www.python.org/downloads/
2. Extract the ZIP file.
3. Open the extracted folder in VS Code.
4. Open Terminal and run:

```bash
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python app.py
```

5. Open http://127.0.0.1:5000

Default local admin login:
- Username: `admin`
- Password: `admin123`

Change these before any public deployment. The app starts with sample products and sample reviews so the dashboard is not empty.

## Main pages

- `/` — dashboard
- `/products` — product list
- `/products/<id>` — product-level aspect and source analytics
- `/reviews/add` — submit a review
- `/reviews/import` — admin CSV import
- `/evaluation` — evaluation overview
- `/export/reviews.csv` — admin CSV export
- `/health` — health check

## CSV import format

Required columns: `product_name`, `review_text`

Optional columns: `category`, `source`, `reviewer`, `rating`, `external_id`

Example:

```csv
product_name,category,source,reviewer,rating,review_text
Nova X Smartphone,Electronics,Amazon,Ada,5,"The battery is excellent but delivery was late."
Nova X Smartphone,Electronics,Trustpilot,John,2,"Poor camera quality and expensive price."
```

## Deploy on Render

This repository includes `render.yaml` and `Procfile`.

1. Create a GitHub repository and push the extracted project folder.
2. Create/sign in to https://render.com and choose **New + → Blueprint**.
3. Connect the GitHub repository. Render reads `render.yaml`.
4. When prompted, set `ADMIN_PASSWORD` to a strong password.
5. The included Blueprint requests a Starter web service and a persistent disk at `/var/data` for SQLite. Persistent disks require a paid Render web service; check current plan and disk pricing before deploying.
6. Deploy. Render builds dependencies and starts Gunicorn.
7. Open the generated `onrender.com` URL. Sign in with username `admin` and the password you configured.

Do not run this SQLite build on an ephemeral free filesystem if you need to retain reviews: Render's default filesystem is ephemeral, and persistent disks are available on paid services. For a free/low-cost experiment, use demo data only and understand that local database changes may disappear on restart/redeploy. For retained data, use a persistent disk or migrate the database adapter to managed PostgreSQL.

## Deploy on Railway

1. Push the project to GitHub.
2. In Railway, create a new project from the GitHub repository.
3. Add variables: `SECRET_KEY`, `ADMIN_USERNAME`, `ADMIN_PASSWORD`, and `DATABASE_PATH`.
4. Add a persistent volume and mount it at `/data`; set `DATABASE_PATH=/data/feedback.db`.
5. Railway detects the `Procfile`; deploy and open the generated domain.

## Security checklist before public use

- Set a strong `SECRET_KEY` and `ADMIN_PASSWORD`.
- Do not commit `.env` or real customer data to GitHub.
- Use HTTPS (Render/Railway provide HTTPS on generated domains).
- Add proper customer consent, privacy notice, rate limiting and stronger role-based access before commercial use.
- Configure backups for the database.
- This student/demo build is not yet hardened for high-volume production traffic.

## Testing

Run:

```bash
pytest -q
```

The included tests verify text cleanup and core aspect sentiment behaviour. For a research-grade evaluation, prepare a manually labelled test CSV with columns `text,aspect,true_sentiment`; evaluate predictions against labels and report macro-averaged precision, recall, F1 and accuracy. Include model comparisons only when those models have actually been trained and tested.

## Architecture

`Review source → Ingestion → Preprocessing → Aspect/Sentiment analysis → Aggregation + SQLite → Dashboard`

The current build supports manually submitted reviews and CSV import labelled by source. It does not automatically fetch Amazon or Trustpilot content; official APIs or authorized data exports should be integrated where access is permitted.
