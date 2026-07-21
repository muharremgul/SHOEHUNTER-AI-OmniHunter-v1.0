package com.shoehunter.radar;

import java.text.Normalizer;
import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** Pure helpers for turning user-approved OCR lines into Radar identity evidence. */
final class OcrSelectionPayload {
    private static final int MAX_QUERY_LENGTH = 500;
    private static final Pattern[] PRODUCT_CODE_PATTERNS = new Pattern[]{
            Pattern.compile("\\b[A-Z]{2}\\d{4}-\\d{3}\\b"),
            Pattern.compile("\\b\\d{7}-\\d{3}\\b"),
            Pattern.compile("\\b[A-Z]{2}\\d{4}\\b"),
            Pattern.compile("\\b(?=[A-Z0-9-]{6,18}\\b)(?=[A-Z0-9-]*[A-Z])(?=[A-Z0-9-]*\\d)[A-Z0-9]+(?:-[A-Z0-9]+)*\\b")
    };

    private OcrSelectionPayload() {
    }

    static String joinSelected(List<String> lines) {
        Set<String> seen = new LinkedHashSet<>();
        StringBuilder query = new StringBuilder();
        for (String value : lines == null ? new ArrayList<String>() : lines) {
            String clean = clean(value);
            if (clean.isEmpty()) continue;
            String key = clean.toLowerCase(new Locale("tr", "TR"));
            if (!seen.add(key)) continue;
            int remaining = MAX_QUERY_LENGTH - query.length() - (query.length() == 0 ? 0 : 1);
            if (remaining <= 0) break;
            if (query.length() > 0) query.append(' ');
            query.append(clean, 0, Math.min(clean.length(), remaining));
        }
        return query.toString().trim();
    }

    static String findProductCode(List<String> lines) {
        for (String line : lines == null ? new ArrayList<String>() : lines) {
            String upper = clean(line).toUpperCase(Locale.ROOT);
            for (Pattern pattern : PRODUCT_CODE_PATTERNS) {
                Matcher matcher = pattern.matcher(upper);
                while (matcher.find()) {
                    String candidate = matcher.group();
                    if (!looksLikeMetadata(candidate)) return candidate;
                }
            }
        }
        return null;
    }

    static String findGtin(List<String> lines) {
        for (String line : lines == null ? new ArrayList<String>() : lines) {
            String digits = clean(line).replaceAll("\\D", "");
            if (isValidGtin(digits)) return digits;
        }
        return null;
    }

    static String findBrand(List<String> lines) {
        String folded = fold(joinSelected(lines));
        if (folded.contains("under armour")) return "Under Armour";
        if (folded.contains("the north face")) return "The North Face";
        if (folded.contains("new balance")) return "New Balance";
        if (folded.contains("jack&jones") || folded.contains("jack jones")
                || folded.contains("jack and jones")) return "Jack & Jones";
        if (folded.contains("on running")) return "On";
        if (folded.contains("adidas")) return "Adidas";
        if (folded.contains("nike")) return "Nike";
        if (folded.contains("puma")) return "Puma";
        if (folded.contains("salomon")) return "Salomon";
        if (folded.contains("columbia")) return "Columbia";
        if (folded.contains("brooks")) return "Brooks";
        if (folded.contains("asics")) return "Asics";
        if (folded.contains("skechers")) return "Skechers";
        if (folded.contains("reebok")) return "Reebok";
        if (folded.contains("converse")) return "Converse";
        if (folded.contains("vans")) return "Vans";
        if (folded.contains("fila")) return "Fila";
        if (folded.contains("hoka")) return "HOKA";
        if (folded.contains("decathlon")) return "Decathlon";
        if (folded.contains("kalenji")) return "Kalenji";
        if (folded.contains("kipsta")) return "Kipsta";
        return null;
    }

    static boolean isValidGtin(String value) {
        if (value == null || !value.matches("\\d{8}|\\d{12}|\\d{13}|\\d{14}")) return false;
        int total = 0;
        int bodyLength = value.length() - 1;
        for (int index = 0; index < bodyLength; index++) {
            int digit = value.charAt(index) - '0';
            total += digit * (((bodyLength - index) % 2 == 1) ? 3 : 1);
        }
        int expected = (10 - total % 10) % 10;
        return expected == value.charAt(bodyLength) - '0';
    }

    private static boolean looksLikeMetadata(String value) {
        String upper = value.toUpperCase(Locale.ROOT);
        return upper.startsWith("EAN") || upper.startsWith("UPC")
                || upper.startsWith("ART") || upper.startsWith("PO-");
    }

    private static String clean(String value) {
        if (value == null) return "";
        return value.trim().replaceAll("\\s+", " ");
    }

    private static String fold(String value) {
        String normalized = Normalizer.normalize(value == null ? "" : value, Normalizer.Form.NFD);
        return normalized.replaceAll("\\p{M}", "").toLowerCase(Locale.ROOT);
    }
}
