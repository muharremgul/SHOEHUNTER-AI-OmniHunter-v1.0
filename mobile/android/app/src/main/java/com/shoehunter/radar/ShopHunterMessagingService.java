package com.shoehunter.radar;

import androidx.annotation.NonNull;

import com.google.firebase.messaging.FirebaseMessagingService;
import com.google.firebase.messaging.RemoteMessage;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.Map;

public final class ShopHunterMessagingService extends FirebaseMessagingService {
    @Override
    public void onRegistered(@NonNull String installationId) {
        FcmRegistrationSync.persistAndSync(this, installationId);
    }

    @Override
    public void onMessageReceived(@NonNull RemoteMessage message) {
        Map<String, String> data = message.getData();
        if (data.isEmpty()) return;
        try {
            JSONObject alert = new JSONObject();
            alert.put("id", data.getOrDefault("alert_id", message.getMessageId()));
            alert.put("alert_type", data.getOrDefault("alert_type", "radar"));
            alert.put("title", data.getOrDefault("title", "ShopHunter Radar"));
            alert.put("notification_body", data.getOrDefault("notification_body", ""));
            alert.put("product_name", data.getOrDefault("product_name", "Ürün"));
            alert.put("store", data.getOrDefault("store", "Mağaza"));
            alert.put("url", data.getOrDefault("url", ""));
            String price = data.getOrDefault("price", "");
            if (!price.isEmpty()) alert.put("price", Double.parseDouble(price));
            String sizes = data.getOrDefault("sizes", "[]");
            alert.put("sizes", new JSONArray(sizes));
            NotificationHelper.showAlert(this, alert);
        } catch (Exception ignored) {
            // Malformed remote data is ignored; WorkManager can still retrieve the alert.
        }
    }
}
