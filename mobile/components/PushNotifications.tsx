/**
 * Push notification setup for FinPilot Mobile (Phase 4.5).
 *
 * Registers for Expo push notifications, requests permissions, and sends
 * the Expo push token to the backend so the server can trigger:
 *   - Fraud alerts (anomaly detected)
 *   - Budget warnings (> 80% of monthly budget spent)
 *   - Price alerts (watchlist stock moves > ±5%)
 *
 * Usage: call `registerForPushNotifications()` once after login.
 */
import * as Device from "expo-device";
import * as Notifications from "expo-notifications";
import * as SecureStore from "expo-secure-store";
import { Platform } from "react-native";

const API_URL = process.env.EXPO_PUBLIC_API_URL ?? "http://localhost:8000";

// Show notifications as banners even when app is foregrounded
Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowAlert: true,
    shouldPlaySound: true,
    shouldSetBadge: true,
  }),
});

export async function registerForPushNotifications(): Promise<string | null> {
  if (!Device.isDevice) {
    console.warn("Push notifications require a physical device");
    return null;
  }

  const { status: existing } = await Notifications.getPermissionsAsync();
  let finalStatus = existing;
  if (existing !== "granted") {
    const { status } = await Notifications.requestPermissionsAsync();
    finalStatus = status;
  }
  if (finalStatus !== "granted") {
    console.warn("Push notification permission denied");
    return null;
  }

  // Android requires a notification channel
  if (Platform.OS === "android") {
    await Notifications.setNotificationChannelAsync("finpilot-alerts", {
      name: "FinPilot Alerts",
      importance: Notifications.AndroidImportance.HIGH,
      vibrationPattern: [0, 250, 250, 250],
      lightColor: "#6366f1",
    });
  }

  const { data: expoPushToken } = await Notifications.getExpoPushTokenAsync({
    projectId: process.env.EXPO_PUBLIC_PROJECT_ID,
  });

  // Register token with backend
  try {
    const token = await SecureStore.getItemAsync("access_token");
    await fetch(`${API_URL}/auth/push-token`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify({ token: expoPushToken, platform: Platform.OS }),
    });
  } catch (err) {
    console.warn("Failed to register push token with backend:", err);
  }

  return expoPushToken;
}

export function usePushNotificationListener(
  onNotification: (notification: Notifications.Notification) => void,
  onResponse: (response: Notifications.NotificationResponse) => void,
) {
  const notificationListener = Notifications.addNotificationReceivedListener(onNotification);
  const responseListener = Notifications.addNotificationResponseReceivedListener(onResponse);
  return () => {
    notificationListener.remove();
    responseListener.remove();
  };
}
