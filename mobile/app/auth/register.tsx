import { router } from "expo-router";
import React, { useState } from "react";
import { ActivityIndicator, KeyboardAvoidingView, Platform, Pressable, StyleSheet, Text, TextInput, View } from "react-native";

const API_URL = process.env.EXPO_PUBLIC_API_URL ?? "http://localhost:8000";

export default function RegisterScreen() {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleRegister() {
    if (!email || !password) { setError("Email and password required"); return; }
    setLoading(true);
    setError("");
    try {
      const res = await fetch(`${API_URL}/auth/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password, full_name: name }),
      });
      const data = await res.json();
      if (!res.ok) { setError(data.detail ?? "Registration failed"); return; }
      router.replace("/auth/login");
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
        <Text style={styles.tagline}>Create your account</Text>

        {error ? <Text style={styles.error}>{error}</Text> : null}

        <TextInput style={styles.input} placeholder="Full name" placeholderTextColor="#64748b"
          value={name} onChangeText={setName} autoComplete="name" />
        <TextInput style={styles.input} placeholder="Email" placeholderTextColor="#64748b"
          value={email} onChangeText={setEmail} keyboardType="email-address" autoCapitalize="none" />
        <TextInput style={styles.input} placeholder="Password" placeholderTextColor="#64748b"
          value={password} onChangeText={setPassword} secureTextEntry />

        <Pressable style={[styles.btn, loading && styles.btnDisabled]} onPress={handleRegister} disabled={loading}>
          {loading ? <ActivityIndicator color="#fff" /> : <Text style={styles.btnText}>Create Account</Text>}
        </Pressable>

        <Pressable onPress={() => router.back()}>
          <Text style={styles.link}>Already have an account? Sign In</Text>
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
