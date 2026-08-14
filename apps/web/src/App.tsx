import { useEffect, useState } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { api, isAuthenticated } from "@/lib/api";
import { personaFor } from "@/lib/workspaces";
import PlatformAdmin from "@/pages/workspaces/PlatformAdmin";
import OrgAdmin from "@/pages/workspaces/OrgAdmin";
import Operator from "@/pages/workspaces/Operator";
import Analyst from "@/pages/workspaces/Analyst";
import SocManager from "@/pages/workspaces/SocManager";
import Executive from "@/pages/workspaces/Executive";
import Auditor from "@/pages/workspaces/Auditor";
import Responder from "@/pages/workspaces/Responder";
import Forbidden from "@/pages/Forbidden";
import Layout from "@/components/Layout";
import Account from "@/pages/Account";
import Admin from "@/pages/Admin";
import Alerts from "@/pages/Alerts";
import AssetDetail from "@/pages/AssetDetail";
import Assets from "@/pages/Assets";
import Dashboard from "@/pages/Dashboard";
import DigitalTwin from "@/pages/DigitalTwin";
import GlobalOps from "@/pages/GlobalOps";
import IncidentDetail from "@/pages/IncidentDetail";
import Investigations from "@/pages/Investigations";
import Login from "@/pages/Login";
import MissionIQ from "@/pages/MissionIQ";
import Quantum from "@/pages/Quantum";
import Reports from "@/pages/Reports";
import Sentinel from "@/pages/Sentinel";
import ThreatIntel from "@/pages/ThreatIntel";
import SSOCallback from "@/pages/SSOCallback";

function Guarded() {
  return isAuthenticated() ? <Layout /> : <Navigate to="/login" replace />;
}

/** Role-aware landing: "/" resolves to the caller's home workspace. */
function RoleHome() {
  const [route, setRoute] = useState<string | null>(null);
  useEffect(() => {
    api.me()
      .then((u) => setRoute(personaFor(u.roles).route))
      .catch(() => setRoute("/workspace/analyst"));
  }, []);
  if (!route) return null;
  return <Navigate to={route} replace />;
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/sso/callback" element={<SSOCallback />} />
        <Route element={<Guarded />}>
          <Route path="/" element={<RoleHome />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/workspace/platform" element={<PlatformAdmin />} />
          <Route path="/workspace/org" element={<OrgAdmin />} />
          <Route path="/workspace/operator" element={<Operator />} />
          <Route path="/workspace/analyst" element={<Analyst />} />
          <Route path="/workspace/soc" element={<SocManager />} />
          <Route path="/workspace/responder" element={<Responder />} />
          <Route path="/workspace/executive" element={<Executive />} />
          <Route path="/forbidden" element={<Forbidden />} />
          <Route path="/workspace/auditor" element={<Auditor />} />
          <Route path="/ops" element={<GlobalOps />} />
          <Route path="/assets" element={<Assets />} />
          <Route path="/assets/:id" element={<AssetDetail />} />
          <Route path="/alerts" element={<Alerts />} />
          <Route path="/investigations" element={<Investigations />} />
          <Route path="/investigations/:id" element={<IncidentDetail />} />
          <Route path="/threat-intel" element={<ThreatIntel />} />
          <Route path="/missioniq" element={<MissionIQ />} />
          <Route path="/digital-twin" element={<DigitalTwin />} />
          <Route path="/quantumshield" element={<Quantum />} />
          <Route path="/sentinel" element={<Sentinel />} />
          <Route path="/reports" element={<Reports />} />
          <Route path="/admin" element={<Admin />} />
          <Route path="/account" element={<Account />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
