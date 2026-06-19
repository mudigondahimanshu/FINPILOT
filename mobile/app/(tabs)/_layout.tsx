import { Tabs } from "expo-router";

export default function TabLayout() {
  return (
    <Tabs screenOptions={{ tabBarActiveTintColor: "#6366f1", tabBarStyle: { backgroundColor: "#0f172a", borderTopColor: "#1e293b" }, headerStyle: { backgroundColor: "#0f172a" }, headerTintColor: "#f8fafc" }}>
      <Tabs.Screen name="index" options={{ title: "Dashboard" }} />
      <Tabs.Screen name="transactions" options={{ title: "Transactions" }} />
      <Tabs.Screen name="trading" options={{ title: "Trading" }} />
      <Tabs.Screen name="insights" options={{ title: "AI Insights" }} />
    </Tabs>
  );
}
