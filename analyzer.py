import re, html
from collections import defaultdict

ASPECTS = ["Product Quality", "Price", "Delivery", "Customer Service", "Packaging"]

ASPECT_TERMS = {
    "Product Quality": ["quality","durable","durability","broken","defective","material","performance","battery","camera","screen","sound","build","works","working","blender","product","reliable","poorly made"],
    "Price": ["price","cost","expensive","cheap","value","worth","affordable","overpriced","money"],
    "Delivery": ["delivery","shipping","arrived","late","delay","delivered","courier","dispatch","arrival"],
    "Customer Service": ["customer service","support","staff","seller","refund","response","helpful","unhelpful","service","complaint","communication"],
    "Packaging": ["packaging","package","box","wrapped","包装","damaged box","seal"]
}
POSITIVE = {"excellent","great","good","love","amazing","beautiful","fast","quick","comfortable","durable","perfect","helpful","easy","reliable","worth","best","satisfied","wonderful","nice","recommend","smooth"}
NEGATIVE = {"poor","bad","terrible","slow","late","broken","defective","expensive","overpriced","worst","unhelpful","damaged","noisy","drains","disappointed","awful","hate","problem","waste","uncomfortable"}

def clean_text(text):
    text = html.unescape(str(text or ""))
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"https?://\S+|www\.\S+", " ", text)
    text = re.sub(r"[\r\n\t]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def classify_segment(segment):
    words = re.findall(r"[a-z']+", segment.lower())
    pos = sum(1 for w in words if w in POSITIVE)
    neg = sum(1 for w in words if w in NEGATIVE)
    # Simple negation handling: "not good" should not count as positive.
    for i, word in enumerate(words[:-1]):
        if word in {"not","never","hardly"} and words[i+1] in POSITIVE:
            pos -= 1
            neg += 1
    if pos > neg:
        return "positive", min(0.99, 0.55 + 0.1 * (pos-neg))
    if neg > pos:
        return "negative", min(0.99, 0.55 + 0.1 * (neg-pos))
    return "neutral", 0.55

def analyze_review(text):
    text = clean_text(text)
    lower = text.lower()
    results = []
    for aspect, terms in ASPECT_TERMS.items():
        positions = [lower.find(term) for term in terms if lower.find(term) >= 0]
        if not positions:
            continue
        # Analyze sentence(s) containing an aspect keyword, preserving mixed sentiment.
        sentences = re.split(r"(?<=[.!?;])\s+", text)
        selected = []
        for sentence in sentences:
            s = sentence.lower()
            if any(term in s for term in terms):
                selected.append(sentence)
        if not selected:
            selected = [text]
        labels = [classify_segment(s) for s in selected]
        # Majority vote; if tied, neutral is the conservative result.
        counts = {k:sum(1 for label,_ in labels if label==k) for k in ("positive","negative","neutral")}
        sentiment = max(("positive","negative","neutral"), key=lambda k:(counts[k], k=="neutral"))
        confidence = round(sum(c for label,c in labels if label==sentiment)/max(1,counts[sentiment]), 3)
        results.append({"aspect":aspect,"sentiment":sentiment,"confidence":confidence,"method":"lexicon-baseline"})
    # If no aspect terms match, retain a general product-quality observation.
    if not results:
        sentiment, confidence = classify_segment(text)
        results.append({"aspect":"Product Quality","sentiment":sentiment,"confidence":confidence,"method":"lexicon-baseline-fallback"})
    return results
