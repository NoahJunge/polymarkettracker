import { Routes, Route } from "react-router-dom";
import Layout from "./components/Layout";
import Dashboard from "./pages/Dashboard";
import MarketDetail from "./pages/MarketDetail";
import Discovery from "./pages/Discovery";
import PaperTrading from "./pages/PaperTrading";
import Settings from "./pages/Settings";

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/markets/:marketId" element={<MarketDetail />} />
        <Route path="/discovery" element={<Discovery />} />
        <Route path="/paper-trading" element={<PaperTrading />} />
        <Route path="/settings" element={<Settings />} />
      </Routes>
    </Layout>
  );
}
