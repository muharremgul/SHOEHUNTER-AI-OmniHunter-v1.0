package com.shoehunter.radar;

import android.content.Context;
import android.content.SharedPreferences;

import org.json.JSONObject;

import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URI;
import java.nio.charset.StandardCharsets;

final class FcmRegistrationSync {
    static final String PREF_FCM_FID = "firebase_installation_id";

    private FcmRegistrationSync() {}

    static void persistAndSync(Context context, String installationId) {
        if (installationId == null || installationId.trim().length() < 10) return;
        SharedPreferences preferences = context.getSharedPreferences(
                AlertSyncWorker.PREFS, Context.MODE_PRIVATE);
        preferences.edit().putString(PREF_FCM_FID, installationId.trim()).apply();
        syncStored(context);
    }

    static void syncStored(Context context) {
        Context application = context.getApplicationContext();
        SharedPreferences preferences = application.getSharedPreferences(
                AlertSyncWorker.PREFS, Context.MODE_PRIVATE);
        String installationId = preferences.getString(PREF_FCM_FID, "");
        String deviceToken = preferences.getString(AlertSyncWorker.PREF_DEVICE_TOKEN, "");
        String serverUrl = preferences.getString(AlertSyncWorker.PREF_SERVER_URL, "");
        if (installationId == null || installationId.length() < 10
                || deviceToken == null || deviceToken.isEmpty()
                || serverUrl == null || serverUrl.isEmpty()) return;
        new Thread(
                () -> postInstallationId(serverUrl, deviceToken, installationId),
                "fcm-fid-sync").start();
    }

    private static void postInstallationId(
            String serverUrl, String deviceToken, String installationId) {
        HttpURLConnection connection = null;
        try {
            URI uri = new URI(serverUrl + "/api/mobile/device/push-registration");
            String scheme = uri.getScheme();
            if (!("http".equalsIgnoreCase(scheme) || "https".equalsIgnoreCase(scheme))
                    || uri.getHost() == null) return;
            connection = (HttpURLConnection) uri.toURL().openConnection();
            connection.setRequestMethod("POST");
            connection.setConnectTimeout(10_000);
            connection.setReadTimeout(15_000);
            connection.setDoOutput(true);
            connection.setRequestProperty("Authorization", "Bearer " + deviceToken);
            connection.setRequestProperty("Content-Type", "application/json; charset=utf-8");
            byte[] body = new JSONObject().put("installation_id", installationId)
                    .toString().getBytes(StandardCharsets.UTF_8);
            connection.setFixedLengthStreamingMode(body.length);
            try (OutputStream output = connection.getOutputStream()) {
                output.write(body);
            }
            connection.getResponseCode();
        } catch (Exception ignored) {
            // WorkManager remains the fallback; the FID is retried on the next app page load.
        } finally {
            if (connection != null) connection.disconnect();
        }
    }
}
