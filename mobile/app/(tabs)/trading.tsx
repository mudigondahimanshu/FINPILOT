import React, { useEffect, useState } from "react";
import {
  ActivityIndicator,
  FlatList,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import * as SecureStore from "expo-secure-store";

const API_URL = process.env.EXPO_PUBLIC_API_URL ?? "http://localhost:8000";

type Quote = { symbol: string; price: number; change_pct: number; currency: string };
type Position = { symbol: string; quantity: number; avg_cost: number; current_value: number; pnl: number };

async function authFetch(path: string, opts?: RequestInit) {
  const token = await SecureStore.getItemAsync("access_token");
  return fetch(`${API_URL}${path}`, {
    ...opts,
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}`, ...opts?.headers },
  });
}

const WATCHLIST = ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "WIPRO.NS"];

export default function TradingScreen() {
  const [quotes, setQuotes] = useState<Record<string, Quote>>({});
  const [positions, setPositions] = useState<Position[]>([]);
  const [loadingQuotes, setLoadingQuotes] = useState(true);
  const [symbol, setSymbol] = useState("TCS.NS");
  const [qty, setQty] = useState("1");
  const [orderSide, setOrderSide] = useState<"buy" | "sell">("buy");
  const [orderMsg, setOrderMsg] = useState("");
  const [placing, setPlacing] = useState(false);

  useEffect(() => {
    void loadQuotes();
    void loadPositions();
  }, []);

  async function loadQuotes() {
    setLoadingQuotes(true);
    try {
      const results = await Promise.allSettled(
        WATCHLIST.map((s) => authFetch(`/market/quote/${s}`).then((r) => r.json()))
      );
      const map: Record<string, Quote> = {};
      results.forEach((r, i) => {
        if (r.status === "fulfilled") map[WATCHLIST[i]] = r.value;
      });
      setQuotes(map);
    } finally {
      setLoadingQuotes(false);
    }
  }

  async function loadPositions() {
    try {
      const r = await authFetch("/portfolio/positions");
      if (r.ok) setPositions(await r.json());
    } catch { /* ignore */ }
  }

  async function placeOrder() {
    if (!symbol || !qty) return;
    setPlacing(true);
    setOrderMsg("");
    try {
      const r = await authFetch("/market/paper/order", {
        method: "POST",
        body: JSON.stringify({ symbol, quantity: Number(qty), side: orderSide, order_type: "market" }),
      });
      const data = await r.json();
      setOrderMsg(r.ok ? `✓ ${orderSide.toUpperCase()} ${qty} ${symbol}` : data.detail ?? "Order failed");
      if (r.ok) void loadPositions();
    } catch {
      setOrderMsg("Network error");
    } finally {
      setPlacing(false);
    }
  }

  return (
    <ScrollView style={styles.container}>
      {/* Watchlist */}
      <Text style={styles.section}>Watchlist</Text>
      {loadingQuotes ? (
        <ActivityIndicator color="#6366f1" style={{ marginVertical: 16 }} />
      ) : (
        <View style={styles.quoteGrid}>
          {WATCHLIST.map((s) => {
            const q = quotes[s];
            const up = q ? q.change_pct >= 0 : true;
            return (
              <Pressable key={s} style={styles.quoteCard} onPress={() => setSymbol(s)}>
                <Text style={styles.quoteSymbol}>{s.replace(".NS", "")}</Text>
                <Text style={styles.quotePrice}>{q ? `₹${q.price.toFixed(2)}` : "—"}</Text>
                <Text style={[styles.quoteChange, { color: up ? "#22c55e" : "#ef4444" }]}>
                  {q ? `${up ? "+" : ""}${q.change_pct.toFixed(2)}%` : "—"}
                </Text>
              </Pressable>
            );
          })}
        </View>
      )}

      {/* Order form */}
      <Text style={styles.section}>Paper Trade</Text>
      <View style={styles.card}>
        <View style={styles.sideToggle}>
          {(["buy", "sell"] as const).map((side) => (
            <Pressable key={side} onPress={() => setOrderSide(side)}
              style={[styles.sideBtn, orderSide === side && (side === "buy" ? styles.sideBuyActive : styles.sideSellActive)]}>
              <Text style={[styles.sideBtnText, orderSide === side && styles.sideBtnTextActive]}>
                {side.toUpperCase()}
              </Text>
            </Pressable>
          ))}
        </View>
        <TextInput style={styles.input} value={symbol} onChangeText={setSymbol}
          placeholder="Symbol (e.g. TCS.NS)" placeholderTextColor="#64748b" autoCapitalize="characters" />
        <TextInput style={styles.input} value={qty} onChangeText={setQty}
          placeholder="Quantity" placeholderTextColor="#64748b" keyboardType="numeric" />
        <Pressable style={[styles.orderBtn, placing && styles.btnDisabled, { backgroundColor: orderSide === "buy" ? "#22c55e" : "#ef4444" }]}
          onPress={() => void placeOrder()} disabled={placing}>
          {placing ? <ActivityIndicator color="#fff" /> : <Text style={styles.orderBtnText}>{orderSide === "buy" ? "Buy" : "Sell"} (Paper)</Text>}
        </Pressable>
        {orderMsg ? <Text style={styles.orderMsg}>{orderMsg}</Text> : null}
      </View>

      {/* Positions */}
      {positions.length > 0 && (
        <>
          <Text style={styles.section}>Open Positions</Text>
          {positions.map((p) => (
            <View key={p.symbol} style={styles.positionRow}>
              <View>
                <Text style={styles.posSymbol}>{p.symbol}</Text>
                <Text style={styles.posQty}>{p.quantity} @ ₹{p.avg_cost.toFixed(2)}</Text>
              </View>
              <View style={{ alignItems: "flex-end" }}>
                <Text style={styles.posValue}>₹{p.current_value.toFixed(2)}</Text>
                <Text style={{ color: p.pnl >= 0 ? "#22c55e" : "#ef4444", fontSize: 12 }}>
                  {p.pnl >= 0 ? "+" : ""}₹{p.pnl.toFixed(2)}
                </Text>
              </View>
            </View>
          ))}
        </>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#0f172a" },
  section: { color: "#94a3b8", fontSize: 11, fontWeight: "600", textTransform: "uppercase", letterSpacing: 0.8, marginHorizontal: 16, marginTop: 20, marginBottom: 8 },
  quoteGrid: { flexDirection: "row", flexWrap: "wrap", paddingHorizontal: 12, gap: 8 },
  quoteCard: { width: "30%", backgroundColor: "#1e293b", borderRadius: 10, padding: 10 },
  quoteSymbol: { color: "#f8fafc", fontSize: 11, fontWeight: "700" },
  quotePrice: { color: "#f8fafc", fontSize: 13, fontWeight: "600", marginTop: 4 },
  quoteChange: { fontSize: 11, marginTop: 2 },
  card: { margin: 16, marginTop: 0, backgroundColor: "#1e293b", borderRadius: 12, padding: 16 },
  sideToggle: { flexDirection: "row", borderRadius: 8, overflow: "hidden", marginBottom: 12 },
  sideBtn: { flex: 1, padding: 10, alignItems: "center", backgroundColor: "#0f172a" },
  sideBuyActive: { backgroundColor: "#166534" },
  sideSellActive: { backgroundColor: "#7f1d1d" },
  sideBtnText: { color: "#64748b", fontWeight: "600", fontSize: 13 },
  sideBtnTextActive: { color: "#fff" },
  input: { backgroundColor: "#0f172a", borderRadius: 8, paddingHorizontal: 12, paddingVertical: 10, color: "#f8fafc", fontSize: 14, marginBottom: 10, borderWidth: 1, borderColor: "#334155" },
  orderBtn: { borderRadius: 8, paddingVertical: 12, alignItems: "center", marginTop: 4 },
  btnDisabled: { opacity: 0.6 },
  orderBtnText: { color: "#fff", fontWeight: "700", fontSize: 15 },
  orderMsg: { color: "#94a3b8", fontSize: 13, marginTop: 10, textAlign: "center" },
  positionRow: { marginHorizontal: 16, marginBottom: 8, backgroundColor: "#1e293b", borderRadius: 10, padding: 12, flexDirection: "row", justifyContent: "space-between" },
  posSymbol: { color: "#f8fafc", fontWeight: "600", fontSize: 14 },
  posQty: { color: "#64748b", fontSize: 12, marginTop: 2 },
  posValue: { color: "#f8fafc", fontWeight: "600", fontSize: 14 },
});
