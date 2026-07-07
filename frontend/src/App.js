import React from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { Toaster } from "sonner";
import Layout from "./components/Layout";
import Dashboard from "./pages/Dashboard";
import Products from "./pages/Products";
import ProductDetail from "./pages/ProductDetail";
import Alerts from "./pages/Alerts";
import AISearch from "./pages/AISearch";
import AICoach from "./pages/AICoach";
import Settings from "./pages/Settings";
import DebugLab from "./pages/DebugLab";
import Profile from "./pages/Profile";

export default function App() {
  return (
    <BrowserRouter>
      <Toaster theme="dark" position="top-right" richColors />
      <Layout>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/urunler" element={<Products />} />
          <Route path="/urunler/:id" element={<ProductDetail />} />
          <Route path="/uyarilar" element={<Alerts />} />
          <Route path="/ai-arama" element={<AISearch />} />
          <Route path="/ai-koc" element={<AICoach />} />
          <Route path="/ayarlar" element={<Settings />} />
          <Route path="/debug" element={<DebugLab />} />
          <Route path="/profil" element={<Profile />} />
        </Routes>
      </Layout>
    </BrowserRouter>
  );
}
