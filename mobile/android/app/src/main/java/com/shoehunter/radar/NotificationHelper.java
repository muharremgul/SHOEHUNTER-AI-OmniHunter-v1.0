package com.shoehunter.radar;

import android.Manifest;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.os.Build;

import org.json.JSONArray;
import org.json.JSONObject;

final class NotificationHelper {
    static final String CHANNEL_ID = "shoehunter_radar_alerts";
    private static final String PREF_SHOWN_ALERT_IDS = "shown_alert_ids";

    private NotificationHelper() {}

    static void ensureChannel(Context context) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return;
        NotificationChannel channel = new NotificationChannel(
                CHANNEL_ID,
                context.getString(R.string.notification_channel_name),
                NotificationManager.IMPORTANCE_HIGH);
        channel.setDescription(context.getString(R.string.notification_channel_description));
        NotificationManager manager = context.getSystemService(NotificationManager.class);
        manager.createNotificationChannel(channel);
    }

    static void showAlert(Context context, JSONObject alert) {
        if (Build.VERSION.SDK_INT >= 33
                && context.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS)
                != PackageManager.PERMISSION_GRANTED) return;
        String alertId = alert.optString("id", "").trim();
        if (!alertId.isEmpty() && wasAlreadyShown(context, alertId)) return;
        ensureChannel(context);

        String title = alert.optString("title", "ShopHunter Radar");
        String product = alert.optString("product_name", "Ürün");
        String store = alert.optString("store", "Mağaza");
        String sizes = join(alert.optJSONArray("sizes"));
        double price = alert.optDouble("price", Double.NaN);
        StringBuilder body = new StringBuilder(product).append(" · ").append(store);
        if (!sizes.isEmpty()) body.append(" · Beden/numara: ").append(sizes);
        if (!Double.isNaN(price)) body.append(" · ").append(String.format("%.2f TL", price));
        String remoteBody = alert.optString("notification_body", "").trim();
        if (!remoteBody.isEmpty()) body = new StringBuilder(remoteBody);

        Intent intent;
        String url = alert.optString("url", "").trim();
        Uri uri = url.isEmpty() ? null : Uri.parse(url);
        if (uri != null && "https".equalsIgnoreCase(uri.getScheme()) && uri.getHost() != null) {
            intent = new Intent(Intent.ACTION_VIEW, uri);
        } else {
            intent = new Intent(context, MainActivity.class)
                    .addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP | Intent.FLAG_ACTIVITY_SINGLE_TOP);
        }
        PendingIntent pendingIntent = PendingIntent.getActivity(
                context,
                alert.optString("id", body.toString()).hashCode(),
                intent,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        Notification.Builder builder = Build.VERSION.SDK_INT >= Build.VERSION_CODES.O
                ? new Notification.Builder(context, CHANNEL_ID)
                : new Notification.Builder(context);
        Notification notification = builder
                .setSmallIcon(R.drawable.ic_launcher)
                .setContentTitle(title)
                .setContentText(body.toString())
                .setStyle(new Notification.BigTextStyle().bigText(body.toString()))
                .setContentIntent(pendingIntent)
                .setAutoCancel(true)
                .setShowWhen(true)
                .build();
        NotificationManager manager = (NotificationManager) context.getSystemService(Context.NOTIFICATION_SERVICE);
        manager.notify(alert.optString("id", body.toString()).hashCode(), notification);
        if (!alertId.isEmpty()) rememberShown(context, alertId);
    }

    private static synchronized boolean wasAlreadyShown(Context context, String alertId) {
        SharedPreferences preferences = context.getSharedPreferences(
                AlertSyncWorker.PREFS, Context.MODE_PRIVATE);
        try {
            JSONArray values = new JSONArray(preferences.getString(PREF_SHOWN_ALERT_IDS, "[]"));
            for (int index = 0; index < values.length(); index++) {
                if (alertId.equals(values.optString(index))) return true;
            }
        } catch (Exception ignored) {
            // Invalid local history is replaced after the next successful notification.
        }
        return false;
    }

    private static synchronized void rememberShown(Context context, String alertId) {
        SharedPreferences preferences = context.getSharedPreferences(
                AlertSyncWorker.PREFS, Context.MODE_PRIVATE);
        JSONArray current;
        try {
            current = new JSONArray(preferences.getString(PREF_SHOWN_ALERT_IDS, "[]"));
        } catch (Exception ignored) {
            current = new JSONArray();
        }
        JSONArray bounded = new JSONArray();
        int start = Math.max(0, current.length() - 99);
        for (int index = start; index < current.length(); index++) {
            String value = current.optString(index, "");
            if (!value.isEmpty() && !alertId.equals(value)) bounded.put(value);
        }
        bounded.put(alertId);
        preferences.edit().putString(PREF_SHOWN_ALERT_IDS, bounded.toString()).apply();
    }

    private static String join(JSONArray values) {
        if (values == null) return "";
        StringBuilder output = new StringBuilder();
        for (int index = 0; index < values.length(); index++) {
            String value = values.optString(index, "").trim();
            if (value.isEmpty()) continue;
            if (output.length() > 0) output.append(", ");
            output.append(value);
        }
        return output.toString();
    }
}
