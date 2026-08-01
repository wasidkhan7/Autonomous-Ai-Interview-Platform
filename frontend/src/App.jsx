import CandidateRegister from "./pages/CandidateRegister";
import InterviewRoom from "./pages/InterviewRoom";
import MentorDashboard from "./pages/MentorDashboard";
import Analytics from "./pages/Analytics";
import MentorLogin from "./pages/MentorLogin";
import { BrowserRouter, Routes, Route, Link, useLocation, Navigate } from "react-router-dom";

function RequireMentorKey({ children }) {
  // Convenience only - the real check happens server-side on every request.
  // This just avoids showing an empty page that would 401 anyway.
  return localStorage.getItem("mentorKey")
    ? children
    : <Navigate to="/mentor-login" replace />;
}

function NavBar() {
  const hasMentorKey = !!localStorage.getItem("mentorKey");
  const location = useLocation();

  const linkClass = (path) =>
    `px-4 py-2 rounded-md text-sm font-medium transition-colors ${
      location.pathname === path
        ? "bg-indigo-600 text-white"
        : "text-slate-900 hover:bg-slate-100"
    }`;

  return (
    <nav className="bg-white border-b border-slate-200 px-6 py-3 flex items-center gap-2">
      <span className="font-mono font-semibold text-slate-900 mr-6">AutonomIQ</span>
      <Link to="/" className={linkClass("/")}>Register</Link>
      {hasMentorKey ? (
        <>
          <Link to="/dashboard" className={linkClass("/dashboard")}>Mentor Dashboard</Link>
          <Link to="/analytics" className={linkClass("/analytics")}>Analytics</Link>
          <button
            onClick={() => {
              localStorage.removeItem("mentorKey");
              window.location.href = "/";
            }}
            className="ml-auto font-mono text-[11px] font-semibold uppercase tracking-wide text-[#5A6478] hover:text-slate-900"
          >
            Sign out
          </button>
        </>
      ) : (
        <Link to="/mentor-login" className={`${linkClass("/mentor-login")} ml-auto`}>
          Mentor access
        </Link>
      )}
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
          <Route path="/mentor-login" element={<MentorLogin />} />
          <Route path="/dashboard" element={<RequireMentorKey><MentorDashboard /></RequireMentorKey>} />
          <Route path="/analytics" element={<RequireMentorKey><Analytics /></RequireMentorKey>} />
        </Routes>
      </div>
    </BrowserRouter>
  );
}

export default App;
