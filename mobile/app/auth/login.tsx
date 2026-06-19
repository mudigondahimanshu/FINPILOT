import { router } from "expo-router";
import * as SecureStore from "expo-secure-store";
import React, { useState } from "react";
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";

const API_URL = process.env.EXPO_PUBLIC_API_URL ?? "http://localhost:8000";

export default function LoginScreen() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleLogin() {
    if (!email || !password) { setError("Email and password required"); return; }
    setLoading(true);
    setError("");
    try {
      const res = await fetch(`${API_URL}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      const data = await res.json();
      if (!res.ok) { setError(data.detail ?? "Login failed"); return; }
      await SecureStore.setItemAsync("access_token", data.access_token);
      await SecureStore.setItemAsync("refresh_token", data.refresh_token);
      router.replace("/(tabs)");
    } catch {
      setError("Network error — check your connection");
    } finally {
      setLoading(false);
    }
  }

  return (
    <KeyboardAvoidingView style={styles.container} behavior={Platform.OS === "ios" ? "padding" : undefined}>
      <View style={styles.inner}>
        <Text style={styles.logo}>FinPilot</Text>
        <Text style={styles.tagline}>AI-powered personal finance</Text>

        {error ? <Text style={styles.error}>{error}</Text> : null}

        <TextInput style={styles.input} placeholder="Email" placeholderTextColor="#64748b"
          value={email} onChangeText={setEmail} keyboardType="email-address"
          autoCapitalize="none" autoComplete="email" />
        <TextInput style={styles.input} placeholder="Password" placeholderTextColor="#64748b"
          value={password} onChangeText={setPassword} secureTextEntry />

        <Pressable style={[styles.btn, loading && styles.btnDisabled]} onPress={handleLogin} disabled={loading}>
          {loading ? <ActivityIndicator color="#fff" /> : <Text style={styles.btnText}>Sign In</Text>}
        </Pressable>

        <Pressable onPress={() => router.push("/auth/register")}>
          <Text style={styles.link}>Don't have an account? Register</Text>
        </Pressable>
      </View>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#0f172a" },
  inner: { flex: 1, justifyContent: "center", padding: 24 },
  logo: { fontSize: 36, fontWeight: "800", color: "#6366f1", textAlign: "center" },
  tagline: { fontSize: 14, color: "#64748b", textAlign: "center", marginBottom: 32 },
  error: { color: "#ef4444", backgroundColor: "#450a0a20", padding: 10, borderRadius: 8, marginBottom: 16, fontSize: 13 },
  input: { backgroundColor: "#1e293b", borderRadius: 10, paddingHorizontal: 16, paddingVertical: 14, color: "#f8fafc", fontSize: 15, marginBottom: 12, borderWidth: 1, borderColor: "#334155" },
  btn: { backgroundColor: "#6366f1", borderRadius: 10, paddingVertical: 14, alignItems: "center", marginTop: 8 },
  btnDisabled: { opacity: 0.6 },
  btnText: { color: "#fff", fontWeight: "700", fontSize: 16 },
  link: { color: "#6366f1", textAlign: "center", marginTop: 16, fontSize: 14 },
});
