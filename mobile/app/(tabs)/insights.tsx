import React, { useState } from "react";
import { ActivityIndicator, KeyboardAvoidingView, Platform, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";
import * as SecureStore from "expo-secure-store";

const API_URL = process.env.EXPO_PUBLIC_API_URL ?? "http://localhost:8000";

async function authFetch(path: string, opts?: RequestInit) {
  const token = await SecureStore.getItemAsync("access_token");
  return fetch(`${API_URL}${path}`, {
    ...opts,
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}`, ...opts?.headers },
  });
}

type Message = { role: "user" | "assistant"; content: string };

export default function InsightsScreen() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [fraudResult, setFraudResult] = useState<string | null>(null);
  const [fraudLoading, setFraudLoading] = useState(false);

  async function sendMessage() {
    const q = input.trim();
    if (!q || loading) return;
    setInput("");
    setMessages((m) => [...m, { role: "user", content: q }]);
    setLoading(true);
    try {
      const r = await authFetch("/ml/copilot/chat", {
        method: "POST",
        body: JSON.stringify({ question: q, history: messages.map((m) => ({ role: m.role, content: m.content })) }),
      });
      const data = await r.json();
      setMessages((m) => [...m, { role: "assistant", content: data.answer ?? data.detail ?? "Error" }]);
    } catch {
      setMessages((m) => [...m, { role: "assistant", content: "Network error" }]);
    } finally {
      setLoading(false);
    }
  }

  async function runFraudCheck() {
    setFraudLoading(true);
    setFraudResult(null);
    try {
      const r = await authFetch("/ml/fraud");
      const data = await r.json();
      const anomalies = (data.isolation_forest ?? []).filter((x: { is_anomaly: boolean }) => x.is_anomaly).length;
      setFraudResult(`${anomalies} anomalies detected across ${(data.isolation_forest ?? []).length} transactions.`);
    } catch {
      setFraudResult("Could not run fraud check.");
    } finally {
      setFraudLoading(false);
    }
  }

  return (
    <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === "ios" ? "padding" : undefined}>
      <ScrollView style={styles.container} keyboardShouldPersistTaps="handled">
        {/* Fraud Guard */}
        <Text style={styles.section}>Fraud Guard</Text>
        <View style={styles.card}>
          <Pressable style={styles.scanBtn} onPress={() => void runFraudCheck()} disabled={fraudLoading}>
            {fraudLoading ? <ActivityIndicator color="#fff" /> : <Text style={styles.scanBtnText}>Run Fraud Scan</Text>}
          </Pressable>
          {fraudResult && <Text style={styles.fraudResult}>{fraudResult}</Text>}
        </View>

        {/* AI Copilot */}
        <Text style={styles.section}>AI Copilot</Text>
        <View style={[styles.card, { minHeight: 200 }]}>
          {messages.length === 0 && (
            <Text style={styles.placeholder}>Ask FinPilot about your finances…</Text>
          )}
          {messages.map((m, i) => (
            <View key={i} style={[styles.bubble, m.role === "user" ? styles.bubbleUser : styles.bubbleBot]}>
              <Text style={[styles.bubbleText, m.role === "user" ? styles.bubbleTextUser : styles.bubbleTextBot]}>
                {m.content}
              </Text>
            </View>
          ))}
          {loading && <ActivityIndicator color="#6366f1" style={{ marginTop: 8 }} />}
        </View>

        {/* Input */}
        <View style={styles.inputRow}>
          <TextInput
            style={styles.textInput}
            value={input}
            onChangeText={setInput}
            placeholder="Ask a question…"
            placeholderTextColor="#64748b"
            onSubmitEditing={() => void sendMessage()}
            returnKeyType="send"
          />
          <Pressable style={[styles.sendBtn, (!input.trim() || loading) && styles.btnDisabled]}
            onPress={() => void sendMessage()} disabled={!input.trim() || loading}>
            <Text style={styles.sendBtnText}>↑</Text>
          </Pressable>
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#0f172a" },
  section: { color: "#94a3b8", fontSize: 11, fontWeight: "600", textTransform: "uppercase", letterSpacing: 0.8, marginHorizontal: 16, marginTop: 20, marginBottom: 8 },
  card: { margin: 16, marginTop: 0, backgroundColor: "#1e293b", borderRadius: 12, padding: 14 },
  scanBtn: { backgroundColor: "#6366f1", borderRadius: 8, paddingVertical: 10, alignItems: "center" },
  scanBtnText: { color: "#fff", fontWeight: "700", fontSize: 14 },
  fraudResult: { color: "#94a3b8", fontSize: 13, marginTop: 10, textAlign: "center" },
  placeholder: { color: "#64748b", fontSize: 13, textAlign: "center", paddingVertical: 16 },
  bubble: { borderRadius: 10, padding: 10, marginVertical: 4, maxWidth: "85%" },
  bubbleUser: { alignSelf: "flex-end", backgroundColor: "#6366f1" },
  bubbleBot: { alignSelf: "flex-start", backgroundColor: "#334155" },
  bubbleText: { fontSize: 14, lineHeight: 20 },
  bubbleTextUser: { color: "#fff" },
  bubbleTextBot: { color: "#f8fafc" },
  inputRow: { flexDirection: "row", margin: 16, marginTop: 8, gap: 8 },
  textInput: { flex: 1, backgroundColor: "#1e293b", borderRadius: 10, paddingHorizontal: 14, paddingVertical: 10, color: "#f8fafc", fontSize: 14, borderWidth: 1, borderColor: "#334155" },
  sendBtn: { backgroundColor: "#6366f1", borderRadius: 10, width: 44, alignItems: "center", justifyContent: "center" },
  btnDisabled: { opacity: 0.5 },
  sendBtnText: { color: "#fff", fontSize: 20, fontWeight: "700" },
});
