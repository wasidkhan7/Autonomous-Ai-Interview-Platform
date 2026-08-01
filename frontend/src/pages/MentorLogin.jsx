// This is the login page for mentors. It is a simple form that asks for the mentor key, which is stored in localStorage 
// and sent with every request to the backend.
//  The backend checks the key against the value in the .env file and returns 401 if it doesn't match.
import { useState } from "react";
import apiClient from "../api/client";

const LABEL = "font-mono text-[11px] font-semibold uppercase tracking-[0.14em] text-[#5A6478]";

function MentorLogin() {
  const [key, setKey] = useState("");
  const [isChecking, setIsChecking] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");

  async function handleSubmit(e) {
    e.preventDefault();
    setErrorMessage("");
    setIsChecking(true);

    // Store first so the interceptor picks it up, then verify against a real
    // protected endpoint. Clear it again if the server rejects it.
    localStorage.setItem("mentorKey", key.trim());

    try {
      await apiClient.get("/analytics/overview");
      // Full page load so the nav bar re-reads localStorage and shows the links.
      window.location.href = "/dashboard";
    } catch (err) {
      localStorage.removeItem("mentorKey");
      setErrorMessage(
        err.response?.status === 401
          ? "That key isn't right. Check it and try again."
          : "Couldn't reach the server. Is the backend running?"
      );
      setIsChecking(false);
    }
  }

  return (
    <div className="min-h-[calc(100vh-57px)] bg-[#F7F8FA] flex items-center justify-center px-6">
      <form onSubmit={handleSubmit} className="w-full max-w-sm bg-white border border-[#EAEDF2] rounded-lg p-6">
        <p className={LABEL}>Ezitech · AutonomIQ</p>
        <h1 className="text-xl font-semibold text-slate-900 mt-1">Mentor access</h1>
        <p className="text-[14px] text-[#5A6478] mt-1.5 mb-5">
          Enter the mentor key to view candidate reports and analytics.
        </p>

        <input
          type="password"
          value={key}
          onChange={(e) => setKey(e.target.value)}
          required
          autoFocus
          placeholder="Mentor key"
          className="w-full border border-[#D8DDE6] rounded-md px-3 py-2.5 text-[15px] font-mono focus:outline-none focus:ring-2 focus:ring-indigo-600 focus:border-indigo-600"
        />

        {errorMessage && (
          <div className="bg-red-50 border border-red-200 text-red-700 text-[13px] rounded-md px-3 py-2 mt-3">
            {errorMessage}
          </div>
        )}

        <button
          type="submit"
          disabled={isChecking || !key.trim()}
          className="w-full mt-4 bg-indigo-600 text-white text-[15px] font-medium py-2.5 rounded-md hover:bg-indigo-700 disabled:opacity-40 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-indigo-600 focus:ring-offset-2 transition-colors"
        >
          {isChecking ? "Checking…" : "Continue"}
        </button>
      </form>
    </div>
  );
}

export default MentorLogin;