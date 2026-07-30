import { BrowserRouter, Routes, Route, Link, useLocation } from "react-router-dom";
import CandidateRegister from "./pages/CandidateRegister";
import InterviewRoom from "./pages/InterviewRoom";
import MentorDashboard from "./pages/MentorDashboard";
import Analytics from "./pages/Analytics";

function NavBar() {
  const location = useLocation();

  const linkClass = (path) =>
    `px-4 py-2 rounded-md text-sm font-medium transition-colors ${
      location.pathname === path
        ? "bg-indigo-600 text-white"
        : "text-slate-900 hover:bg-slate-100"
    }`;
Routes
  return (
    <nav className="bg-white border-b border-slate-200 px-6 py-3 flex items-center gap-2">
      <span className="font-mono font-semibold text-slate-900 mr-6">AutonomIQ</span>
      <Link to="/" className={linkClass("/")}>Register</Link>
      <Link to="/dashboard" className={linkClass("/dashboard")}>Mentor Dashboard</Link>
      <Link to="/analytics" className={linkClass("/analytics")}>Analytics</Link>
    </nav>
  );
}

function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-[#F7F8FA]">
        <NavBar />
        <Routes>
          <Route path="/" element={<CandidateRegister />} />
          <Route path="/interview/:interviewId" element={<InterviewRoom />} />
          <Route path="/dashboard" element={<MentorDashboard />} />
          <Route path="/analytics" element={<Analytics />} />
        </Routes>
      </div>
    </BrowserRouter>
  );
}

export default App;
