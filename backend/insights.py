from datetime import datetime, timedelta, timezone


def _dt(iso):
    try:
        d = datetime.fromisoformat(iso)
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


def compute_price_insight(history, current_price, target_price):
    now = datetime.now(timezone.utc)
    points = []
    for h in history:
        p = h.get("price")
        if p is None or p <= 0 or p > 150000:
            continue
        t = _dt(h.get("checked_at"))
        if t:
            points.append((t, p))

    def window_vals(days):
        cutoff = now - timedelta(days=days)
        return [p for t, p in points if t >= cutoff]

    v7, v30, v90 = window_vals(7), window_vals(30), window_vals(90)
    min_30d = min(v30) if v30 else None
    avg_30d = round(sum(v30) / len(v30), 2) if v30 else None
    return {
        "current_price": current_price,
        "target_price": target_price,
        "min_7d": min(v7) if v7 else None,
        "min_30d": min_30d,
        "min_90d": min(v90) if v90 else None,
        "avg_30d": avg_30d,
        "is_near_lowest": bool(current_price and min_30d and current_price <= min_30d * 1.02),
        "data_points": len(points),
    }


SOURCE_CONFIDENCE = {
    "cart_offer": 15,
    "manual": 14,
    "shelf": 12,
    "json_ld": 9,
    "embedded_json": 8,
    "meta": 6,
}


def _norm_size(s):
    return str(s or "").replace(",", ".").strip().upper()


def compute_buy_decision(listing, rule, insight, profile, product_name=""):
    reasons = []
    risks = []
    current = listing.get("last_price")
    sizes = listing.get("last_sizes") or []

    if current is None:
        return {
            "decision": "BELİRSİZ",
            "score": 0,
            "breakdown": {"fiyat": 0, "stok": 0, "profil": 0, "guven": 0},
            "reasons": ["Güncel fiyat okunamadı"],
            "risks": ["Fiyat verisi olmadan karar üretilemez"],
            "insight": insight,
        }

    target = rule.get("target_price") if rule else None
    old_price = listing.get("last_old_price")

    # ---- Fiyat skoru (0-40) ----
    price_score = 0
    if target:
        if current <= target:
            price_score += 20
            reasons.append(f"Hedef fiyatın ({target:.0f} TL) altında")
        elif current <= target * 1.1:
            price_score += 10
            reasons.append("Hedef fiyata çok yakın (%10 bandında)")
        else:
            risks.append(f"Hedef fiyatın ({target:.0f} TL) üzerinde")
    else:
        price_score += 8
        risks.append("Hedef fiyat kuralı tanımlı değil")
    if insight.get("is_near_lowest") and insight.get("data_points", 0) >= 3:
        price_score += 10
        reasons.append("Son 30 günün en düşük fiyatına yakın")
    elif insight.get("min_30d") and current > insight["min_30d"] * 1.1:
        risks.append(f"Son 30 günde daha ucuzu görüldü ({insight['min_30d']:.0f} TL)")
    if old_price and old_price > current:
        rate = (old_price - current) / old_price * 100
        if rate >= 20:
            price_score += 6
            reasons.append(f"Etiket fiyatına göre %{rate:.0f} indirim")
        elif rate >= 10:
            price_score += 4
        elif rate > 0:
            price_score += 2
    if listing.get("last_cart_price"):
        price_score += 4
        reasons.append("Sepet indirimi yakalandı")
        risks.append("Sepet indirimi ödeme ekranında doğrulanmalı")
    price_score = min(price_score, 40)

    # ---- Stok/beden skoru (0-20) ----
    desired_size = _norm_size((rule or {}).get("size")) or None
    if desired_size in ("", "-"):
        desired_size = None
    profile_size = _norm_size((profile or {}).get("shoe_size"))
    stocked = [_norm_size(s.get("name") or s.get("size")) for s in sizes if s.get("in_stock")]

    stock_score = 0
    if desired_size:
        if desired_size in stocked:
            stock_score = 20
            reasons.append(f"İstenen beden ({desired_size}) bildirim anında stokta görünüyordu")
        else:
            stock_score = 0
            risks.append(f"İstenen beden ({desired_size}) stokta görünmüyor")
    elif sizes:
        if stocked:
            stock_score = 14
            reasons.append(f"{len(stocked)} beden stokta görünüyor")
        else:
            risks.append("Hiçbir beden stokta görünmüyor")
    else:
        stock_score = 8 if listing.get("last_in_stock") else 3
        risks.append("Beden bazlı stok bilgisi yok, stok durumu belirsiz")
    if stocked:
        risks.append("Stok hızlı tükenebilir")

    # ---- Profil uygunluğu (0-25) ----
    profile_score = 5
    if profile and (profile.get("usage") or profile.get("priorities")):
        profile_score = 8
    if profile_size:
        matched = profile_size in stocked
        if matched:
            profile_score += 12
            reasons.append(f"Profilinizdeki numara ({profile.get('shoe_size')}) stokta")
        elif stocked:
            risks.append("Profilinizdeki numara stok listesinde görünmüyor")
    if rule:
        profile_score += 5
    profile_score = min(profile_score, 25)

    # ---- Fırsat güveni (0-15) ----
    source = listing.get("last_price_source") or ""
    conf_score = SOURCE_CONFIDENCE.get(source, 4 if source else 2)
    if listing.get("last_error"):
        conf_score = 2
        risks.append("Son kontrolde hata alındı, veri bayat olabilir")
    if source == "cart_offer":
        reasons.append("Fiyat sepet teklifinden okundu (yüksek güven)")

    total = price_score + stock_score + profile_score + conf_score
    if total >= 85:
        decision = "AL"
    elif total >= 70:
        decision = "ALINABİLİR"
    elif total >= 50:
        decision = "BEKLE"
    elif total >= 30:
        decision = "SADECE ÇOK UCUZSA"
    else:
        decision = "UYGUN DEĞİL"
    if conf_score <= 2 and not sizes:
        decision = "BELİRSİZ"

    return {
        "decision": decision,
        "score": total,
        "breakdown": {"fiyat": price_score, "stok": stock_score, "profil": profile_score, "guven": conf_score},
        "reasons": reasons[:6],
        "risks": risks[:5],
        "insight": insight,
    }


def short_comment(decision_result):
    d = decision_result
    parts = d["reasons"][:2]
    text = f"{d['decision']} ({d['score']}/100)"
    if parts:
        text += ". " + "; ".join(parts)
    return text
