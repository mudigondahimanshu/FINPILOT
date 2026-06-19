import React from "react";
import { ScrollView, StyleSheet, Text, View } from "react-native";

export default function DashboardScreen() {
  return (
    <ScrollView style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>FinPilot</Text>
        <Text style={styles.subtitle}>Your AI Finance Copilot</Text>
      </View>

      <View style={styles.kpiRow}>
        {[
          { label: "Income", value: "₹0", color: "#22c55e" },
          { label: "Expenses", value: "₹0", color: "#ef4444" },
          { label: "Net Savings", value: "₹0", color: "#6366f1" },
        ].map((k) => (
          <View key={k.label} style={styles.kpi}>
            <Text style={styles.kpiLabel}>{k.label}</Text>
            <Text style={[styles.kpiValue, { color: k.color }]}>{k.value}</Text>
          </View>
        ))}
      </View>

      <View style={styles.card}>
        <Text style={styles.cardTitle}>Recent Transactions</Text>
        <Text style={styles.empty}>No transactions yet. Add one to get started.</Text>
      </View>

      <View style={styles.card}>
        <Text style={styles.cardTitle}>Budget Overview</Text>
        <Text style={styles.empty}>Set budgets on the web app to see them here.</Text>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#0f172a" },
  header: { padding: 24, paddingTop: 48 },
  title: { fontSize: 28, fontWeight: "700", color: "#f8fafc" },
  subtitle: { fontSize: 14, color: "#94a3b8", marginTop: 4 },
  kpiRow: { flexDirection: "row", paddingHorizontal: 16, gap: 8, marginBottom: 16 },
  kpi: { flex: 1, backgroundColor: "#1e293b", borderRadius: 12, padding: 12, alignItems: "center" },
  kpiLabel: { fontSize: 10, color: "#64748b", textTransform: "uppercase", letterSpacing: 0.5 },
  kpiValue: { fontSize: 18, fontWeight: "700", marginTop: 4 },
  card: { margin: 16, marginTop: 0, backgroundColor: "#1e293b", borderRadius: 12, padding: 16 },
  cardTitle: { fontSize: 14, fontWeight: "600", color: "#f8fafc", marginBottom: 8 },
  empty: { fontSize: 13, color: "#64748b" },
});
