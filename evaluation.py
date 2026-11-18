"""
Offline evaluation helper for an annotated CSV.

Expected columns:
    text, aspect, true_sentiment
Sentiment values must be positive, negative, or neutral.

Run:
    python evaluation.py annotated_reviews.csv

This evaluates the included baseline analyzer. It does not claim to evaluate BERT.
"""
import csv, sys
from collections import defaultdict
from analyzer import analyze_review
from sklearn.metrics import accuracy_score, precision_recall_fscore_support, classification_report, confusion_matrix

def main(path):
    y_true, y_pred = [], []
    with open(path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            text = row["text"].strip()
            aspect = row["aspect"].strip()
            true = row["true_sentiment"].strip().lower()
            if true not in {"positive","negative","neutral"}:
                continue
            predicted = next((x["sentiment"] for x in analyze_review(text) if x["aspect"].lower()==aspect.lower()), None)
            if predicted is None:
                predicted = analyze_review(text)[0]["sentiment"]
            y_true.append(true); y_pred.append(predicted)
    if not y_true:
        raise SystemExit("No valid labelled rows found.")
    p,r,f,_ = precision_recall_fscore_support(y_true,y_pred,labels=["positive","negative","neutral"],average="macro",zero_division=0)
    print(f"Samples: {len(y_true)}")
    print(f"Accuracy:  {accuracy_score(y_true,y_pred):.4f}")
    print(f"Macro precision: {p:.4f}")
    print(f"Macro recall:    {r:.4f}")
    print(f"Macro F1-score:  {f:.4f}")
    print("\nPer-class report:")
    print(classification_report(y_true,y_pred,labels=["positive","negative","neutral"],zero_division=0))
    print("Confusion matrix (positive, negative, neutral):")
    print(confusion_matrix(y_true,y_pred,labels=["positive","negative","neutral"]))

if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python evaluation.py annotated_reviews.csv")
    main(sys.argv[1])
