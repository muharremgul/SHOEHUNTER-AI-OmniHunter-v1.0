package com.shoehunter.radar;

import android.content.Context;
import android.content.SharedPreferences;

import androidx.annotation.NonNull;
import androidx.work.Constraints;
import androidx.work.ExistingPeriodicWorkPolicy;
import androidx.work.NetworkType;
import androidx.work.PeriodicWorkRequest;
import androidx.work.WorkManager;
import androidx.work.Worker;
import androidx.work.WorkerParameters;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URI;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.TimeUnit;

public class AlertSyncWorker extends Worker {
    static final String UNIQUE_WORK = "shoehunter-alert-sync";
    static final String PREFS = "shoehunter_mobile";
    static final String PREF_SERVER_URL = "server_url";
    static final String PREF_DEVICE_TOKEN = "mobile_device_token";
    static final String PREF_ALERT_CURSOR = "mobile_alert_cursor";

    public AlertSyncWorker(@NonNull Context context, @NonNull WorkerParameters parameters) {
        super(context, parameters);
    }

    static void schedule(Context context) {
        Constraints constraints = new Constraints.Builder()
                .setRequiredNetworkType(NetworkType.CONNECTED)
                .build();
        PeriodicWorkRequest request = new PeriodicWorkRequest.Builder(
                AlertSyncWorker.class, 15, TimeUnit.MINUTES)
                .setConstraints(constraints)
                .build();
        WorkManager.getInstance(context).enqueueUniquePeriodicWork(
                UNIQUE_WORK, ExistingPeriodicWorkPolicy.UPDATE, request);
    }

    @NonNull
    @Override
    public Result doWork() {
        SharedPreferences preferences = getApplicationContext()
                .getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        String serverUrl = preferences.getString(PREF_SERVER_URL, "");
        String token = preferences.getString(PREF_DEVICE_TOKEN, "");
        if (serverUrl == null || serverUrl.isEmpty() || token == null || token.isEmpty()) {
            return Result.success();
        }
        HttpURLConnection connection = null;
        try {
            String cursor = preferences.getString(PREF_ALERT_CURSOR, "");
            String endpoint = serverUrl + "/api/mobile/alerts?limit=30";
            if (cursor != null && !cursor.isEmpty()) {
                endpoint += "&since=" + URLEncoder.encode(cursor, StandardCharsets.UTF_8);
            }
            URI uri = new URI(endpoint);
            String scheme = uri.getScheme();
            if (!("http".equalsIgnoreCase(scheme) || "https".equalsIgnoreCase(scheme))
                    || uri.getHost() == null) return Result.failure();
            connection = (HttpURLConnection) uri.toURL().openConnection();
            connection.setConnectTimeout(10_000);
            connection.setReadTimeout(15_000);
            connection.setRequestProperty("Authorization", "Bearer " + token);
            connection.setRequestProperty("Accept", "application/json");
            if (connection.getResponseCode() == 401) return Result.failure();
            if (connection.getResponseCode() >= 500) return Result.retry();
            if (connection.getResponseCode() != 200) return Result.failure();
            StringBuilder response = new StringBuilder();
            try (BufferedReader reader = new BufferedReader(
                    new InputStreamReader(connection.getInputStream(), StandardCharsets.UTF_8))) {
                String line;
                while ((line = reader.readLine()) != null) response.append(line);
            }
            JSONObject payload = new JSONObject(response.toString());
            JSONArray alerts = payload.optJSONArray("alerts");
            if (alerts != null) {
                for (int index = 0; index < alerts.length(); index++) {
                    JSONObject alert = alerts.optJSONObject(index);
                    if (alert != null) NotificationHelper.showAlert(getApplicationContext(), alert);
                }
            }
            String nextCursor = payload.optString("cursor", "");
            if (!nextCursor.isEmpty()) {
                preferences.edit().putString(PREF_ALERT_CURSOR, nextCursor).apply();
            }
            return Result.success();
        } catch (Exception error) {
            return Result.retry();
        } finally {
            if (connection != null) connection.disconnect();
        }
    }
}
